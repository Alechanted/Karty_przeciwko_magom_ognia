# Karty przeciwko magom ognia

Nieoficjalna, elektroniczna wersja gry typu *Cards Against Humanity*, napisana w **Pythonie (backend)** i **JavaScript (frontend)**, przystosowana do grania online z pięknymi mężczyznami.  
Projekt ma charakter **hobbystyczny / edukacyjny / szyderczo-złośliwy / metareligijny**.

https://tetriando.ch

https://discord.gg/nE3jskQCVg

---

## Spis treści
- [Wymagania](#wymagania)
- [Uruchamianie projektu](#uruchamianie-projektu)
- [Struktura repozytorium](#struktura-repozytorium)
- [Zasady pracy z Gitem](#zasady-pracy-z-gitem)
- [Decki – format plików](#decki--format-plików)
- [Wersjonowanie](#wersjonowanie)
- [Dobre praktyki](#dobre-praktyki)

---

## Wymagania

- Python 3.x
- fastapi
- Git
- (opcjonalnie) PyCharm / VS Code

---

## Uruchamianie projektu

1. Sklonuj repozytorium:
```bash
git clone https://github.com/Alechanted/Karty_przeciwko_magom_ognia.git
```
Wejdź do katalogu projektu:
```bash
cd Karty_przeciwko_magom_ognia
```
Uruchom backend (szczegóły mogą się zmieniać wraz z rozwojem projektu):
```bash
python run.py
```
lub:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 2137
```
---

## Struktura repozytorium
Przykładowa struktura (może ewoluować):

```text
/static
    editor.css
    editor.html
    editor.js
    game.js
    index.html    
    style.css 
/decks
    example.json
bot.py
enums.py
game_engine.py
locales.py
main.py
message_handler.py
models.py
README.md
room_manager.py
run.py
```
- static/ – *interfejs użytkownika (JS/HTML/CSS), w tym edytor decków*
- decks/ – *pliki z deckami w formacie JSON (bez logiki)*
- bot.py - *logika botów*
- enums.py – *enumy / stałe*
- game_engine.py – *silnik gry / logika rozgrywki*
- message_handler.py – *obsługa komunikacji / wiadomości*
- locales.py - *słownik, żeby dało się to konwertować, jakbyśmy chcieli jednak zrobić karty przeciwko forknife*
- main.py - *główny backend gry*
- models.py - *karteluszki*
- room_manager - *logika pokoi*
- run.py - *uruchamiacz*

### Branch główny

- master – *zawsze grywalna wersja gry*

- testing – *integracja zmian i testy*

### Branch robocze

- feature/* – *nowe funkcje*

- fix/* – *poprawki błędów*

- deck/* – *nowe lub poprawiane decki*

---

## Zasady pracy z gitem
❌ Nie commitujemy bezpośrednio na main

✅ Każda zmiana → osobny branch

✅ Jeden branch = jedno zadanie, chyba, że zadania są ściśle powiązane i idiotyzmem byłoby pisać dwie wykluczające się poprawki

✅ Commit musi mieć ~~sensowny~~ opis

### Przykłady nazw branchy
feature/lobby-timer

fix/disconnect-bug

deck/finanse

## Decki – format plików

Decki trzymamy w katalogu `decks/` jako pliki **`.json`**.

### Szybki workflow (dodanie/zmiana decku)
1. Utwórz / edytuj plik `decks/<nazwa>.json` (najwygodniej przez edytor – patrz niżej)
2. Zrestartuj backend, żeby serwer wczytał nowy plik

---

## Edytor decków (GUI)
W repo jest prosty edytor, który pozwala:
- wczytać deck z serwera,
- wczytać lokalny plik `.json`,
- edytować metadane i karty (białe/czarne),
- pobrać gotowy deck jako `.json`.

Plik: `static/editor.html`

Uwaga: edytor działa sensownie, gdy backend jest uruchomiony (wczytywanie decków z serwera).

---

## Format JSON (v1.0)

Każdy deck ma postać:
- `format_version`: aktualnie `"1.0"`
- `meta`: metadane decku
- `cards.white`: lista kart białych
- `cards.black`: lista kart czarnych

Minimalny szkielet:


json { "format_version": "1.0", "meta": { "name": "my_deck", "display_name": "Mój deck", "authors": [], "description": "", "language": "pl", "tags": [], "version": "" }, "cards": { "white": [], "black": [] } }``` 

### Karta biała (`cards.white[]`)
Biała karta zawiera odmianę przez przypadki (PL) w polu `forms`.

- `id`: identyfikator karty (unikalny w ramach decku)
- `forms`: obiekt z kluczami: `M, D, C, B, N, MSC, W`
- `theme`: lista stringów (opcjonalna kategoryzacja)
- `tags`: lista tagów
- `weight`: waga losowania (domyślnie `1`)

Przykład (schematyczny):


json { "id": "w0001", "forms": { "M": "…", "D": "…", "C": "…", "B": "…", "N": "…", "MSC": "…", "W": "…" }, "theme": [], "tags": [], "weight": 1 }``` 

### Karta czarna (`cards.black[]`)
Czarna karta używa placeholderów przypadków, np. `<M>`, `<B>`, itd.  
Placeholder wskazuje, której formy z białej karty użyć w danym slocie.

- `template`: treść karty czarnej z placeholderami
- `slots`: lista placeholderów wykrytych w `template` (np. `["B"]` albo `["B","B"]`)
- `pick`: ile białych kart jest dobieranych (zwykle liczba slotów; jeśli brak slotów → `1`)
- `id`, `tags`, `weight`: jak wyżej

Przykład:


json { "id": "b0001", "template": "Tekst z placeholderem .", "slots": ["B"], "pick": 1, "tags": [], "weight": 1 }``` 

### Odmiana przez przypadki (PL) – placeholdery
Skróty używane w kartach czarnych:

`<M>` – Mianownik (kto? co?)  
`<D>` – Dopełniacz (kogo? czego?)  
`<C>` – Celownik (komu? czemu?)  
`<B>` – Biernik (kogo? co?)  
`<N>` – Narzędnik (z kim? z czym?)  
`<MSC>` – Miejscownik (o kim? o czym?)  
`<W>` – Wołacz

## Wersjonowanie
Stosujemy (xD) semantyczne wersjonowanie:

### MAJOR.MINOR.PATCH
**MAJOR** – duże zmiany / niekompatybilność

**MINOR** – nowe funkcje

**PATCH** – bugfixy, poprawki decków

Przykłady:

- v0.1.0 – pierwsza grywalna wersja

- v0.2.0 – nowe mechaniki

- v0.2.1 – poprawki błędów

---

## Dobre praktyki
* Commituj często, ale sensownie

* Nie bój się branchy – są tanie i bezpieczne

* Decki wrzucamy tylko do branchy deck/*

* Jeśli nie jesteś pewien:  
zapytaj  
...a najlepiej zrób osobny branch i testuj - naprawiając błędy uczysz się szybciej, niż robiąc rzeczy w pytkę od strzału

### Uwagi końcowe
Projekt jest rozwijany iteracyjnie.  
Nie wszystko musi być idealne — ważne, żeby był fun, gra działała i projekt nie ciągnął się jak dzieje khorinis.

### Miłej zabawy