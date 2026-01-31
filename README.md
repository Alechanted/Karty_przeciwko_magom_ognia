# Karty przeciwko magom ognia

Nieoficjalna, elektroniczna wersja gry typu *Cards Against Humanity*, napisana w **Pythonie (backend)** i **JavaScript (frontend)**, przystosowana do grania online z pięknymi mężczyznami.  
Projekt ma charakter **hobbystyczny / edukacyjny / szyderczo-złośliwy / metareligijny**.

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
    game.js
    index.html    
    style.css 
/decks
    example.white
    example.black
bot.py
README.md
debug.py
locales.py
main.py
models.py
room_manager.py
run.py
```
- static/ – *interfejs użytkownika (JS/HTML/CSS)*

- decks/ – *pliki z kartami (bez logiki)*

- bot.py - *logika botów*

- debug.py – *skrypt do sprawdzania poprawności decków*

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
Decki są prostymi plikami tekstowymi, łatwymi do edycji nawet dla osób bez doświadczenia programistycznego.

### Informacje ogólne
Decki umieszczamy w katalogu decks/

Wystarczy:

1. wrzucić plik do katalogu

2. zrestartować program

Każda linijka pliku = jedna karta

### Odmiana przez przypadki (PL)

Skróty używane w kartach:

`<M>` – Mianownik (kto? co?)

`<D>` – Dopełniacz (kogo? czego?)

`<C>` – Celownik (komu? czemu?)

`<B>` – Biernik (kogo? co?)

`<N>` – Narzędnik (z kim? z czym?)

`<MSC>` – Miejscownik (o kim? o czym?)

`<W>` – Wołacz

### Pliki .white
Każda linijka zawiera kartę białą odmienioną przez wszystkie przypadki  
Odmiany oddzielone są znakiem |

Przykład:
```text
błogosławienie nowicjusza do listu gończego z mordą Bezimiennego | błogosławienia nowicjusza do listu gończego z mordą Bezimiennego | błogosławieniu nowicjusza do listu gończego z mordą Bezimiennego | błogosławienie nowicjusza do listu gończego z mordą Bezimiennego | błogosławieniem nowicjusza do listu gończego z mordą Bezimiennego | błogosławieniu nowicjusza do listu gończego z mordą Bezimiennego | błogosławienie nowicjusza do listu gończego z mordą Bezimiennego
spuszczanie się z drabiny | spuszczania się z drabiny | spuszczaniu się z drabiny | spuszczanie się z drabiny | spuszczaniem się z drabiny | spuszczaniu się z drabiny | spuszczanie się z drabiny
mordowanie magów ognia | mordowania magów ognia | mordowaniu magów ognia | mordowanie magów ognia | mordowaniem magów ognia | mordowaniu magów ognia | mordowanie magów ognia
```

### Pliki .black
Każda linijka to karta czarna  
Karta zawiera jedno lub dwa puste pola  
Puste pole oznaczamy skrótem przypadku w ostrych nawiasach

Przykład:
```text
Jestem Ur-Shak. Jestem Syn Ducha, ludzie mówią: <M>
Nie interesuje mnie kim jesteś, Jesteś tu nowy, a do mnie należy dbanie o <B>
Nie. Po namyśle doszedłem do wniosku, że bardziej przydasz się tutaj. Będziesz dla mnie <B>
```

### Sprawdzanie decków
Format decków można szybko sprawdzić:
```bash
python debug.py
```
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




