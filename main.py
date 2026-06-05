import os
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required!")

ptb_application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

# ==================== IMPROVED HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Welcome to File → Link Bot</b>\n\n"
        "Send any file and get <b>direct link</b> with <b>maximum speed</b>.\n\n"
        "✅ Supports up to 2GB\n"
        "✅ Best for streaming videos & fast downloads\n\n"
        "Just send a file now!",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>How to use:</b>\n\n"
        "• Send video → Get Stream + Download buttons\n"
        "• Send document/photo/audio → Get fast download link\n\n"
        "All links come from Telegram's own servers = Maximum speed!",
        parse_mode="HTML"
    )

async def file_to_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    file = None
    file_type = "File"
    is_video = False

    if message.document:
        file = message.document
        file_type = "Document"
    elif message.photo:
        file = message.photo[-1]
        file_type = "Photo"
    elif message.video:
        file = message.video
        file_type = "Video"
        is_video = True
    elif message.audio:
        file = message.audio
        file_type = "Audio"
    elif message.voice:
        file = message.voice
        file_type = "Voice Message"
    elif message.animation:
        file = message.animation
        file_type = "GIF / Animation"
        is_video = True
    elif message.video_note:
        file = message.video_note
        file_type = "Video Note"
        is_video = True
    else:
        await message.reply_text("Please send a supported file (video, photo, document, audio, etc.)")
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
            size_str = f"{size_bytes} bytes"

        # Beautiful message
        text = (
            f"✅ <b>{file_type} Ready!</b>\n\n"
            f"📝 <b>Name:</b> <code>{filename}</code>\n"
            f"📦 <b>Size:</b> {size_str}\n\n"
            f"⚡ <b>Maximum Speed</b> — Powered by Telegram CDN\n"
            f"No limits. No capping. Enjoy!"
        )

        # Smart buttons
        if is_video:
            # For videos and GIFs → Show both Stream and Download
            keyboard = [
                [InlineKeyboardButton("▶️ Stream / Watch Online", url=direct_link)],
                [InlineKeyboardButton("📥 Download File", url=direct_link)]
            ]
        else:
            # For other files → Strong download button
            keyboard = [[InlineKeyboardButton("📥 Download File", url=direct_link)]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        logger.info(f"Link sent: {file_type} ({size_str})")

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("❌ Error processing file. Please try again.")

# Register everything
ptb_application.add_handler(CommandHandler("start", start_command))
ptb_application.add_handler(CommandHandler("help", help_command))

file_filters = (
    filters.Document.ALL | filters.PHOTO | filters.VIDEO | 
    filters.AUDIO | filters.VOICE | filters.ANIMATION | filters.VIDEO_NOTE
)
ptb_application.add_handler(MessageHandler(file_filters, file_to_link_handler))

# ==================== FASTAPI ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_URL:
        await ptb_application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    yield

app = FastAPI(title="File to Link Bot - Improved", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

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
    return {"message": "Improved File to Link Bot is running!"}
