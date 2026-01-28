import os
import random
import logging
import asyncio
from typing import List, Dict, Tuple, Set

from models import WhiteCard, BlackCard
from enums import Phase
from locales import TEXTS

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(self, room_name, settings):
        self.room_name = room_name
        self.settings = settings  # dict: max_players, hand_size, win_score, timeout, decks

        self.white_deck_master = []
        self.black_deck_master = []

        # 1. Ładowanie Masterów
        self._load_selected_decks(settings.get('decks', []))

        self.game_started = False
        self.phase = Phase.LOBBY
        self.current_black_card = None
        self.czar_socket = None
        self.winner_nick = None

        # 2. Inicjalizacja pustych talii roboczych
        self.white_deck = []
        self.black_deck = []

        self.players_data = {}  # ws -> {nick, hand, score}
        self.round_submissions = {}
        self.judging_order = []
        self.ready_players = set()
        self.winning_submission_index = -1

        self._timeout_task = None
        self.broadcast_callback = None

        # 3. Kopiowanie kart z Master do Active (pierwsze tasowanie)
        self.reset_game()

    def _load_selected_decks(self, selected_decks):
        for deck_name in selected_decks:
            w_path = f"decks/{deck_name}.white"
            b_path = f"decks/{deck_name}.black"
            if os.path.exists(w_path): self.white_deck_master.extend(self._load_file(w_path, WhiteCard))
            if os.path.exists(b_path): self.black_deck_master.extend(self._load_file(b_path, BlackCard))

        logger.info(
            f"Pokój '{self.room_name}': Załadowano {len(self.white_deck_master)} w, {len(self.black_deck_master)} b.")

    @staticmethod
    def _load_file(path, cls):
        items = []
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.strip(): items.append(cls(line))
        except Exception:
            pass
        return items

    def reset_game(self):
        self.game_started = False
        self.phase = Phase.LOBBY
        self.current_black_card = None
        self.czar_socket = None
        self.winner_nick = None

        # Kopiowanie i tasowanie
        self.white_deck = self.white_deck_master.copy()
        self.black_deck = self.black_deck_master.copy()
        random.shuffle(self.white_deck)
        random.shuffle(self.black_deck)

        for p in self.players_data.values():
            p['score'] = 0
            p['hand'] = []

        self.round_submissions = {}
        self.judging_order = []
        self.ready_players = set()
        self._cancel_timeout()

    def add_player(self, ws, nick):
        self.players_data[ws] = {'nick': nick, 'hand': [], 'score': 0}

    def remove_player(self, ws):
        if ws in self.players_data:
            del self.players_data[ws]
            self.ready_players.discard(ws)
            if ws == self.czar_socket: self.czar_socket = None
            if ws in self.round_submissions: del self.round_submissions[ws]

    async def start_round(self):
        self._cancel_timeout()

        # --- FIX: AUTO-RESHUFFLE ---
        # Jeśli talia robocza jest pusta, ale Master ma karty -> przetasuj od nowa.
        # To naprawia błąd przy starcie ORAZ pozwala na nieskończoną grę.
        if not self.black_deck:
            if self.black_deck_master:
                logger.info(f"Pokój '{self.room_name}': Talia czarnych pusta/niezainicjowana. Tasowanie z Mastera...")
                self.black_deck = self.black_deck_master.copy()
                random.shuffle(self.black_deck)
            else:
                # Tylko jeśli Master też pusty, kończymy grę
                logger.error(f"Pokój '{self.room_name}': Brak czarnych kart nawet w Masterze!")
                self.phase = Phase.GAME_OVER
                self.winner_nick = TEXTS["MSG_DECK_EMPTY"]
                return

        if not self.white_deck:
            if self.white_deck_master:
                logger.info(f"Pokój '{self.room_name}': Talia białych pusta. Tasowanie z Mastera...")
                self.white_deck = self.white_deck_master.copy()
                random.shuffle(self.white_deck)
        # ---------------------------

        self.current_black_card = self.black_deck.pop()
        self.phase = Phase.SELECTING
        self.round_submissions = {}
        self.judging_order = []
        self.ready_players = set()

        hand_limit = int(self.settings.get('hand_size', 10))

        for ws, p_data in self.players_data.items():
            while len(p_data['hand']) < hand_limit:
                if not self.white_deck:
                    # Auto-reshuffle dla białych w trakcie rozdawania
                    if self.white_deck_master:
                        self.white_deck = self.white_deck_master.copy()
                        random.shuffle(self.white_deck)
                    else:
                        break
                p_data['hand'].append(self.white_deck.pop())

        active = list(self.players_data.keys())
        if not active: return

        if not self.czar_socket or self.czar_socket not in active:
            self.czar_socket = random.choice(active)
        else:
            try:
                curr_idx = active.index(self.czar_socket)
                self.czar_socket = active[(curr_idx + 1) % len(active)]
            except ValueError:
                self.czar_socket = random.choice(active)

        timeout_sec = self.settings.get('timeout')
        if timeout_sec and timeout_sec > 0:
            self._timeout_task = asyncio.create_task(self._round_timeout_logic(timeout_sec))

    async def _round_timeout_logic(self, seconds):
        try:
            await asyncio.sleep(seconds)
            if self.phase == Phase.SELECTING:
                logger.info(f"Pokój '{self.room_name}': {TEXTS['MSG_TIMEOUT']}")
                await self._force_resolve_round()
        except asyncio.CancelledError:
            pass

    async def _force_resolve_round(self):
        pick = self.current_black_card.pick_count
        updated = False

        for ws, p_data in self.players_data.items():
            if ws == self.czar_socket: continue
            if ws not in self.round_submissions:
                if len(p_data['hand']) >= pick:
                    random_pick = random.sample(p_data['hand'], pick)
                    # Używamy internal logic, żeby nie duplikować kodu
                    self.submit_cards(ws, [c.id for c in random_pick])
                    updated = True

        if self.broadcast_callback:
            await self.broadcast_callback(self.room_name)

    def _cancel_timeout(self):
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None

    def submit_cards(self, ws, card_ids):
        player = self.players_data.get(ws)
        if not player or ws == self.czar_socket: return False

        selected = [c for c in player['hand'] if c.id in card_ids]
        if len(selected) != self.current_black_card.pick_count: return False

        self.round_submissions[ws] = selected
        for c in selected: player['hand'].remove(c)

        needed = 0
        for s, p_data in self.players_data.items():
            if s == self.czar_socket: continue
            if len(p_data['hand']) > 0 or s in self.round_submissions: needed += 1

        if len(self.round_submissions) >= needed:
            self._cancel_timeout()
            self.phase = Phase.JUDGING
            lst = list(self.round_submissions.items())
            random.shuffle(lst)
            self.judging_order = lst
            return True
        return False

    def pick_winner(self, index):
        try:
            index = int(index)
            winner_ws, _ = self.judging_order[index]
            self.winning_submission_index = index

            winner_nick = TEXTS["MSG_GHOST"]
            if winner_ws in self.players_data:
                self.players_data[winner_ws]['score'] += 1
                winner_nick = self.players_data[winner_ws]['nick']

            win_score = int(self.settings.get('win_score', 5))
            if self.players_data.get(winner_ws, {}).get('score', 0) >= win_score:
                self.phase = Phase.GAME_OVER
                self.winner_nick = winner_nick
            else:
                self.phase = Phase.SUMMARY
            return winner_nick
        except:
            return None

    async def mark_player_ready(self, ws):
        if ws in self.players_data: self.ready_players.add(ws)

        relevant = [s for s, p in self.players_data.items() if len(p['hand']) > 0]
        if not relevant: relevant = list(self.players_data.keys())

        ready_rel = [s for s in self.ready_players if s in relevant]

        if len(ready_rel) == len(relevant) and len(relevant) > 0:
            await self.start_round()
            return True
        return False