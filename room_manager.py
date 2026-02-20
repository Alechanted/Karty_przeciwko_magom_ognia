import os
import glob
import logging
import random
import time
from typing import Dict, Optional
from fastapi import WebSocket

from game_engine import GameEngine
from models import GameSettings
from enums import Phase
from locales import TEXTS

logger = logging.getLogger(__name__)


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, GameEngine] = {}
        self.player_room_map: Dict[WebSocket, str] = {}
        self.active_connections: Dict[WebSocket, Optional[str]] = {}

        # Anti-spam dla lobby
        self.last_lobby_sound_time = 0
        self.lobby_sound_cooldown = 2.0  # sekundy

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = None

    async def remove_player(self, websocket: WebSocket, remove_connection: bool):
        room_removed = False

        nick = None
        if remove_connection:
            nick = self.active_connections.pop(websocket, None)
        else:
            nick = self.active_connections.get(websocket)

        room_name = self.player_room_map.pop(websocket, None)
        room = self.rooms.get(room_name) if room_name else None

        if room:
            room.remove_player(websocket)
            if not room.players_data:
                logger.info(f"Pokój '{room_name}' jest pusty. Usuwanie.")
                del self.rooms[room_name]
                room_removed = True

        # Jeśli gracz był w lobby (nie w pokoju) i miał nick -> dźwięk wyjścia
        if room_name is None and nick:
            await self.broadcast_lobby_sound("goodbye")

        return nick, room_name, room_removed

    def get_deck_list(self):
        files = glob.glob("decks/*.*")
        decks = set()
        for f in files:
            base = os.path.basename(f)
            name = os.path.splitext(base)[0]
            decks.add(name)
        return list(decks)

    async def broadcast_room_count(self, room_name: str):
        """Send a minimal update about a single room to lobby clients only."""
        room = self.rooms.get(room_name)
        if not room:
            return

        payload = {
            "type": "ROOM_UPDATE",
            "room": {
                "name": room_name,
                "players": len(room.players_data),
                "max": room.settings.max_players,
                "has_password": room.settings.has_password()
            }
        }

        for ws, nick in list(self.active_connections.items()):
            try:
                if self.player_room_map.get(ws) is None:
                    await ws.send_json(payload)
            except Exception:
                pass

    async def broadcast_lobby_players(self):
        """Send current list of connected players (with room info) to lobby clients."""
        players_list = [{
            'nick': nick,
            'room': self.player_room_map.get(ws)
        } for ws, nick in self.active_connections.items() if nick]

        payload = {"type": "LOBBY_PLAYERS", "players": players_list}

        for ws, _ in list(self.active_connections.items()):
            try:
                if not self.player_room_map.get(ws):
                    await ws.send_json(payload)
            except Exception:
                pass

    def create_room(self, owner_name: str, settings: GameSettings):
        if settings.name in self.rooms:
            return False
        
        engine = GameEngine(owner_name, settings)
        engine.broadcast_callback = self.broadcast_room_state
        engine.sound_callback = self.broadcast_sound_to_room

        self.rooms[settings.name] = engine
        return True

    async def join_room(self, websocket, room_name, password):
        room = self.rooms.get(room_name)
        if not room: return TEXTS["ERR_NO_ROOM"]

        if not room.is_password_correct(password):
            return TEXTS["ERR_WRONG_PASS"]

        if len(room.players_data) >= room.settings.max_players:
            return TEXTS["ERR_ROOM_FULL"]

        nick = self.active_connections.get(websocket)
        if not nick:
            return "ERR_NO_NICK"
        self.player_room_map[websocket] = room_name
        room.add_player(websocket, nick)
        return "OK"

    async def send_room_list(self, websocket):
        rooms, players = self._get_rooms_and_players()
        
        await websocket.send_json({"type": "ROOM_LIST", "rooms": rooms, "players": players})

    async def broadcast_room_list(self):
        # Full room list is intended only for lobby clients.
        rooms, players = self._get_rooms_and_players()

        for ws in list(self.active_connections.keys()):
            try:
                if self.player_room_map.get(ws) is None:
                    await ws.send_json({"type": "ROOM_LIST", "rooms": rooms, "players": players})
            except Exception:
                pass

    async def broadcast_room_state(self, room_name):
        room = self.rooms.get(room_name)
        if not room: return

        black_card_data = None
        if room.current_black_card:
            black_card_data = {
                "text": room.current_black_card.get_display_text(),
                "pick": room.current_black_card.pick_count
            }

        submissions_data = []
        if room.phase in [Phase.JUDGING, Phase.SUMMARY]:
            for i, (ws, cards) in enumerate(room.judging_order):
                full_text = room.current_black_card.fill_blanks(cards)
                entry = {"id": i, "full_text": full_text}
                if room.phase == Phase.SUMMARY:
                    entry['author'] = room.players_data.get(ws, {}).get('nick', '???')
                    entry['is_winner'] = (i == room.winning_submission_index)
                submissions_data.append(entry)

        relevant = [s for s, p in room.players_data.items() if len(p['hand']) > 0]
        if not relevant: relevant = list(room.players_data.keys())
        ready_count = len([s for s in room.ready_players if s in relevant])

        players_list = []
        for ws, p in room.players_data.items():
            players_list.append({
                "nick": p['nick'], "score": p['score'], "is_czar": (ws == room.czar_socket)
            })

        for ws in list(room.players_data.keys()):
            try:
                player = room.players_data.get(ws, {})
                hand = player.get('hand', [])
                nick = player.get('nick', '')
                hand_data = [{"id": c.id, "text": c.get_nominative()} for c in hand]
                can_start_game = room.phase == Phase.LOBBY and len(room.players_data) > 1 and room.can_start_game(nick)
                
                await ws.send_json({
                    "type": "GAME_UPDATE",
                    "phase": room.phase.value,
                    "black_card": black_card_data,
                    "hand": hand_data,
                    "is_czar": (ws == room.czar_socket),
                    "submissions": submissions_data,
                    "has_submitted": (ws in room.round_submissions),
                    "ready_status": {"ready": ready_count, "total": len(relevant)},
                    "am_i_ready": (ws in room.ready_players),
                    "players_list": players_list,
                    "winner": room.winner_nick,
                    "room_name": room_name,
                    "can_start_game": can_start_game
                })
            except Exception:
                pass

    def _get_rooms_and_players(self):
        rooms_list = [{
            "name": name,
            "players": len(engine.players_data),
            "max": engine.settings.max_players,
            "has_password": engine.settings.has_password()
        } for name, engine in self.rooms.items()]

        players_list = [{
            "nick": nick,
            "room": self.player_room_map.get(ws)
        } for ws, nick in self.active_connections.items() if nick]

        return rooms_list, players_list

        # --- SOUND SYSTEM ---

    def _get_random_sound_file(self, prefix: str) -> Optional[str]:
        """Skanuje static/sounds w poszukiwaniu plików pasujących do prefixu i losuje jeden."""
        # Szukamy plików zaczynających się od prefixu (np. welcome*)
        search_pattern = os.path.join("static", "sounds", f"{prefix}*")
        files = glob.glob(search_pattern)

        # Filtrujemy tylko audio
        valid_exts = {'.mp3', '.wav', '.ogg', '.m4a'}
        audio_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_exts]

        if not audio_files:
            return None

        selected = random.choice(audio_files)
        # Zamieniamy ścieżkę na URL (np. static/sounds/welcome1.mp3 -> /static/sounds/welcome1.mp3)
        return "/" + selected.replace(os.sep, "/")

    async def broadcast_lobby_sound(self, prefix: str):
        """Odtwarza dźwięk wszystkim w lobby (z anty-spamem)."""
        now = time.time()
        if now - self.last_lobby_sound_time < self.lobby_sound_cooldown:
            return

        sound_src = self._get_random_sound_file(prefix)
        if not sound_src:
            return

        self.last_lobby_sound_time = now
        payload = {"type": "PLAY_SOUND", "src": sound_src}

        for ws in list(self.active_connections.keys()):
            # Tylko gracze, którzy nie są w żadnym pokoju
            if self.player_room_map.get(ws) is None:
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass

    async def broadcast_sound_to_room(self, room_name: str, prefix: str):
        """Odtwarza dźwięk wszystkim w danym pokoju."""
        sound_src = self._get_random_sound_file(prefix)
        if not sound_src:
            return

        payload = {"type": "PLAY_SOUND", "src": sound_src}
        room = self.rooms.get(room_name)
        if room:
            for ws in list(room.players_data):
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass