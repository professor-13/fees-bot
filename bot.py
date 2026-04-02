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

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.getenv("GOOGLE_CREDENTIALS")), scope
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# Headers
headers = sheet.row_values(1)
if not headers:
    sheet.append_row(["Name", "Amount", "Category", "Type", "Status", "Date"])

print("✅ Google Sheets connected")

# =====================
# FLASK
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
        [["➕ Add Entry", "📊 Summary"],
         ["📌 Pending", "📅 Monthly Report"]],
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

    if text in ["➕ Add Entry", "📊 Summary", "📌 Pending", "📅 Monthly Report"]:
        await update.message.reply_text("Enter valid name:")
        return NAME

    context.user_data["name"] = text
    await update.message.reply_text("Enter Amount:")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = int(update.message.text)
    except:
        await update.message.reply_text("Enter valid number")
        return AMOUNT

    keyboard = [["income", "expense"]]
    await update.message.reply_text("Select Type:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return TYPE

async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["type"] = update.message.text

    keyboard = [["academy", "jersey", "match", "salary"]]
    await update.message.reply_text("Select Category:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text

    keyboard = [["paid", "pending"]]
    await update.message.reply_text("Select Status:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return STATUS

async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet.append_row([
        context.user_data["name"],
        context.user_data["amount"],
        context.user_data["category"],
        context.user_data["type"],
        update.message.text,
        datetime.now().strftime("%Y-%m-%d")
    ])

    await update.message.reply_text("✅ Saved", reply_markup=get_menu())
    return ConversationHandler.END

# =====================
# SUMMARY
# =====================
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    income = 0
    expense = 0

    for r in records:
        try:
            amt = int(r.get("Amount", 0))
            t = str(r.get("Type", "")).lower()

            if t == "income":
                income += amt
            elif t == "expense":
                expense += amt
        except:
            continue

    await update.message.reply_text(
        f"💰 Income: ₹{income}\n💸 Expense: ₹{expense}\n📊 Balance: ₹{income - expense}",
        reply_markup=get_menu()
    )

# =====================
# PENDING
# =====================
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    pending_list = [r for r in records if str(r.get("Status", "")).lower() == "pending"]

    if not pending_list:
        await update.message.reply_text("No pending 🎉", reply_markup=get_menu())
        return

    msg = "📌 Pending:\n"
    for r in pending_list:
        msg += f"{r['Name']} - ₹{r['Amount']} ({r['Category']})\n"

    await update.message.reply_text(msg, reply_markup=get_menu())

# =====================
# MONTHLY REPORT
# =====================
async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = sheet.get_all_records()

    current_month = datetime.now().strftime("%Y-%m")

    income = 0
    expense = 0

    for r in records:
        try:
            date = str(r.get("Date", ""))
            if current_month in date:
                amt = int(r.get("Amount", 0))
                t = str(r.get("Type", "")).lower()

                if t == "income":
                    income += amt
                elif t == "expense":
                    expense += amt
        except:
            continue

    await update.message.reply_text(
        f"📅 Monthly Report\n\n💰 Income: ₹{income}\n💸 Expense: ₹{expense}\n📊 Profit: ₹{income - expense}",
        reply_markup=get_menu()
    )

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
    app.add_handler(MessageHandler(filters.Regex("📅 Monthly Report"), monthly_report))
    app.add_handler(conv)

    print("🚀 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()