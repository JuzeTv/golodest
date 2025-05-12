import os
import asyncio
import json
import websockets
from flask import Flask, request, jsonify
from threading import Thread
from charai import CharAI

# Переменные окружения
CHAR_ID = os.environ['FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU']
AI_NAME = os.environ.get('AI_NAME', 'Голо-Джон')
PORT = int(os.environ.get('PORT', 8765))
COOKIE_PATH = os.environ.get('COOKIE_PATH', 'cookies.json')

# CharacterAI клиент
client = CharAI(cookie_path=COOKIE_PATH)
# Храним все WebSocket-соединения
clients = set()

# Запускаем Flask только для health-check (если надо)
app = Flask(__name__)
@app.route('/')
def index():
    return 'OK'

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# WebSocket handler
def encode_unicode(s): return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s): return s.encode('utf-8').decode('unicode_escape')

async def handler(ws, _):
    clients.add(ws)
    try:
        async for raw in ws:
            # raw: "Nick;<\u-text>"
            nick, enc = raw.split(';',1)
            text = decode_unicode(enc)
            # отправляем в CharacterAI: "Nick: text"
            resp = client.chat(CHAR_ID, f"{nick}: {text}")
            reply = resp.get('response','')
            # кодируем и шлём всем CC
            out = f"{AI_NAME}>{nick}:{reply}"
            enc_out = encode_unicode(out)
            for c in list(clients):
                await c.send(enc_out)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)

async def main():
    # Запускаем Flask в фоновом потоке
    Thread(target=run_flask, daemon=True).start()
    # WS-сервер
    server = await websockets.serve(handler, '0.0.0.0', PORT)
    print(f"WebSocket server running on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
