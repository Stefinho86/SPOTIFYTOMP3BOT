import os
import logging
import tempfile
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from bs4 import BeautifulSoup

# --- Carica variabili ambiente
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MENU, ENTER_QUERY, SHOW_RESULTS = range(3)

def get_spotify():
    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
    )

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🎵 Brano", "🎤 Artista"],
        ["💿 Album", "📜 Playlist"],
        ["❌ Esci"]
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
    if "brano" in text or ("cerca" in text and "titolo" in text):
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
    sp = get_spotify()
    results = []

    try:
        if mode == "track":
            res = sp.search(q=text, type='track', limit=20)
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
        await update.message.reply_text("Errore nella ricerca su Spotify. Verifica le chiavi API.")
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
            msg += f"*{idx}.* {r['name']} \n   _Artista:_ {r['artists']}\n"
        elif r['type'] == 'album':
            msg += f"*{idx}.* Album: {r['name']} \n   _Artista:_ {r['artists']}\n"
        elif r['type'] == 'playlist':
            msg += f"*{idx}.* Playlist: {r['name']} \n   _Owner:_ {r['owner']}\n"
        elif r['type'] == 'artist':
            msg += f"*{idx}.* Artista: {r['name']}\n"
    msg += "\nScegli cosa scaricare dai pulsanti qui sotto."
    for i, r in enumerate(paginated):
        if r['type'] == 'artist':
            keyboard.append([InlineKeyboardButton(f"Visualizza", url=r['url'])])
        else:
            keyboard.append([InlineKeyboardButton(f"Scarica {i+1}", callback_data=f"dl_{start+i}")])
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
        spotify_url = result['url']
        name = result['name']
        artist = result.get('artists', result.get('owner', ''))
        await query.edit_message_text(f"Sto cercando di scaricare *{name}* da SpotiDownloader...", parse_mode="Markdown")
        mp3_link = get_mp3_from_spotidownloader(spotify_url)
        if not mp3_link:
            await query.message.reply_text("❌ Download non riuscito. Potrebbe essere attivo un reCAPTCHA o la traccia non è disponibile. Prova da browser o riprova più tardi.")
            await manda_menu(query)
            return MENU
        try:
            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(temp_fd)
            r = requests.get(mp3_link, stream=True, timeout=60)
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            with open(temp_path, "rb") as fmp3:
                await query.message.reply_audio(
                    audio=fmp3,
                    title=name,
                    performer=artist
                )
            os.remove(temp_path)
            await query.message.reply_text("✅ Download completato.")
        except Exception as e:
            logger.error(f"Errore download mp3: {e}")
            await query.message.reply_text("Errore durante il download del file mp3.")
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

def get_mp3_from_spotidownloader(spotify_url):
    session = requests.Session()
    main_url = "https://spotidownloader.com/it"
    try:
        # Step 1: accedi alla home per ottenere eventuali cookie
        session.get(main_url, headers={"User-Agent": "Mozilla/5.0"})
        # Step 2: invia la POST (molti siti usano POST, ma può essere GET)
        resp = session.post(
            main_url,
            data={"url": spotify_url},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        # Step 3: controlla se c'è reCAPTCHA nella risposta
        if "g-recaptcha" in resp.text.lower():
            logger.warning("reCAPTCHA rilevato, download impossibile.")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Cerca il link download mp3 (di solito con testo o href che termina con .mp3)
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if ".mp3" in href:
                return href
        return None
    except Exception as e:
        logger.exception("Errore nell'accesso a SpotiDownloader")
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