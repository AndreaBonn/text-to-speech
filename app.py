#!/usr/bin/env python3
"""
app.py
Wrapper per mantenere compatibilità con il comando: python app.py

Il codice reale è in src/app.py
"""

if __name__ == "__main__":
    from src.app import app
    from src.config import verifica_prerequisiti
    import os

    errori = verifica_prerequisiti(modalita="web")
    if errori:
        raise SystemExit(1)

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("\n  TTS Reader Web UI")
    print("  http://localhost:5000\n")
    app.run(debug=debug, port=5000)
