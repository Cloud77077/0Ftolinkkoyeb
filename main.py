import os
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

ptb_application = Application.builder().token(BOT_TOKEN).build()

# ==================== BOT HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot is working!\n\nSend any file to get direct link with Stream + Download buttons."
    )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        file_type = "Voice"
    elif message.animation:
        file = message.animation
        file_type = "GIF"
        is_video = True
    else:
        await message.reply_text("Send a file (video, photo, document, etc.)")
        return

    try:
        tg_file = await context.bot.get_file(file.file_id)
        direct_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_file.file_path}"

        text = f"✅ {file_type} Ready!\n\n⚡ Maximum speed from Telegram"

        if is_video:
            keyboard = [
                [{"text": "▶️ Stream", "url": direct_link}],
                [{"text": "📥 Download", "url": direct_link}]
            ]
        else:
            keyboard = [[{"text": "📥 Download", "url": direct_link}]]

        await message.reply_text(
            text,
            reply_markup={"inline_keyboard": keyboard}
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("Error processing file.")

ptb_application.add_handler(CommandHandler("start", start_command))
ptb_application.add_handler(MessageHandler(
    filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.ANIMATION,
    file_handler
))

# ==================== FASTAPI ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and start the bot application
    await ptb_application.initialize()
    await ptb_application.start()
    
    if WEBHOOK_URL:
        await ptb_application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    
    yield
    
    # Shutdown
    await ptb_application.stop()
    await ptb_application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        await ptb_application.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
