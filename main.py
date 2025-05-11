import asyncio
import json
from flask import Flask, request, jsonify
from PyCharacterAI import get_client

app = Flask(__name__)
loop = asyncio.get_event_loop()
client = loop.run_until_complete(get_client(token="b7f78883b597e751f7d8b3bd39bd254124eb3013"))
CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"

# 💾 Словарь сессий: nickname → chat_id
sessions = {}

last_message = None

def encode_unicode_escaped(text):
    return text.encode('unicode_escape').decode('ascii')


@app.route("/chat", methods=["POST"])
def chat():
    global last_message

    data = request.json
    nickname = data.get("nickname")
    text = data.get("text")

    if not nickname or not text:
        return jsonify({"error": "Invalid request"}), 400

    # 🧠 Отправляем асинхронно
    response = loop.run_until_complete(process_message(nickname, text))

    # Сохраняем ответ
    last_message = response
    return jsonify({"status": "ok"})


@app.route("/poll", methods=["GET"])
def poll():
    global last_message

    if last_message:
        response = last_message
        last_message = None
        return jsonify(response)
    else:
        return jsonify([])


async def process_message(nickname, text):
    # 🔁 Ищем существующую сессию
    if nickname not in sessions:
        print(f"[Flask] Creating new chat session for: {nickname}")
        chat, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nickname] = chat.chat_id
    else:
        print(f"[Flask] Continuing chat for: {nickname}")

    chat_id = sessions[nickname]
    answer = await client.chat.send_message(CHARACTER_ID, chat_id, text)
    bot_text = answer.get_primary_candidate().text

    final = f"Бот: >{nickname}, {bot_text}"
    escaped = encode_unicode_escaped(final)

    return [{"text": escaped, "color": "aqua"}]


@app.route("/")
def home():
    return "✅ Flask-прокси работает"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
