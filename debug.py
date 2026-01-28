import os

def check_deck(filename):
    print(f"--- Sprawdzam plik: {filename} ---")
    if not os.path.exists(filename):
        print("❌ Plik nie istnieje!")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        print("❌ BŁĄD KODOWANIA: Plik nie jest zapisany w UTF-8. Zapisz go w notatniku jako UTF-8.")
        return

    errors = 0
    for i, line in enumerate(lines):
        line_num = i + 1
        raw = line.strip()

        if not raw:
            continue

        parts = raw.split('|')
        count = len(parts)

        if count == 1:
            pass
        elif count == 7:
            pass
        else:
            print(f"⚠️ OSTRZEŻENIE w linii {line_num}: Znaleziono {count} elementów zamiast 1 lub 7.")
            print(f"   Treść: {raw}")
            errors += 1

    if errors == 0:
        print("✅ Plik wygląda poprawnie!")
    else:
        print(f"❌ Znaleziono {errors} potencjalnych problemów.")
    print("\n")


if __name__ == "__main__":
    check_deck("decks/base.white")
    check_deck("decks/base.black")