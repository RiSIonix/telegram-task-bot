from flask import Flask, request
import requests
import os
from dotenv import load_dotenv

# Učitaj promenljive iz kod.env
load_dotenv(dotenv_path='kod.env')

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'
ZADATAK_STATUSI = {}  # {status_msg_id: {'zad_msg_id': ..., 'preuzeo': ..., 'zavrseno': ...}}

def posalji_zadatak(chat_id, tekst_zadatka):
    r1 = requests.post(f'{TELEGRAM_API_URL}/sendMessage', json={
        'chat_id': chat_id,
        'text': f'📋 ZADATAK:\n\n{tekst_zadatka}',
        'parse_mode': 'HTML'
    })

    if r1.status_code != 200:
        print("❌ Greška pri slanju zadatka:", r1.text)
        return

    original_msg_id = r1.json()['result']['message_id']

    r2 = requests.post(f'{TELEGRAM_API_URL}/sendMessage', json={
        'chat_id': chat_id,
        'text': '👤 Status: ⏳ Čeka preuzimanje...',
        'reply_markup': {
            'inline_keyboard': [
                [{'text': '✅ Preuzeo zadatak', 'callback_data': 'preuzeo:ID'}],
                [{'text': '🏁 Zadatak završen', 'callback_data': 'zavrseno:ID'}]
            ]
        },
        'parse_mode': 'HTML'
    })

    if r2.status_code == 200:
        status_msg_id = r2.json()['result']['message_id']

        keyboard = {
            'inline_keyboard': [
                [{'text': '✅ Preuzeo zadatak', 'callback_data': f'preuzeo:{status_msg_id}'}],
                [{'text': '🏁 Zadatak završen', 'callback_data': f'zavrseno:{status_msg_id}'}]
            ]
        }

        requests.post(f'{TELEGRAM_API_URL}/editMessageReplyMarkup', json={
            'chat_id': chat_id,
            'message_id': status_msg_id,
            'reply_markup': keyboard
        })

        ZADATAK_STATUSI[status_msg_id] = {
            'zad_msg_id': original_msg_id,
            'preuzeo': None,
            'zavrseno': False
        }
        print("✅ Zadatak i status poslati.")
    else:
        print("❌ Greška pri slanju status poruke:", r2.text)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("📨 Primljeno:", data)

    if "message" in data and "text" in data["message"]:
        message = data["message"]
        chat_id = message["chat"]["id"]
        tekst_poruke = message["text"]
        posalji_zadatak(chat_id, tekst_poruke)
        return 'OK', 200

    elif "callback_query" in data:
        callback = data["callback_query"]
        callback_data = callback["data"]
        akcija, status_msg_id = callback_data.split(":")
        status_msg_id = int(status_msg_id)

        korisnik = callback["from"].get("first_name", "")
        if callback["from"].get("last_name"):
            korisnik += f" {callback['from']['last_name']}"

        status = ZADATAK_STATUSI.get(status_msg_id)
        if not status:
            return 'Status not found', 200

        chat_id = callback["message"]["chat"]["id"]

        if akcija == "preuzeo":
            if status["preuzeo"]:
                posalji_info(chat_id, f"⚠️ Zadatak je već preuzeo {status['preuzeo']}.")
            else:
                status["preuzeo"] = korisnik
                novi_tekst = f'👤 Status: 🧑‍🔧 Preuzeo: <b>{korisnik}</b>'
                izmeni_status(chat_id, status_msg_id, novi_tekst)
                posalji_info(chat_id, f"{korisnik} je preuzeo zadatak.")

        elif akcija == "zavrseno":
            if not status["preuzeo"]:
                posalji_info(chat_id, f"⚠️ Niko još nije preuzeo zadatak.")
            elif status["zavrseno"]:
                posalji_info(chat_id, f"✅ Zadatak je već označen kao završen.")
            else:
                status["zavrseno"] = True
                novi_tekst = f'✅ ZADATAK ZAVRŠEN od: <b>{korisnik}</b>'
                izmeni_status(chat_id, status_msg_id, novi_tekst, disable_buttons=True)
                posalji_info(chat_id, f"{korisnik} je označio zadatak kao završen.")

        requests.post(f'{TELEGRAM_API_URL}/answerCallbackQuery', json={
            'callback_query_id': callback["id"]
        })

        return 'OK', 200

    return 'No message or callback', 200

def izmeni_status(chat_id, message_id, novi_tekst, disable_buttons=False):
    keyboard = None
    if not disable_buttons:
        keyboard = {
            'inline_keyboard': [
                [{'text': '✅ Preuzeo zadatak', 'callback_data': f'preuzeo:{message_id}'}],
                [{'text': '🏁 Zadatak završen', 'callback_data': f'zavrseno:{message_id}'}]
            ]
        }

    requests.post(f'{TELEGRAM_API_URL}/editMessageText', json={
        'chat_id': chat_id,
        'message_id': message_id,
        'text': novi_tekst,
        'parse_mode': 'HTML',
        'reply_markup': keyboard
    })

def posalji_info(chat_id, tekst):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": tekst
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
