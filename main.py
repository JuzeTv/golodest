import asyncio, json, os
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

color_table = {
    "1": "white",
    "2": "red",
    "3": "aqua",
    "4": "green",
    "5": "yellow",
    "6": "blue",
    "7": "light_purple",
    "8": "gray",
    "9": "gold"
}

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
async def chat():
    data = await request.get_json()
    nickname = data.get("nickname", "").lower()
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

    lower = text.lower()

    if lower.startswith("!help"):
        help_text = "Команды:\n"
        help_text += "!set color=<номер> — цвет текста\n"
        help_text += "!set bold=yes|no — жирный текст\n"
        help_text += "\nЦвета:\n"

        for num, color in color_table.items():
            entry = {
                "text": encode_unicode_escaped(f"[{num}] Пример текста цвета {color}"),
                "color": color
            }
            messages[nickname].append([entry])

        messages[nickname].append(format_response(nickname, "Команды отображены."))
        return jsonify({"status": "helped"})

    if lower.startswith("!set "):
        apply_setting(nickname, text)
        save_config()
        messages[nickname].append(format_response(nickname, "Настройки обновлены."))
        return jsonify({"status": "configured"})

    asyncio.create_task(handle_async_message(nickname, text))
    return jsonify({"status": "processing"})

@app.route("/poll", methods=["GET"])
def poll():
    nickname = request.args.get("nickname", "").lower()
    if nickname not in messages:
        return jsonify([])

    if messages[nickname]:
        return jsonify(messages[nickname].pop(0))
    else:
        return jsonify([])

@app.route("/status", methods=["GET"])
def status():
    nickname = request.args.get("nickname", "").lower()
    if nickname in messages and messages[nickname]:
        return jsonify({"ready": True})
    return jsonify({"ready": False})

def apply_setting(nickname, text):
    cfg = player_config[nickname]
    lower = text.lower()

    if "color=" in lower:
        val = text.split("color=")[1].split()[0]
        if val in color_table:
            cfg["color"] = color_table[val]

    if "bold=yes" in lower:
        cfg["bold"] = True
    elif "bold=no" in lower:
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

async def handle_async_message(nickname, text):
    response = await process_message(nickname, text)
    messages[nickname].append(response)

async def process_message(nickname, text):
    if nickname not in sessions:
        chat, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nickname] = chat.chat_id

    chat_id = sessions[nickname]
    user_message = f"{nickname}: {text.lstrip('!')}"
    reply = await client.chat.send_message(CHARACTER_ID, chat_id, user_message)
    ai_text = reply.get_primary_candidate().text
    return format_response(nickname, ai_text)

@app.route("/")
def home():
    return "✅ Голо-Джон работает!"
