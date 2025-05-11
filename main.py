import asyncio
import json
from flask import Flask, request, jsonify
from PyCharacterAI import get_client

app = Flask(__name__)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

client = loop.run_until_complete(get_client(token="b7f78883b597e751f7d8b3bd39bd254124eb3013"))
CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"
# Хранилище состояний
last_message = None
ready = False
sessions = {}

def encode_unicode_escaped(text):
    return text.encode("unicode_escape").decode("ascii")

@app.route("/chat", methods=["POST"])
def chat():
    global last_message, ready
    data = request.get_json()
    nickname = data.get("nickname")
    text = data.get("text")

    if not nickname or not text:
        return jsonify({"error": "invalid"}), 400

    print(f"[{nickname}] {text}")
    response = loop.run_until_complete(process_message(nickname, text))
    last_message = response
    ready = True
    return jsonify({"status": "ok"})

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"ready": ready})

@app.route("/poll", methods=["GET"])
def poll():
    global last_message, ready
    if last_message:
        response = last_message
        last_message = None
        ready = False
        return jsonify(response)
    return jsonify([])

async def process_message(nickname, text):
    if nickname not in sessions:
        chat, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nickname] = chat.chat_id

    chat_id = sessions[nickname]
    reply = await client.chat.send_message(CHARACTER_ID, chat_id, text)
    bot_text = reply.get_primary_candidate().text

    formatted = f"Бот: >{nickname}, {bot_text}"
    escaped = encode_unicode_escaped(formatted)

    return [{"text": escaped, "color": "aqua"}]

@app.route("/")
def home():
    return "✅ Flask-прокси работает"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
