import asyncio, json, time, os
from flask import Flask, request, jsonify
from PyCharacterAI import get_client

app = Flask(__name__)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

client = loop.run_until_complete(get_client(token="b7f78883b597e751f7d8b3bd39bd254124eb3013"))
CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"

sessions = {}         # nickname → chat_id
messages = {}         # nickname → [response1, response2]
player_config = {}    # nickname → настройки
CONFIG_FILE = "player_config.json"

def encode_unicode_escaped(text):
    return text.encode("unicode_escape").decode("ascii")

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(player_config, f, indent=2)

def load_config():
    global player_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            player_config = json.load(f)

load_config()

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    nickname = data.get("nickname")
    text = data.get("text")

    if not nickname or not text:
        return jsonify({"error": "Invalid request"}), 400

    if nickname not in messages:
        messages[nickname] = []

    if nickname not in player_config:
        player_config[nickname] = {
            "color": "aqua",
            "bold": False
        }

    if text.lower().startswith("!настройка"):
        apply_setting(nickname, text)
        save_config()
        messages[nickname].append(format_response(nickname, "Настройка обновлена."))
        return jsonify({"status": "configured"})

    response = loop.run_until_complete(process_message(nickname, text))
    messages[nickname].append(response)
    return jsonify({"status": "ok"})

@app.route("/poll", methods=["GET"])
def poll():
    nickname = request.args.get("nickname")
    if not nickname or nickname not in messages:
        return jsonify([])

    if messages[nickname]:
        return jsonify(messages[nickname].pop(0))
    else:
        return jsonify([])

def apply_setting(nickname, text):
    cfg = player_config[nickname]
    lower = text.lower()

    if "цвет=" in lower:
        val = text.split("цвет=")[1].split()[0]
        cfg["color"] = val

    if "жирный=да" in lower or "bold=yes" in lower:
        cfg["bold"] = True
    if "жирный=нет" in lower or "bold=no" in lower:
        cfg["bold"] = False

def format_response(nickname, message):
    cfg = player_config[nickname]
    bot_prefix = f"Голо-Джон: >{nickname}, "
    full = bot_prefix + message
    text = encode_unicode_escaped(full)

    entry = {
        "text": text,
        "color": cfg.get("color", "aqua")
    }
    if cfg.get("bold"):
        entry["bold"] = True

    return [entry]

async def process_message(nickname, text):
    if nickname not in sessions:
        chat, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nickname] = chat.chat_id

    chat_id = sessions[nickname]
    reply = await client.chat.send_message(CHARACTER_ID, chat_id, text)
    ai_text = reply.get_primary_candidate().text
    return format_response(nickname, ai_text)

@app.route("/")
def home():
    return "CharacterAI Proxy is live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
