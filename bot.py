import asyncio
import websockets
import json
import random
import logging
import time


class GameBot:
    def __init__(self, nickname, server_url):
        self.nickname = nickname
        self.server_url = server_url
        self.ws = None
        self.current_room = None
        self.latest_state = None
        self.room_search_task = None
        self.game_loop_task = None
        self.is_acting = False

        self.next_search_timestamp = 0

        self.logger = logging.getLogger(f"Bot_{nickname}")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(f"%(asctime)s [{self.nickname}] %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        self.logger.handlers = []
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    async def connect(self):
        await asyncio.sleep(random.uniform(1.0, 5.0))

        while True:
            try:
                self.logger.info(f"Łączenie z {self.server_url}...")
                async with websockets.connect(self.server_url) as websocket:
                    self.ws = websocket
                    self.current_room = None
                    self.latest_state = None
                    self.is_acting = False
                    self.logger.info("Połączono!")

                    await self.send_json({"type": "SET_NICK", "nickname": self.nickname})

                    self.room_search_task = asyncio.create_task(self.loop_search_rooms())
                    self.game_loop_task = asyncio.create_task(self.game_logic_loop())

                    async for message in websocket:
                        await self.handle_message(message)

            except (websockets.ConnectionClosed, ConnectionRefusedError):
                self.logger.warning("Brak połączenia. Ponawiam za 5s...")
            except Exception as e:
                self.logger.error(f"Krytyczny błąd: {e}")

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

            if mtype == 'ROOM_LIST':
                if not self.current_room and time.time() > self.next_search_timestamp:
                    await self.try_join_room(data.get('rooms', []))

            elif mtype == 'JOIN_ROOM_OK':
                self.current_room = data.get('room')
                self.logger.info(f"Dołączono do pokoju '{self.current_room}'")

            elif mtype == 'GAME_UPDATE':
                self.latest_state = data

            elif mtype == 'LEFT_ROOM':
                cooldown = 60.0 + random.uniform(0, 5.0)
                self.next_search_timestamp = time.time() + cooldown

                self.logger.info(f"Opuszczono pokój. Odpoczywam {cooldown:.1f}s zanim poszukam nowego...")
                self.current_room = None
                self.latest_state = None

            elif mtype == 'ERROR':
                if "FULL" in str(data.get('message')) or "NO_ROOM" in str(data.get('message')):
                    self.current_room = None

        except Exception:
            pass

    async def loop_search_rooms(self):
        while True:
            now = time.time()
            if self.ws and not self.current_room:
                if now > self.next_search_timestamp:
                    await self.send_json({"type": "GET_ROOMS"})
                else:
                    pass

            await asyncio.sleep(3.0)

    async def try_join_room(self, rooms):
        available = [r for r in rooms if not r['has_password'] and r['players'] < r['max']]

        if available:
            target = random.choice(available)
            self.logger.info(f"Próba wejścia do: {target['name']}")
            await self.send_json({"type": "JOIN_ROOM", "name": target['name'], "password": ""})

    async def game_logic_loop(self):
        while True:
            await asyncio.sleep(1.0)
            if not self.latest_state or self.is_acting: continue

            try:
                state = self.latest_state
                phase = state.get('phase')
                is_czar = state.get('is_czar')
                am_i_ready = state.get('am_i_ready')

                if phase == "GAME_OVER":
                    self.is_acting = True
                    try:
                        winner = state.get('winner', '???')
                        delay = random.uniform(5, 12)
                        self.logger.info(f"Koniec gry! Wygrał {winner}. Wychodzę za {delay:.1f}s")
                        await asyncio.sleep(delay)
                        await self.send_json({"type": "LEAVE_ROOM"})
                    finally:
                        self.is_acting = False
                    continue

                if phase == "SUMMARY" and not am_i_ready:
                    self.is_acting = True
                    try:
                        await asyncio.sleep(random.uniform(2, 6))
                        if self.latest_state.get('phase') == "SUMMARY":
                            await self.send_json({"type": "PLAYER_READY"})
                            self.logger.info("Ready!")
                    finally:
                        self.is_acting = False
                    continue

                if phase == "JUDGING" and is_czar:
                    subs = state.get('submissions', [])
                    if subs and not state.get('winner'):
                        self.is_acting = True
                        try:
                            await asyncio.sleep(random.uniform(3, 8))
                            fresh_subs = self.latest_state.get('submissions', [])
                            if fresh_subs:
                                choice = random.choice(fresh_subs)
                                await self.send_json({"type": "PICK_WINNER", "index": choice['id']})
                                self.logger.info(f"Wybrano ID: {choice['id']}")
                        finally:
                            self.is_acting = False
                        continue

                if phase == "SELECTING" and not is_czar:
                    black_card = state.get('black_card')
                    if not state.get('has_submitted') and black_card:
                        self.is_acting = True
                        try:
                            pick = black_card.get('pick', 1)
                            hand = state.get('hand', [])
                            if len(hand) >= pick:
                                await asyncio.sleep(random.uniform(2, 9))
                                fresh_hand = self.latest_state.get('hand', [])
                                if len(fresh_hand) >= pick:
                                    chosen = random.sample(fresh_hand, pick)
                                    ids = [c['id'] for c in chosen]
                                    await self.send_json({"type": "SUBMIT_CARDS", "cards": ids})
                                    self.logger.info("Wysłano karty")
                        finally:
                            self.is_acting = False
                        continue

            except Exception as e:
                self.logger.error(f"Logic error: {e}")
                self.is_acting = False


def start_bot_process(nickname, host, port):
    url = f"ws://{host}:{port}/ws"
    bot = GameBot(nickname, url)
    try:
        asyncio.run(bot.connect())
    except KeyboardInterrupt:
        pass
