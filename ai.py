from ollama import AsyncClient
import json

class Ai:
    select_winner_template = """
        Jesteś graczem w grze karcianej, która polega na wytypowaniu najzabawniejszej kombinacji karty czarnej z propozycjami graczy na kartach białych.
        Podstawiasz tekst z białej karty (lub kart) w wolne pole na karcie czarnej uzyskując kombinację.
        Teraz twoja kolej, żeby wybierać zwycięzcę. Skomentuj ironicznie wybrane karty i wybierz najśmiesznieją.
        Odpowiedz w json o następującej strukturze:
        {{ winner: <id zwycięzcy>, comment: <twój komentarz> }}

        Oto czarna karta:
        {0}

        Oto karty białe:
        {1}
        """
    
    select_white_card_template = """
        Jesteś graczem w grze karcianej, która polega na wytypowaniu najzabawniejszej kombinacji karty czarnej z propozycjami graczy na kartach białych.
        Podstawiasz tekst z białej karty (lub kart) w wolne pole na karcie czarnej uzyskując kombinację.
        Teraz twoja kolej, żeby rzucić białą kartę. Dobierz najlepsze twoim zdaniem karty białe i rzuć śmiesznym komentarzem na temat karty czarnej.
        W swoim zabawnym komentarzu NIE UJAWNIAJ, ani nie nawiązuj do białych kart, które wybierasz. Komentarz ma się skupiać wyłącznie na karcie czarnej.
        Czarna karta wskazuje, ile kart musisz rzucić.
        Odpowiedz w json o następującej strukturze:
        {{ cards: [<obiekty wybranych kart białych>], comment: <twój komentarz> }}

        Oto czarna karta:
        {0}

        Oto twoje karty białe:
        {1}
    """

    def __init__(self):
        self.client = AsyncClient(host = 'http://localhost:11434', )
        self.is_busy = False

    async def send_message(self, message):
        return await self.client.chat(model='SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M', messages=[message], format='json')

    async def test(self):
        message = {'role': 'user', 'content': 'Co jest fajniejsze, skarpetki, czy ser?'}
        response = await self.send_message(message)
        print(response.message.content)

    async def pick_winner(self, state):
        if self.is_busy:
            return

        self.is_busy = True
        black_card = state.get('black_card')
        submissions = state.get('submissions')

        message = {'role': 'user', 'content': self.select_winner_template.format(json.dumps(black_card), json.dumps(submissions)) }
        response = await self.send_message(message)
        result = json.loads(response.message.content)

        winner = result.get('winner')
        comment = result.get('comment')
        self.is_busy = False

        return { "id": winner if winner else 0, "message": comment }
    
    async def select_white_card(self, state):
        if self.is_busy:
            return
        
        self.is_busy = True
        hand = state.get('hand')
        black_card = state.get('black_card')
        
        message = {'role': 'user', 'content': self.select_white_card_template.format(json.dumps(black_card), json.dumps(hand)) }
        response = await self.send_message(message)
        result = json.loads(response.message.content)

        comment = result.get('comment') 
        cards = result.get('cards')
        self.is_busy = False

        return { "cards": cards if cards else hand[0]['ids'], "message": comment }
