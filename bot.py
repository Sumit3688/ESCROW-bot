import os
from telegram.ext import Application
# from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
# from your_handlers import start, on_currency_select, assign_buyer, handle_text

def create_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # ⬇️ Attach your handlers here
    # app.add_handler(CommandHandler("start", start))
    # app.add_handler(CallbackQueryHandler(on_currency_select, pattern="^currency_"))
    # app.add_handler(CallbackQueryHandler(assign_buyer, pattern="^assign_buyer"))
    # app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
