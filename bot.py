import asyncio
import websockets
import json
import random
import logging

# --- KONFIGURACJA ---
SERVER_URL = "ws://83.168.90.152:2137/ws"
BOT_NICK = "Gomez"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GOMEZ] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("GomezBot")


class GomezBot:
    def __init__(self):
        self.ws = None
        self.current_room = None
        self.latest_state = None
        self.room_search_task = None
        self.game_loop_task = None
        self.is_acting = False
        self.last_debug_time = 0

    async def connect(self):
        while True:
            try:
                logger.info(f"Łączenie z {SERVER_URL}...")
                async with websockets.connect(SERVER_URL) as websocket:
                    self.ws = websocket
                    self.current_room = None
                    self.latest_state = None
                    self.is_acting = False
                    logger.info("Połączono!")

                    await self.send_json({"type": "SET_NICK", "nickname": BOT_NICK})

                    self.room_search_task = asyncio.create_task(self.loop_search_rooms())
                    self.game_loop_task = asyncio.create_task(self.game_logic_loop())

                    async for message in websocket:
                        await self.handle_message(message)

            except (websockets.ConnectionClosed, ConnectionRefusedError):
                logger.warning("Rozłączono! Ponawiam za 5s...")
            except Exception as e:
                logger.error(f"Krytyczny błąd: {e}")

            # Sprzątanie
            if self.room_search_task: self.room_search_task.cancel()
            if self.game_loop_task: self.game_loop_task.cancel()
            self.current_room = None
            await asyncio.sleep(5)

    async def send_json(self, data):
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
            except Exception:
                pass

    async def handle_message(self, message):
        try:
            data = json.loads(message)
            mtype = data.get('type')

            if mtype == 'NICK_OK':
                logger.info("Nick zaakceptowany.")

            elif mtype == 'ROOM_LIST':
                if not self.current_room:
                    await self.try_join_room(data.get('rooms', []))

            elif mtype == 'JOIN_ROOM_OK':
                self.current_room = data.get('room')
                logger.info(f"SUKCES: Dołączono do pokoju '{self.current_room}'")

            elif mtype == 'GAME_UPDATE':
                self.latest_state = data

            elif mtype == 'ERROR':
                logger.error(f"SERWER: {data.get('message')}")
                if "FULL" in str(data.get('message')) or "NO_ROOM" in str(data.get('message')):
                    self.current_room = None

        except Exception as e:
            logger.error(f"Błąd parsowania: {e}")

    async def loop_search_rooms(self):
        while True:
            if self.ws and not self.current_room:
                await self.send_json({"type": "GET_ROOMS"})
            await asyncio.sleep(2.0)

    async def try_join_room(self, rooms):
        for room in rooms:
            if not room['has_password'] and room['players'] < room['max']:
                logger.info(f"Próba wejścia do: {room['name']}")
                await self.send_json({"type": "JOIN_ROOM", "name": room['name'], "password": ""})
                return

    async def game_logic_loop(self):
        while True:
            await asyncio.sleep(1.0)  # Taktowanie bota, warznewchuj

            if not self.latest_state or self.is_acting:
                continue

            try:
                state = self.latest_state
                phase = state.get('phase')
                is_czar = state.get('is_czar')
                am_i_ready = state.get('am_i_ready')

                if phase == "SUMMARY" and not am_i_ready:
                    now = asyncio.get_event_loop().time()
                    if now - self.last_debug_time > 5:
                        logger.info(
                            f"DEBUG SUMMARY: Czekam na kliknięcie Ready. Ready={am_i_ready}, Acting={self.is_acting}")
                        self.last_debug_time = now

                if phase == "SUMMARY" and not am_i_ready:
                    self.is_acting = True
                    try:
                        delay = random.uniform(2, 5)
                        logger.info(f"[SUMMARY] Koniec rundy. Klikam READY za {delay:.1f}s...")
                        await asyncio.sleep(delay)

                        curr_state = self.latest_state
                        if curr_state.get('phase') == "SUMMARY" and not curr_state.get('am_i_ready'):
                            await self.send_json({"type": "PLAYER_READY"})
                            logger.info("-> Wysłano PLAYER_READY")
                    finally:
                        self.is_acting = False
                    continue

                if phase == "JUDGING" and is_czar:
                    submissions = state.get('submissions', [])
                    # Sprawdź czy są zgłoszenia i czy nie ma jeszcze zwycięzcy
                    if submissions and not state.get('winner'):
                        self.is_acting = True
                        try:
                            delay = random.uniform(3, 8)
                            logger.info(
                                f"[JUDGING] Jestem Carem. Wybieram z {len(submissions)} kart za {delay:.1f}s...")
                            await asyncio.sleep(delay)

                            fresh_state = self.latest_state
                            fresh_subs = fresh_state.get('submissions', [])

                            if fresh_state.get('phase') == "JUDGING" and fresh_subs:
                                choice = random.choice(fresh_subs)
                                await self.send_json({"type": "PICK_WINNER", "index": choice['id']})
                                logger.info(f"-> Wybrano ID: {choice['id']}")
                        finally:
                            self.is_acting = False
                        continue

                if phase == "SELECTING" and not is_czar:
                    has_submitted = state.get('has_submitted')
                    black_card = state.get('black_card')

                    if not has_submitted and black_card:
                        self.is_acting = True
                        try:
                            pick_count = black_card.get('pick', 1)
                            hand = state.get('hand', [])

                            if len(hand) >= pick_count:
                                delay = random.uniform(2, 8)
                                logger.info(f"[SELECTING] Wybieram {pick_count} kart za {delay:.1f}s...")
                                await asyncio.sleep(delay)

                                fresh_state = self.latest_state
                                if fresh_state.get('phase') == "SELECTING" and not fresh_state.get('has_submitted'):
                                    curr_hand = fresh_state.get('hand', [])
                                    if len(curr_hand) >= pick_count:
                                        chosen = random.sample(curr_hand, pick_count)
                                        ids = [c['id'] for c in chosen]
                                        await self.send_json({"type": "SUBMIT_CARDS", "cards": ids})
                                        logger.info(f"-> Wysłano karty")
                            else:
                                logger.warning("Brak kart na ręce!")
                        finally:
                            self.is_acting = False
                        continue

            except Exception as e:
                logger.error(f"Błąd w logice: {e}")
                self.is_acting = False


if __name__ == "__main__":
    bot = GomezBot()
    try:
        asyncio.run(bot.connect())
    except KeyboardInterrupt:
        pass