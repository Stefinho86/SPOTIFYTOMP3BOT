import os
import logging
import tempfile
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from bs4 import BeautifulSoup

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MENU, CHOOSE_MODE, ENTER_QUERY, SHOW_RESULTS = range(4)

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def get_spotify_client():
    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
    )

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎵 Cerca titolo"), KeyboardButton("🎤 Cerca artista")],
        [KeyboardButton("💿 Cerca album"), KeyboardButton("📜 Cerca playlist")],
        [KeyboardButton("❌ Esci")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await manda_menu(update)
    return MENU

async def manda_menu(update):
    if hasattr(update, "message") and update.message:
        await update.message.reply_text(
            "Benvenuto! Scegli una modalità di ricerca su Spotify.",
            reply_markup=main_keyboard()
        )
    elif hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.message.reply_text(
            "Menù principale:",
            reply_markup=main_keyboard()
        )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "titolo" in text:
        context.user_data['mode'] = "track"
        await update.message.reply_text("Inserisci il titolo del brano da cercare:", reply_markup=ReplyKeyboardMarkup([["Annulla"]], resize_keyboard=True))
        return ENTER_QUERY
    elif "artista" in text:
        context.user_data['mode'] = "artist"
        await update.message.reply_text("Inserisci il nome dell'artista:", reply_markup=ReplyKeyboardMarkup([["Annulla"]], resize_keyboard=True))
        return ENTER_QUERY
    elif "album" in text:
        context.user_data['mode'] = "album"
        await update.message.reply_text("Inserisci il nome dell'album:", reply_markup=ReplyKeyboardMarkup([["Annulla"]], resize_keyboard=True))
        return ENTER_QUERY
    elif "playlist" in text:
        context.user_data['mode'] = "playlist"
        await update.message.reply_text("Inserisci il nome della playlist:", reply_markup=ReplyKeyboardMarkup([["Annulla"]], resize_keyboard=True))
        return ENTER_QUERY
    elif "esci" in text or "annulla" in text or "/annulla" in text:
        await update.message.reply_text(
            "Conversazione annullata.",
            reply_markup=ReplyKeyboardRemove()
        )
        await manda_menu(update)
        return MENU
    else:
        await update.message.reply_text("Scegli una delle opzioni dal menu.")
        return MENU

async def enter_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ["annulla", "/annulla"]:
        await update.message.reply_text(
            "Operazione annullata.",
            reply_markup=ReplyKeyboardRemove()
        )
        await manda_menu(update)
        return MENU

    mode = context.user_data.get('mode')
    sp = get_spotify_client()
    results = []
    try:
        if mode == "track":
            res = sp.search(q=text, type='track', limit=15)
            items = res['tracks']['items']
            for t in items:
                results.append({
                    'type': 'track',
                    'name': t['name'],
                    'artists': ", ".join(a['name'] for a in t['artists']),
                    'url': t['external_urls']['spotify']
                })
        elif mode == "artist":
            res = sp.search(q=text, type='artist', limit=10)
            items = res['artists']['items']
            for a in items:
                results.append({
                    'type': 'artist',
                    'name': a['name'],
                    'url': a['external_urls']['spotify']
                })
        elif mode == "album":
            res = sp.search(q=text, type='album', limit=10)
            items = res['albums']['items']
            for a in items:
                results.append({
                    'type': 'album',
                    'name': a['name'],
                    'artists': ", ".join(ar['name'] for ar in a['artists']),
                    'url': a['external_urls']['spotify']
                })
        elif mode == "playlist":
            res = sp.search(q=text, type='playlist', limit=10)
            items = res['playlists']['items']
            for p in items:
                results.append({
                    'type': 'playlist',
                    'name': p['name'],
                    'owner': p['owner']['display_name'],
                    'url': p['external_urls']['spotify']
                })
    except Exception as e:
        logger.error(f"Errore ricerca Spotify: {e}")
        await update.message.reply_text("Errore nella ricerca su Spotify.")
        return MENU

    if not results:
        await update.message.reply_text("Nessun risultato trovato.")
        await manda_menu(update)
        return MENU

    context.user_data['results'] = results
    context.user_data['page'] = 0
    await show_results(update, context)
    return SHOW_RESULTS

async def show_results(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data['results']
    page = context.user_data.get('page', 0)
    per_page = 5
    total = len(results)
    start = page * per_page
    end = start + per_page
    paginated = results[start:end]
    msg = ""
    keyboard = []
    for idx, r in enumerate(paginated, start=1):
        if r['type'] == 'track':
            msg += f"*{idx}. {r['name']}* \n   _Artista:_ {r['artists']}\n"
        elif r['type'] == 'album':
            msg += f"*{idx}. Album: {r['name']}* \n   _Artista:_ {r['artists']}\n"
        elif r['type'] == 'playlist':
            msg += f"*{idx}. Playlist: {r['name']}* \n   _Owner:_ {r['owner']}\n"
        elif r['type'] == 'artist':
            msg += f"*{idx}. Artista: {r['name']}*\n"
    msg += "\nScegli cosa scaricare dai pulsanti qui sotto."
    # Pulsanti scarica
    for i, r in enumerate(paginated):
        keyboard.append([InlineKeyboardButton(f"Scarica {i+1}", callback_data=f"dl_{start+i}")])
    # Navigazione
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Indietro", callback_data="prev"))
    if end < total:
        nav.append(InlineKeyboardButton("Avanti ➡️", callback_data="next"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="annulla")])
    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        await update_or_query.callback_query.edit_message_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update_or_query.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

async def show_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "next":
        context.user_data['page'] += 1
        await show_results(update, context)
        return SHOW_RESULTS
    elif data == "prev":
        context.user_data['page'] = max(0, context.user_data['page'] - 1)
        await show_results(update, context)
        return SHOW_RESULTS
    elif data.startswith("dl_"):
        idx = int(data[3:])
        result = context.user_data['results'][idx]
        url = result['url']
        name = result['name']
        await query.edit_message_text(f"Scaricamento da SpotifyMate in corso per {name}...")
        mp3_urls = get_mp3_from_spotimate(url)
        if not mp3_urls:
            await query.message.reply_text("❌ Impossibile recuperare download da SpotifyMate.")
            await manda_menu(query)
            return MENU
        # Per semplificare: se è una lista prendi il primo, oppure scarica tutti
        for mp3_url in mp3_urls:
            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(temp_fd)
            r = requests.get(mp3_url, stream=True)
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            with open(temp_path, "rb") as f:
                await query.message.reply_audio(audio=f, title=name)
            os.remove(temp_path)
        await query.message.reply_text("✅ Download completato.")
        await manda_menu(query)
        return MENU
    elif data == "annulla":
        await query.edit_message_text("Operazione annullata.")
        await manda_menu(query)
        return MENU
    else:
        await query.edit_message_text("Comando sconosciuto.")
        await manda_menu(query)
        return MENU

def get_mp3_from_spotimate(spotify_url):
    session = requests.Session()
    main_url = "https://spotimate.io/it"
    try:
        resp = session.post(
            main_url,
            data={"url": spotify_url},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        # Cerca tutti i link mp3
        mp3_links = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href.endswith(".mp3"):
                mp3_links.append(href)
        return mp3_links
    except Exception as e:
        logger.exception("Errore nell'accesso a SpotifyMate")
        return None

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Conversazione annullata.", reply_markup=ReplyKeyboardRemove())
    await manda_menu(update)
    return MENU

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [MessageHandler(filters.TEXT, menu)],
            ENTER_QUERY: [MessageHandler(filters.TEXT, enter_query)],
            SHOW_RESULTS: [CallbackQueryHandler(show_callback)],
        },
        fallbacks=[
            CommandHandler('annulla', annulla),
            MessageHandler(filters.Regex("(?i)annulla"), annulla)
        ],
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()