import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
from dotenv import load_dotenv

from vk_search import vk_login, vk_audio_search
# from public_search import search_ru_music  # Scommenta se usi altre fonti

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VK_LOGIN = os.getenv("VK_LOGIN")
VK_PASSWORD = os.getenv("VK_PASSWORD")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎶 Inviami il nome di una canzone, artista o incolla un link Spotify. "
        "Io cercherò l'mp3 su database pubblici (VK, ecc.)"
    )

async def search_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Scrivi il nome di una canzone o artista.")
        return

    # 1. Ricerca su VK
    await update.message.reply_text("🔎 Cerco su VK...")
    if not context.bot_data.get("vk_session"):
        vk_session = vk_login(VK_LOGIN, VK_PASSWORD)
        if not vk_session:
            await update.message.reply_text("❌ Errore login VK.")
            return
        context.bot_data["vk_session"] = vk_session
    else:
        vk_session = context.bot_data["vk_session"]

    vk_results = vk_audio_search(vk_session, query, max_results=3)
    if vk_results:
        for track in vk_results:
            try:
                await update.message.reply_audio(
                    audio=track['url'],
                    title=track['title'],
                    performer=track['artist'],
                    caption=f"{track['artist']} - {track['title']}\n[VK]"
                )
            except Exception as e:
                logger.error(f"Errore invio audio VK: {e}")

    # 2. Ricerca su altri motori pubblici (opzionale)
    # await update.message.reply_text("🔎 Cerco su ru-music...")
    # ru_results = search_ru_music(query)
    # if ru_results:
    #     for track in ru_results:
    #         try:
    #             await update.message.reply_audio(
    #                 audio=track['url'],
    #                 title=track['title'],
    #                 caption=f"{track['title']}\n[ru-music.com]"
    #             )
    #         except Exception as e:
    #             logger.error(f"Errore invio audio ru-music: {e}")

    if not vk_results:  # and not ru_results  # Estendi se usi altri motori
        await update.message.reply_text("❌ Nessun risultato trovato su VK.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_and_send))
    app.run_polling()

if __name__ == "__main__":
    main()