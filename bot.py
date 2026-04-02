import os
import json
import threading
from datetime import datetime

from flask import Flask

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

# =====================
# CONFIG
# =====================
TOKEN = os.getenv("TOKEN")
SHEET_NAME = "Fees Tracker"

# =====================
# GOOGLE AUTH
# =====================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# Add headers if not present
headers = sheet.row_values(1)
if not headers:
    sheet.append_row(["Name", "Amount", "Category", "Type", "Status", "Date"])

print("✅ Google Sheets connected")

# =====================
# FLASK (KEEP ALIVE)
# =====================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot running"

def run_web():
    app_web.run(host='0.0.0.0', port=10000)

# =====================
# STATES
# =====================
NAME, AMOUNT, TYPE, CATEGORY, STATUS = range(5)

# =====================
# MENU
# =====================
def get_menu():
    return ReplyKeyboardMarkup(
        [["➕ Add Entry", "📊 Summary", "📌 Pending"]],
        resize_keyboard=True
    )

# =====================
# HANDLERS
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose option:", reply_markup=get_menu())

async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter Name:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Ignore menu buttons
    if text in ["➕ Add Entry", "📊 Summary", "📌 Pending"]:
        await update.message.reply_text("Please enter a valid name:")
        return NAME

    context.user_data["name"] = text
    await update.message.reply_text("Enter Amount:")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = int(update.message.text)
    except:
        await update.message.reply_text("❌ Enter valid number")
        return AMOUNT

    keyboard = [["income", "expense"]]
    await update.message.reply_text(
        "Select Type:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TYPE

async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["type"] = update.message.text

    keyboard = [["academy", "jersey", "match", "salary"]]
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
    name = context.user_data["name"]
    amount = context.user_data["amount"]
    type_ = context.user_data["type"]
    category = context.user_data["category"]
    status = update.message.text
    date = datetime.now().strftime("%Y-%m-%d")

    sheet.append_row([name, amount, category, type_, status, date])

    await update.message.reply_text(
        "✅ Entry saved!\n\nChoose next option:",
        reply_markup=get_menu()
    )

    return ConversationHandler.END

# =====================
# SUMMARY (FIXED)
# =====================
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    income = 0
    expense = 0

    for r in records:
        try:
            amt = int(r.get("Amount", 0))
            type_val = str(r.get("Type", "")).strip().lower()

            if type_val == "income":
                income += amt
            elif type_val == "expense":
                expense += amt
        except:
            continue

    balance = income - expense

    await update.message.reply_text(
        f"💰 Income: ₹{income}\n💸 Expense: ₹{expense}\n📊 Balance: ₹{balance}",
        reply_markup=get_menu()
    )

# =====================
# PENDING (FIXED)
# =====================
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    pending_list = []

    for r in records:
        status_val = str(r.get("Status", "")).strip().lower()

        if status_val == "pending":
            pending_list.append(r)

    if not pending_list:
        await update.message.reply_text(
            "No pending 🎉",
            reply_markup=get_menu()
        )
        return

    msg = "📌 Pending:\n"

    for r in pending_list:
        name = r.get("Name", "Unknown")
        amount = r.get("Amount", "0")
        category = r.get("Category", "-")

        msg += f"{name} - ₹{amount} ({category})\n"

    await update.message.reply_text(msg, reply_markup=get_menu())

# =====================
# MAIN
# =====================
def main():
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ Add Entry"), add_entry)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_type)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
            STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_status)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("📊 Summary"), summary))
    app.add_handler(MessageHandler(filters.Regex("📌 Pending"), pending))
    app.add_handler(conv)

    print("🚀 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()