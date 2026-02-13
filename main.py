import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from room_manager import RoomManager
from message_handler import MessageHandler
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
    handler = MessageHandler(room_manager, websocket)

    await room_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get('type')

            match message_type:
                case 'GET_ROOMS':
                    await room_manager.send_room_list(websocket)

                case 'GET_DECKS':
                    decks = room_manager.get_deck_list()
                    await websocket.send_json({"type": "DECK_LIST", "decks": decks})

                case 'SET_NICK':
                    await handler.set_nick(data.get('nickname'))

                case 'CHAT_MSG':
                    await handler.send_chat_message(data.get('message'))

                case 'CREATE_ROOM':
                    await handler.create_room(data['name'], data['password'], data['settings'])

                case 'JOIN_ROOM':
                    await handler.join_room(data['name'], data['password'])

                case 'START_GAME':
                    await handler.start_game()

                case 'SUBMIT_CARDS':
                    await handler.submit_cards(data['cards'])

                case 'PICK_WINNER':
                    await handler.pick_winner(data['index'])

                case 'PLAYER_READY':
                    await handler.set_ready()

                case 'LEAVE_ROOM':
                    await handler.leave_room()

    except WebSocketDisconnect:
        nick, r_name, room_removed = await room_manager.disconnect(websocket)
        if r_name and r_name in room_manager.rooms:
            await room_manager.broadcast_room_state(r_name)
        # Notify lobby: only full list when a room was removed, otherwise update single room count
        if room_removed:
            await room_manager.broadcast_room_list()
        elif r_name and r_name in room_manager.rooms:
            await room_manager.broadcast_room_count(r_name)
        # Update lobby players list
        await room_manager.broadcast_lobby_players()

