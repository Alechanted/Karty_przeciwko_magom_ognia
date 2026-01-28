import uvicorn

# KONFIGURACJA
HOST = "0.0.0.0"
PORT = 2137
RELOAD = True #autoodświeżanie kodu - fajne do szybkiego sprawdzania zmian, ale może robić dziwne akcje

if __name__ == "__main__":
    print(f"Uruchamianie serwera gry na http://{HOST}:{PORT}")

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        log_level="info"
    )