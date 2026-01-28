import re
import uuid
from typing import List


class WhiteCard:
    def __init__(self, raw_line: str):
        parts = [p.strip() for p in raw_line.strip().split('|')]
        base_word = parts[0] if parts else "???"
        self.forms = parts if len(parts) >= 7 else [base_word] * 7
        self.id = str(uuid.uuid4())
        self.text = self.forms[0]  # Dla łatwego dostępu

    def get_nominative(self) -> str:
        return self.forms[0]

    def get_form_by_tag(self, tag: str) -> str:
        mapping = {'<M>': 0, '<D>': 1, '<C>': 2, '<B>': 3, '<N>': 4, '<MSC>': 5, '<W>': 6}
        return self.forms[mapping.get(tag, 0)]


class BlackCard:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text.strip()
        self.tags = re.findall(r'<[A-Z]+>', self.raw_text)
        self.pick_count = max(1, len(self.tags))
        self.id = str(uuid.uuid4())

    def get_display_text(self) -> str:
        return re.sub(r'<[A-Z]+>', '__________', self.raw_text)

    def fill_blanks(self, white_cards: List[WhiteCard]) -> str:
        text = self.raw_text
        for i, tag in enumerate(self.tags):
            if i < len(white_cards):
                text = text.replace(tag, f"<b>{white_cards[i].get_form_by_tag(tag)}</b>", 1)
        if len(self.tags) == 0 and white_cards:
            text += f" <b>{white_cards[0].get_nominative()}</b>"
        return re.sub(r'<[A-Z]+>', '____', text)