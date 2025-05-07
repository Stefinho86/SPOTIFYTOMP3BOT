import vk_api
import logging

def vk_login(login, password):
    vk_session = vk_api.VkApi(login, password)
    try:
        vk_session.auth()
    except vk_api.AuthError as error_msg:
        logging.error(f"Errore login VK: {error_msg}")
        return None
    return vk_session

def vk_audio_search(vk_session, query, max_results=3):
    vk = vk_session.get_api()
    try:
        res = vk.audio.search(q=query, count=max_results, auto_complete=1)
        # Restituisce lista di dict {artist, title, url, duration}
        tracks = []
        for item in res['items']:
            if 'url' in item and item['url']:
                tracks.append({
                    'artist': item['artist'],
                    'title': item['title'],
                    'url': item['url'],
                    'duration': item['duration']
                })
        return tracks
    except Exception as e:
        logging.error(f"Errore ricerca VK: {e}")
        return []