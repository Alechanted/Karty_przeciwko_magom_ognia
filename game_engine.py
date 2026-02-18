import os
import random
import logging
import asyncio

from models import GameSettings, WhiteCard, BlackCard
from enums import Phase
from locales import TEXTS

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(self, owner_name: str, settings: GameSettings):
        self.owner_name = owner_name
        self.room_name = settings.name
        self.settings = settings  # dict: max_players, hand_size, win_score, timeout, decks

        self.white_deck_master = []
        self.black_deck_master = []

        # 1. Ładowanie Masterów
        self._load_selected_decks(settings.decks)

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
            json_path = f"decks/{deck_name}.json"
            w_path = f"decks/{deck_name}.white"
            b_path = f"decks/{deck_name}.black"
            if os.path.exists(json_path):
                # load from unified JSON
                w, b = self._load_json_deck(json_path)
                self.white_deck_master.extend(w)
                self.black_deck_master.extend(b)
            else:
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

    def _load_json_deck(self, path):
        white_items = []
        black_items = []
        try:
            import json
            from models import WhiteCard, BlackCard
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cards = data.get('cards', {})
            for w in cards.get('white', []):
                try:
                    white_items.append(WhiteCard.from_json(w))
                except Exception:
                    # fallback: construct from joined forms
                    forms = w.get('forms')
                    if isinstance(forms, dict):
                        parts = [forms.get(k, '') for k in ["M","D","C","B","N","MSC","W"]]
                        white_items.append(WhiteCard('|'.join(parts)))
            for b in cards.get('black', []):
                try:
                    black_items.append(BlackCard.from_json(b))
                except Exception:
                    tmpl = b.get('template') or b.get('raw_text') or ''
                    black_items.append(BlackCard(tmpl))
        except Exception:
            pass
        return white_items, black_items

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
        """ Usuwa gracza z pokoju. Zwraca True jeśli pokój jest teraz pusty i powinien zostać usunięty."""
        if ws in self.players_data:
            p = self.players_data[ws]
            del self.players_data[ws]
            self.ready_players.discard(ws)
            
            if p['nick'] == self.owner_name: self.owner_name = None
            if ws == self.czar_socket: self.czar_socket = None
            if ws in self.round_submissions: del self.round_submissions[ws]

        return len(self.players_data) == 0

    def is_password_correct(self, password: str):
        return not self.settings.has_password() or self.settings.password == password

    def can_start_game(self, nick: str):
        return self.settings.anyone_can_start or self.owner_name is None or self.owner_name == nick

    # FIX: Gra duplikuje karty
    # Gra miała nieprzemyślane zabezpieczenie przed przedwczesnym zakończeniem gry z powodu brak kart
    # Usunąłem zabezpieczenie i dodałem kończenie rundy przy braku kart na ręce gracza
    # https://github.com/Alechanted/Karty_przeciwko_magom_ognia/issues/1#issue-3869636354
    async def start_round(self):
        self._cancel_timeout()

        if not self.black_deck:
            logger.info(f"Pokój '{self.room_name}': Brak czarnych kart. Koniec gry.")
            self.phase = Phase.GAME_OVER
            self.winner_nick = TEXTS["MSG_DECK_EMPTY"]
            return

        # Dobieramy czarną kartę
        self.current_black_card = self.black_deck.pop()
        self.phase = Phase.SELECTING
        self.round_submissions = {}
        self.judging_order = []
        self.ready_players = set()

        hand_limit = int(self.settings.hand_size)

        for ws, p_data in self.players_data.items():
            while len(p_data['hand']) < hand_limit and self.white_deck:
                p_data['hand'].append(self.white_deck.pop())

        active = list(self.players_data.keys())
        if not active:
            return

        if not self.czar_socket or self.czar_socket not in active:
            self.czar_socket = random.choice(active)
        else:
            try:
                curr_idx = active.index(self.czar_socket)
                self.czar_socket = active[(curr_idx + 1) % len(active)]
            except ValueError:
                self.czar_socket = random.choice(active)

        timeout_sec = self.settings.timeout
        if timeout_sec and timeout_sec > 0:
            self._timeout_task = asyncio.create_task(
                self._round_timeout_logic(timeout_sec)
            )

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

        id_map = {c.id: c for c in player['hand']}
        selected = [id_map[cid] for cid in card_ids if cid in id_map]
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

            win_score = int(self.settings.win_score)
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