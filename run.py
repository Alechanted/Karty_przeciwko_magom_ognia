import uvicorn
import multiprocessing
import time
import random
from locales import BOT_NAMES
from bot import start_bot_process

# --- KONFIGURACJA ---
HOST = "0.0.0.0"
PORT = 2137
RELOAD = True
NUM_BOTS = 3  # <-- TUTAJ USTALASZ LICZBĘ BOTÓW


def launch_bots():
    """Funkcja zarządzająca procesami botów."""
    processes = []

    # Wybierz unikalne imiona (lub powtarzaj, jeśli botów jest więcej niż imion)
    available_names = BOT_NAMES.copy()
    random.shuffle(available_names)

    print(f"--- URUCHAMIANIE {NUM_BOTS} BOTÓW ---")

    for i in range(NUM_BOTS):
        # Jeśli braknie unikalnych imion, zacznij dodawać cyferki
        if i < len(available_names):
            nick = available_names[i]
        else:
            base_nick = BOT_NAMES[i % len(BOT_NAMES)]
            nick = f"{base_nick}_{i}"

        # Uruchomienie procesu bota
        p = multiprocessing.Process(
            target=start_bot_process,
            args=(nick, HOST, PORT),
            daemon=True  # Daemon sprawi, że boty zginą, gdy ubijesz główny proces
        )
        p.start()
        processes.append(p)
        print(f" -> Uruchomiono bota: {nick}")

    return processes

if __name__ == "__main__":
    print(f"Uruchamianie serwera gry na http://{HOST}:{PORT}")

    bot_processes = launch_bots()

    try:
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=RELOAD,
            log_level="warning"  # Mniej logów z uvicorna, żeby widzieć logi botów
        )
    except KeyboardInterrupt:
        print("Zamykanie serwera...")
    finally:
        # Sprzątanie procesów botów przy wyjściu
        for p in bot_processes:
            p.terminate()