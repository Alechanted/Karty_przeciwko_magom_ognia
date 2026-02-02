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

    @classmethod
    def from_json(cls, data: dict):
        # data expected to have 'forms' dict or list
        forms_data = data.get('forms')
        if isinstance(forms_data, dict):
            order = ['M', 'D', 'C', 'B', 'N', 'MSC', 'W']
            parts = [forms_data.get(k, '') for k in order]
        elif isinstance(forms_data, list):
            parts = forms_data
        else:
            parts = [''] * 7
        obj = cls('|'.join(parts))
        # preserve id if present
        if data.get('id'):
            obj.id = data['id']
        # override forms if provided explicitly
        obj.forms = parts
        obj.text = obj.forms[0] if obj.forms else ''
        return obj


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

    @classmethod
    def from_json(cls, data: dict):
        # data expected to have 'template' and optionally 'slots'
        raw = data.get('template') or data.get('raw_text') or ''
        obj = cls(raw)
        if data.get('id'):
            obj.id = data['id']
        # if slots provided, ensure tags reflect them
        slots = data.get('slots')
        if isinstance(slots, list) and slots:
            obj.tags = [f"<{s}>" for s in slots]
            obj.pick_count = max(1, len(obj.tags))
        return obj