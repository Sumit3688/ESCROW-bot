import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ✅ Step 1: Function jo buyer confirm message bhejega
async def ask_buyer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✅ Deal is 100% secure.\nEverything is under Pagal World Escrow."
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("✅ Confirm as Buyer", callback_data="confirm_buyer")
    )
    if update.message:  # agar normal message hai
        await update.message.reply_text(text, reply_markup=keyboard)
    else:  # agar callback se aya hai
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)

# ✅ Step 2: Function jo button press hone par chalega
async def handle_buyer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # 👉 yahan buyer ko assign karne ka logic add karna hai (abhi simple text)
    await query.edit_message_text("You are set as the buyer. ✅")

# ✅ Step 3: Application create karke handlers attach karna
def create_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # /buyerconfirm command → message + button bhejta hai
    app.add_handler(CommandHandler("buyerconfirm", ask_buyer_confirm))

    # confirm button dabane par yeh handle karega
    app.add_handler(CallbackQueryHandler(handle_buyer_confirm, pattern="^confirm_buyer$"))

    return app
