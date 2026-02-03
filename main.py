import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from room_manager import RoomManager
import asyncio
import run as run_cfg
from enums import Phase
from locales import TEXTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("CAH_Main")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/decks", StaticFiles(directory="decks"), name="decks")

room_manager = RoomManager()


async def _lobby_broadcaster_loop():
    # Periodically broadcast room/player list to all connected clients
    interval = getattr(run_cfg, 'LOBBY_REFRESH', 3)
    while True:
        try:
            await room_manager.broadcast_room_list()
        except Exception:
            pass
        await asyncio.sleep(interval)


@app.on_event("startup")
async def _startup_tasks():
    # No periodic lobby broadcaster: full ROOM_LIST is sent only on room create/remove.
    pass

@app.get("/")
async def get():
    with open("static/index.html", 'r', encoding='utf-8') as f:
        return HTMLResponse(f.read())

@app.get("/locales.js")
async def get_locales():
    js_content = f"const TEXTS = {json.dumps(TEXTS)};"
    return Response(content=js_content, media_type="application/javascript")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await room_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get('type')

            if mtype == 'SET_NICK':
                nick = data.get('nickname')
                if nick:
                    room_manager.active_connections[websocket] = nick
                    await websocket.send_json({"type": "NICK_OK"})
                    # Send full ROOM_LIST only to this new client in lobby
                    await room_manager.send_room_list(websocket)
                    # Notify lobby clients about updated player list
                    await room_manager.broadcast_lobby_players()

            if mtype == 'CHAT_MSG':
                nick = room_manager.active_connections.get(websocket)
                # If player is in a room -> send to that room, else broadcast to lobby clients only
                room_name_for_msg = room_manager.player_room_map.get(websocket)
                if room_name_for_msg:
                    room = room_manager.rooms.get(room_name_for_msg)
                    if room:
                        for ws in room.players_data:
                            await ws.send_json({"type": "CHAT", "author": nick, "message": data['message']})
                else:
                    # lobby chat: send only to clients not in a room
                    for ws, _ in room_manager.active_connections.items():
                        try:
                            if room_manager.player_room_map.get(ws) is None:
                                await ws.send_json({"type": "CHAT", "author": nick, "message": data['message'], "scope": "LOBBY"})
                        except Exception:
                            pass
                continue

            elif mtype == 'GET_ROOMS':
                await room_manager.send_room_list(websocket)

            elif mtype == 'GET_DECKS':
                decks = room_manager.get_deck_list()
                await websocket.send_json({"type": "DECK_LIST", "decks": decks})

            elif mtype == 'CREATE_ROOM':
                success = room_manager.create_room(data['name'], data['password'], data['settings'])
                if success:
                    res = await room_manager.join_room(websocket, data['name'], data['password'])
                    await websocket.send_json({"type": "JOIN_ROOM_OK", "room": data['name']})
                    await room_manager.broadcast_room_state(data['name'])
                    # New room created: notify lobby clients with full list
                    await room_manager.broadcast_room_list()
                else:
                    await websocket.send_json({"type": "ERROR", "message": "Pokój o tej nazwie już istnieje!"})

            elif mtype == 'JOIN_ROOM':
                res = await room_manager.join_room(websocket, data['name'], data.get('password'))
                if res == "OK":
                    await websocket.send_json({"type": "JOIN_ROOM_OK", "room": data['name']})
                    await room_manager.broadcast_room_state(data['name'])
                    # Update lobby clients with changed player count for this room
                    await room_manager.broadcast_room_count(data['name'])
                    # Also update lobby's player list
                    await room_manager.broadcast_lobby_players()
                else:
                    await websocket.send_json({"type": "ERROR", "message": res})
            else:
                room_name = room_manager.player_room_map.get(websocket)
                if not room_name: continue
                room = room_manager.rooms[room_name]

                if mtype == 'CHAT_MSG':
                    nick = room_manager.active_connections[websocket]
                    for ws in room.players_data:
                        await ws.send_json({"type": "CHAT", "author": nick, "message": data['message']})

                elif mtype == 'START_GAME':
                    if len(room.players_data) < 2:
                        await websocket.send_json({"type": "ERROR", "message": "ERR_MIN_PLAYERS"})
                    elif not room.game_started:
                        room.game_started = True
                        await room.start_round()
                        await room_manager.broadcast_room_state(room_name)

                elif mtype == 'SUBMIT_CARDS':
                    if room.phase == Phase.SELECTING:
                        if room.submit_cards(websocket, data['cards']):
                            await room_manager.broadcast_room_state(room_name)

                elif mtype == 'PICK_WINNER':
                    if room.phase == Phase.JUDGING and websocket == room.czar_socket:
                        winner_nick = room.pick_winner(data['index'])
                        if winner_nick:
                            for ws in room.players_data:
                                await ws.send_json({"type": "CHAT", "author": "SYSTEM",
                                                    "message": f"Wygrywa: {winner_nick}"})
                            await room_manager.broadcast_room_state(room_name)
                            # Do not broadcast full list here; lobby unaffected by picking winner

                elif mtype == 'PLAYER_READY':
                    if room.phase == Phase.SUMMARY:
                        if await room.mark_player_ready(websocket):
                            pass
                        await room_manager.broadcast_room_state(room_name)

                elif mtype == 'LEAVE_ROOM':
                    nick, room_name, room_removed = room_manager.disconnect(websocket)
                    await websocket.send_json({"type": "LEFT_ROOM"})
                    # Send full room list to this client (now in lobby)
                    await room_manager.send_room_list(websocket)
                    # Notify lobby: if room was removed, send full list; otherwise send single-room update
                    if room_removed:
                        await room_manager.broadcast_room_list()
                    elif room_name and room_name in room_manager.rooms:
                        await room_manager.broadcast_room_count(room_name)
                    # Update lobby players list
                    await room_manager.broadcast_lobby_players()

    except WebSocketDisconnect:
        nick, r_name, room_removed = room_manager.disconnect(websocket)
        if r_name and r_name in room_manager.rooms:
            await room_manager.broadcast_room_state(r_name)
        # Notify lobby: only full list when a room was removed, otherwise update single room count
        if room_removed:
            await room_manager.broadcast_room_list()
        elif r_name and r_name in room_manager.rooms:
            await room_manager.broadcast_room_count(r_name)
        # Update lobby players list
        await room_manager.broadcast_lobby_players()
