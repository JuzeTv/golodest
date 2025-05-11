import asyncio, json, os
from flask import Flask, request, jsonify
from PyCharacterAI import get_client

app = Flask(__name__)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

client = loop.run_until_complete(get_client(token="b7f78883b597e751f7d8b3bd39bd254124eb3013"))
CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"

sessions = {}
messages = {}
player_config = {}
pending_tasks = {}  # nickname → asyncio.Task
CONFIG_FILE = "player_config.json"

COLOR_MAP = {
    "black": "black", "dark_blue": "dark_blue", "dark_green": "dark_green",
    "dark_aqua": "dark_aqua", "dark_red": "dark_red", "dark_purple": "dark_purple",
    "gold": "gold", "gray": "gray", "dark_gray": "dark_gray", "blue": "blue",
    "green": "green", "aqua": "aqua", "red": "red", "light_purple": "light_purple",
    "yellow": "yellow", "white": "white"
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
def chat():
    data = request.get_json()
    nickname = data.get("nickname", "").lower()
    text = data.get("text", "").strip()

    if not nickname or not text:
        return jsonify({"error": "Invalid request"}), 400

    if nickname not in messages:
        messages[nickname] = []

    if nickname not in player_config:
        player_config[nickname] = {
            "color": "aqua",
            "bold": False
        }

    # === Handle settings command ===
    if text.startswith("!settings"):
        apply_setting(nickname, text)
        save_config()
        messages[nickname].append(format_response(nickname, "Settings updated.", system=True))
        return jsonify({"status": "configured"})

    # === Handle help command ===
    if text.startswith("!help"):
        help_text = (
            "Available commands:\n"
            "!help — show this help message\n"
            "!settings color=<color> — set message color\n"
            "!settings bold=yes|no — toggle bold style\n"
            "Example: !settings color=red bold=yes"
        )
        messages[nickname].append(format_response(nickname, help_text, system=True))
        return jsonify({"status": "help"})

    # === Queue message for async processing ===
    async def handle():
        response = await process_message(nickname, text)
        messages[nickname].append(response)

    if nickname not in pending_tasks or pending_tasks[nickname].done():
        pending_tasks[nickname] = loop.create_task(handle())

    return jsonify({"status": "accepted"})

@app.route("/poll", methods=["GET"])
def poll():
    nickname = request.args.get("nickname", "").lower()
    if nickname in messages and messages[nickname]:
        return jsonify(messages[nickname].pop(0))
    return jsonify([])

@app.route("/status", methods=["GET"])
def status():
    nickname = request.args.get("nickname", "").lower()
    if nickname in messages and messages[nickname]:
        return jsonify({"ready": True})
    return jsonify({"ready": False})

def apply_setting(nickname, text):
    cfg = player_config[nickname]
    parts = text.split()
    for part in parts:
        if "color=" in part:
            color = part.split("=", 1)[1].lower()
            if color in COLOR_MAP:
                cfg["color"] = COLOR_MAP[color]
        if "bold=" in part:
            val = part.split("=", 1)[1].lower()
            if val in ("yes", "true", "on"):
                cfg["bold"] = True
            elif val in ("no", "false", "off"):
                cfg["bold"] = False

def format_response(nickname, message, system=False):
    cfg = player_config[nickname]
    prefix = f"Голо-Джон: >{nickname}, "
    full = prefix + message
    text = encode_unicode_escaped(full)

    entry = {
        "text": text,
        "color": cfg.get("color", "aqua")
    }
    if cfg.get("bold"):
        entry["bold"] = True
    if system:
        entry["system"] = True
    return [entry]

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
