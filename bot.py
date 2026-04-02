import os
import logging
import threading
from datetime import datetime

print("🚀 Starting bot...")

# Flask (to keep Render alive)
from flask import Flask

# Google Sheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Telegram
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# ================================
# 🔐 CONFIG
# ================================
TOKEN = os.getenv("TOKEN")
SHEET_NAME = "Fees Tracker"

print("TOKEN Loaded:", "YES" if TOKEN else "NO")

# ================================
# 🌐 DUMMY WEB SERVER
# ================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running!"

def run_web():
    web_app.run(host='0.0.0.0', port=10000)

# ================================
# 📊 GOOGLE SHEETS SETUP
# ================================
try:
    print("🔗 Connecting to Google Sheets...")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

    print("✅ Google Sheets connected!")

except Exception as e:
    print("❌ Google Sheets ERROR:", e)
    raise e

# ================================
# STATES
# ================================
NAME, AMOUNT, CATEGORY, STATUS = range(4)

logging.basicConfig(level=logging.INFO)

# ================================
# START MENU
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["➕ Add Entry", "📊 Summary", "📌 Pending"]]
    await update.message.reply_text(
        "Choose option:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================================
# ADD ENTRY FLOW
# ================================
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter Name:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Enter Amount:")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["amount"] = update.message.text

    keyboard = [["academy", "jersey", "match"]]
    await update.message.reply_text(
        "Select Category:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text

    keyboard = [["paid", "pending"]]
    await update.message.reply_text(
        "Select Status:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATUS

async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["status"] = update.message.text

    name = context.user_data["name"]
    amount = context.user_data["amount"]
    category = context.user_data["category"]
    status = context.user_data["status"]
    date = datetime.now().strftime("%Y-%m-%d")

    try:
        sheet.append_row([name, amount, category, status, date])
        print("✅ Row added:", name, amount)
    except Exception as e:
        print("❌ Sheet Write Error:", e)

    await update.message.reply_text(
        f"✅ Added:\n{name} | ₹{amount} | {category} | {status}"
    )

    return ConversationHandler.END

# ================================
# SUMMARY
# ================================
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    total_paid = 0
    total_pending = 0

    for r in records:
        amt = int(r["Amount"])
        if r["Status"] == "paid":
            total_paid += amt
        else:
            total_pending += amt

    await update.message.reply_text(
        f"💰 Paid: ₹{total_paid}\n⏳ Pending: ₹{total_pending}"
    )

# ================================
# PENDING
# ================================
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()
    pending_list = [r for r in records if r["Status"] == "pending"]

    if not pending_list:
        await update.message.reply_text("No pending payments 🎉")
        return

    msg = "📌 Pending:\n"
    for r in pending_list:
        msg += f"{r['Name']} - ₹{r['Amount']} ({r['Category']})\n"

    await update.message.reply_text(msg)

# ================================
# CANCEL
# ================================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

# ================================
# MAIN
# ================================
def main():
    try:
        print("🚀 Starting services...")

        # Start dummy server
        threading.Thread(target=run_web).start()

        # Telegram bot
        app_bot = ApplicationBuilder().token(TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("➕ Add Entry"), add_entry)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
                CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
                STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_status)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(MessageHandler(filters.Regex("📊 Summary"), summary))
        app_bot.add_handler(MessageHandler(filters.Regex("📌 Pending"), pending))
        app_bot.add_handler(conv_handler)

        print("✅ Bot is running now...")
        app_bot.run_polling()

    except Exception as e:
        print("❌ BOT ERROR:", e)
        raise e

# ================================
# RUN
# ================================
if __name__ == "__main__":
    main()