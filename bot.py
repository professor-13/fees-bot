import os
import logging
import threading
from datetime import datetime

print("🚀 BOT STARTING...")

# Flask
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

TOKEN = os.getenv("TOKEN")
SHEET_NAME = "Fees Tracker"

print("TOKEN:", "OK" if TOKEN else "MISSING")

# Flask server
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot running"

def run_web():
    web_app.run(host='0.0.0.0', port=10000)

# Google Sheets
try:
    print("Loading credentials.json...")

    if not os.path.exists("credentials.json"):
        raise Exception("credentials.json NOT FOUND")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)

    print("Opening sheet:", SHEET_NAME)

    sheet = client.open(SHEET_NAME).sheet1

    print("✅ Google Sheets connected")

except Exception as e:
    print("❌ GOOGLE ERROR:", e)
    raise e


NAME, AMOUNT, CATEGORY, STATUS = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["➕ Add Entry", "📊 Summary", "📌 Pending"]]
    await update.message.reply_text("Choose option:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

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
    await update.message.reply_text("Select Category:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    keyboard = [["paid", "pending"]]
    await update.message.reply_text("Select Status:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return STATUS

async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["name"]
    amount = context.user_data["amount"]
    category = context.user_data["category"]
    status = update.message.text
    date = datetime.now().strftime("%Y-%m-%d")

    sheet.append_row([name, amount, category, status, date])

    await update.message.reply_text(f"✅ Added {name}")
    return ConversationHandler.END

def main():
    print("Starting services...")

    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Add Entry"), add_entry)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
            STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_status)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("✅ BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ FINAL ERROR:", e)
        raise e