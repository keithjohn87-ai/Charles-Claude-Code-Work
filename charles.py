"""Charles entrypoint. M0: starts the Telegram channel and blocks."""
from channels.telegram import run

if __name__ == "__main__":
    run()
