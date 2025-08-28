import logging, threading, asyncio, os
from app import app
from bot import create_application

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

def run_bot():
    application = create_application()
    asyncio.run(
        application.run_polling(
            allowed_updates=application.resolve_used_update_types()
        )
    )

if __name__ == "__main__":
    logging.info("Starting Admin Dashboard + Telegram Bot...")
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    run_flask()
