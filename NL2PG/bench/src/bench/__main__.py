"""Punto di ingresso principale per l'esecuzione del pacchetto bench via CLI.

:author: Riccardo Morabito
"""

from bench.adapters.inbound.cli.app import app

if __name__ == "__main__":
    app()
