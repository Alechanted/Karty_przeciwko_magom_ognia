import os
import glob
import logging
from typing import Dict, Optional
from fastapi import WebSocket

from game_engine import GameEngine
from enums import Phase
from locales import TEXTS

logger = logging.getLogger(__name__)


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, GameEngine] = {}
        self.player_room_map: Dict[WebSocket, str] = {}
        self.active_connections: Dict[WebSocket, Optional[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = None

#zmiana pisana na kolanie, nie mam dostępu do moich plików i IDE, klepię w chujowniku ms windows
    async def disconnect(self, websocket: WebSocket):
        nick = self.active_connections.pop(websocket, None)
        room_name = self.player_room_map.pop(websocket, None)
        room_removed = False

        if room_name and room_name in self.rooms:
            room = self.rooms[room_name]
            room.remove_player(websocket)
            if not room.players_data:
                logger.info(f"Pokój '{room_name}' jest pusty. Usuwanie.")
                del self.rooms[room_name]
                room_removed = True
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
                "max": room.settings['max_players'],
                "has_password": bool(room.settings.get('password'))
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
        players_list = []
        for ws, nick in self.active_connections.items():
            if not nick: continue
            players_list.append({
                'nick': nick,
                'room': self.player_room_map.get(ws)
            })

        payload = {"type": "LOBBY_PLAYERS", "players": players_list}

        for ws, nick in list(self.active_connections.items()):
            try:
                if self.player_room_map.get(ws) is None:
                    await ws.send_json(payload)
            except Exception:
                pass

    def create_room(self, name, password, settings):
        if name in self.rooms: return False
        final_settings = {
            "password": password,
            "max_players": int(settings.get('max_players', 8)),
            "hand_size": int(settings.get('hand_size', 10)),
            "win_score": int(settings.get('win_score', 5)),
            "timeout": int(settings.get('timeout', 60)) if settings.get('timeout') != 'inf' else 0,
            "decks": settings.get('decks', [])
        }

        engine = GameEngine(name, final_settings)
        engine.broadcast_callback = self.broadcast_room_state

        self.rooms[name] = engine
        return True

    async def join_room(self, websocket, room_name, password):
        room = self.rooms.get(room_name)
        if not room: return TEXTS["ERR_NO_ROOM"]

        if room.settings.get('password') and room.settings['password'] != password:
            return TEXTS["ERR_WRONG_PASS"]

        if len(room.players_data) >= room.settings['max_players']:
            return TEXTS["ERR_ROOM_FULL"]

        nick = self.active_connections[websocket]
        self.player_room_map[websocket] = room_name
        room.add_player(websocket, nick)
        return "OK"

    async def send_room_list(self, websocket):
        rooms_list = [{
            "name": name,
            "players": len(engine.players_data),
            "max": engine.settings['max_players'],
            "has_password": bool(engine.settings.get('password'))
        } for name, engine in self.rooms.items()]

        players_list = [{
            "nick": nick,
            "room": self.player_room_map.get(ws)
        } for ws, nick in self.active_connections.items() if nick]

        await websocket.send_json({"type": "ROOM_LIST", "rooms": rooms_list, "players": players_list})

    async def broadcast_room_list(self):
        # Full room list is intended only for lobby clients.
        rooms_list = [{
            "name": name,
            "players": len(engine.players_data),
            "max": engine.settings['max_players'],
            "has_password": bool(engine.settings.get('password'))
        } for name, engine in self.rooms.items()]

        players_list = [{
            "nick": nick,
            "room": self.player_room_map.get(ws)
        } for ws, nick in self.active_connections.items() if nick]

        for ws in list(self.active_connections.keys()):
            try:
                if self.player_room_map.get(ws) is None:
                    await ws.send_json({"type": "ROOM_LIST", "rooms": rooms_list, "players": players_list})
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
                hand = room.players_data.get(ws, {}).get('hand', [])
                hand_data = [{"id": c.id, "text": c.get_nominative()} for c in hand]

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
                    "room_name": room_name
                })
            except Exception:

                pass
