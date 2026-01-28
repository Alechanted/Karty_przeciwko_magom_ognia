import logging
import json # <--- DODAJ IMPORT JSON
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response # <--- DODAJ RESPONSE
from fastapi.staticfiles import StaticFiles

from room_manager import RoomManager
from enums import Phase
from locales import TEXTS # <--- IMPORT TEKSTÓW

# --- KONFIGURACJA LOGOWANIA ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("CAH_Main")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

room_manager = RoomManager()


@app.get("/")
async def get():
    with open("static/index.html", 'r', encoding='utf-8') as f:
        return HTMLResponse(f.read())

@app.get("/locales.js")
async def get_locales():
    # Zamienia słownik Python na obiekt JS: const TEXTS = { ... };
    js_content = f"const TEXTS = {json.dumps(TEXTS)};"
    return Response(content=js_content, media_type="application/javascript")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await room_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get('type')

            # --- FAZA 1: LOGOWANIE I POKOJE ---
            if mtype == 'SET_NICK':
                nick = data.get('nickname')
                if nick:
                    room_manager.active_connections[websocket] = nick
                    await websocket.send_json({"type": "NICK_OK"})
                    await room_manager.send_room_list(websocket)

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
                else:
                    await websocket.send_json({"type": "ERROR", "message": "Pokój o tej nazwie już istnieje!"})

            elif mtype == 'JOIN_ROOM':
                res = await room_manager.join_room(websocket, data['name'], data.get('password'))
                if res == "OK":
                    await websocket.send_json({"type": "JOIN_ROOM_OK", "room": data['name']})
                    await room_manager.broadcast_room_state(data['name'])
                else:
                    await websocket.send_json({"type": "ERROR", "message": res})

            # --- FAZA 2: ROZGRYWKA (wymaga bycia w pokoju) ---
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
                        if room.pick_winner(data['index']):
                            for ws in room.players_data:
                                await ws.send_json({"type": "CHAT", "author": "SYSTEM",
                                                    "message": f"Wygrywa: {room.winning_submission_index}"})
                            await room_manager.broadcast_room_state(room_name)

                elif mtype == 'PLAYER_READY':
                    if room.phase == Phase.SUMMARY:
                        if await room.mark_player_ready(websocket):
                            pass
                        await room_manager.broadcast_room_state(room_name)

                elif mtype == 'LEAVE_ROOM':
                    room_manager.disconnect(websocket)
                    room_manager.active_connections[websocket] = room.players_data[websocket]['nick']
                    await websocket.send_json({"type": "LEFT_ROOM"})
                    await room_manager.send_room_list(websocket)

    except WebSocketDisconnect:
        nick, r_name = room_manager.disconnect(websocket)
        if r_name and r_name in room_manager.rooms:
            await room_manager.broadcast_room_state(r_name)