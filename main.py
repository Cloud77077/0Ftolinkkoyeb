import os
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

ptb_application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Welcome to File → Link Bot!</b>\n\n"
        "Send any file and I will give you a direct download link.\n\n"
        "Just send a file now!",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Just send any file (photo, video, document, audio etc) and I will give direct link.\n\n"
        "Commands: /start /help",
        parse_mode="HTML"
    )

async def file_to_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file = None
    file_type = "File"

    if message.document:
        file = message.document
        file_type = "Document"
    elif message.photo:
        file = message.photo[-1]
        file_type = "Photo"
    elif message.video:
        file = message.video
        file_type = "Video"
    elif message.audio:
        file = message.audio
        file_type = "Audio"
    elif message.voice:
        file = message.voice
        file_type = "Voice"
    elif message.animation:
        file = message.animation
        file_type = "GIF"
    elif message.video_note:
        file = message.video_note
        file_type = "Video Note"
    else:
        await message.reply_text("Please send a file (photo, video, document etc)")
        return

    try:
        tg_file = await context.bot.get_file(file.file_id)
        direct_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_file.file_path}"

        filename = getattr(file, "file_name", None) or f"{file_type}_{file.file_id[:8]}"
        size_bytes = getattr(file, "file_size", 0) or 0
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} B"

        text = f"✅ Direct Link Ready!\n\nType: {file_type}\nName: {filename}\nSize: {size_str}"
        keyboard = [[InlineKeyboardButton("📥 Download", url=direct_link)]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("Sorry, error. Try again.")

ptb_application.add_handler(CommandHandler("start", start_command))
ptb_application.add_handler(CommandHandler("help", help_command))

file_filters = (filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.ANIMATION | filters.VIDEO_NOTE)
ptb_application.add_handler(MessageHandler(file_filters, file_to_link_handler))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL:
        await ptb_application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    yield

app = FastAPI(title="File to Link Bot", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        await ptb_application.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

@app.get("/")
async def root():
    return {"message": "Bot is running!"}
