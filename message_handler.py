from fastapi import WebSocket
from enums import Phase
from models import GameSettings
from room_manager import RoomManager

class MessageHandler:
    def __init__(self, room_manager: RoomManager, websocket: WebSocket):
        self.room_manager = room_manager
        self.websocket = websocket

    async def send_chat_message(self, message, nick = None):
        room = self._get_player_room()
        nick = nick if nick else self._get_player_nick()

        if room:
            await self._broadcast_to_room(room, {"type": "CHAT", "author": nick, "message": message})
        else:
            await self._broadcast_to_all({"type": "CHAT", "author": nick, "message": message, "scope": "LOBBY"})

    async def set_nick(self, nick: str):
        if nick:
            self.room_manager.active_connections[self.websocket] = nick

            await self.websocket.send_json({"type": "NICK_OK"})
            # Send full ROOM_LIST only to this new client in lobby
            await self.room_manager.send_room_list(self.websocket)
            # Notify lobby clients about updated player list
            await self.room_manager.broadcast_lobby_players()

    async def create_room(self, settings: GameSettings):
        owner_name = self._get_player_nick()
        success = self.room_manager.create_room(owner_name, settings)
        if success:
            await self.room_manager.broadcast_room_list()
            await self.join_room(settings.name, settings.password)
        else:
            await self._send_to_self({"type": "ERROR", "message": "Pokój o tej nazwie już istnieje!"})

    async def join_room(self, name, password):
        result = await self.room_manager.join_room(self.websocket, name, password)
        if result == "OK":
            await self._send_to_self({"type": "JOIN_ROOM_OK", "room": name})
            await self.room_manager.broadcast_room_state(name)
            # Update lobby clients with changed player count for this room
            await self.room_manager.broadcast_room_count(name)
            # Also update lobby's player list
            await self.room_manager.broadcast_lobby_players()
        else:
            await self._send_to_self({"type": "ERROR", "message": result})

    async def start_game(self):
        room = self._get_player_room()
        if room.game_started:
            await self._send_to_self({"type": "ERROR", "message": "ERR_GAME_ALREADY_STARTED"})
            return

        if not room.can_start_game(self._get_player_nick()):
            await self._send_to_self({"type": "ERROR", "message": "ERR_NOT_ALLOWED_TO_START"})
            return

        if len(room.players_data) < 2:
            await self._send_to_self({"type": "ERROR", "message": "ERR_MIN_PLAYERS"})
            return

        room.game_started = True
        await room.start_round()
        await self.room_manager.broadcast_room_state(room.room_name)

    async def submit_cards(self, cards):
        room = self._get_player_room()

        if room.phase == Phase.SELECTING and room.submit_cards(self.websocket, cards):
            await self.room_manager.broadcast_room_state(room.room_name)

    async def pick_winner(self, winner):
        room = self._get_player_room()
        if room.phase == Phase.JUDGING and self.websocket == room.czar_socket:
            winner_nick = room.pick_winner(winner)
            if winner_nick:
                await self.send_chat_message(f"Wygrywa: {winner_nick}", "SYSTEM")
                await self.room_manager.broadcast_room_state(room.room_name)

    async def set_ready(self):
        room = self._get_player_room()
        if room.phase == Phase.SUMMARY:
            await room.mark_player_ready(self.websocket)
            await self.room_manager.broadcast_room_state(room.room_name)

    #poprawka pisana na kolanie, nie mam tu dostępu do mojego ide i klepię w chujowniku ms windows
    async def leave_room(self):
        await self.room_manager.remove_player(self.websocket, remove_connection=False)
        await self._send_to_self({"type": "LEFT_ROOM"})

    def _get_player_nick(self):
        return self.room_manager.active_connections.get(self.websocket)
    
    def _get_player_room_name(self):
        return self.room_manager.player_room_map.get(self.websocket)

    def _get_player_room(self):
        return self._get_room(self._get_player_room_name())

    async def _broadcast_to_all(self, message):
        for ws in list(self.room_manager.active_connections.keys()):
            if self.room_manager.player_room_map.get(ws) is None:
                await self._send(ws, message)

    async def _broadcast_to_room(self, room, message):
        if room:
            for ws in list(room.players_data):
                await self._send(ws, message)

    async def _send_to_self(self, message):
        await self._send(self.websocket, message)

    async def _send(self, ws, message):
        try:
            await ws.send_json(message)
        except Exception:
            pass

    def _get_room(self, room_name):
        return self.room_manager.rooms.get(room_name)
