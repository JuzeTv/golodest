import os, asyncio, re
from queue import Queue
from threading import Thread
from typing import Dict
from http import HTTPStatus
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from mcrcon import MCRcon
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфиг через ENV ─────────────────────────────────────────────────────────
RCON_HOST     = os.environ['RCON_HOST']
RCON_PORT     = int(os.environ.get('RCON_PORT', 25737))
RCON_PASS     = os.environ['RCON_PASS']
CHAR_ID       = os.environ['CHAR_ID']
API_TOKEN     = os.environ['API_TOKEN']
AI_NAME       = os.environ.get('AI_NAME', 'Голо-Джон')
WS_PORT       = int(os.environ.get('PORT', 8765))
POLL_LOGS_CMD = os.environ.get('POLL_LOGS_CMD', 'logs last')
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI()
chat_re = re.compile(r'^<([^>]+)>\s*!(.+)$')

# health-checks:
@app.get("/", response_class=PlainTextResponse)
@app.head("/", response_class=PlainTextResponse)
async def hc(): return "OK"

# очередь никнеймов
signal_queue: "Queue[str]" = Queue()
# все WS клиенты
clients: set[WebSocket] = set()
# память веток чата
chats: Dict[str, any] = {}
# CharacterAI client
client = None

@app.on_event("startup")
async def startup():
    global client
    client = await get_client(token=API_TOKEN)
    # фоновый RCON-пуллер в отдельном потоке
    Thread(target=lambda: asyncio.run(rcon_worker()), daemon=True).start()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            # ждем сигнал в формате "Nick"
            raw = await ws.receive_text()
            signal_queue.put(raw)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)

def encode_unicode(s: str) -> str:
    return "".join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

async def rcon_worker():
    """Постоянно ждем сигналы, читаем логи RCON и пушим ответы."""
    global client, chats
    # подключаем CharacterAI, RCON в одном потоке
    async with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as rcon:
        while True:
            nick = signal_queue.get()  # блокирующий
            # читаем последние строки лога
            resp = rcon.command(POLL_LOGS_CMD)
            text = None
            for line in reversed(resp.splitlines()):
                m = chat_re.match(line)
                if m and m.group(1) == nick:
                    text = m.group(2).strip()
                    break
            if not text:
                continue
            # ветка чата
            if nick not in chats:
                try:
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                except SessionClosedError:
                    client = await get_client(token=API_TOKEN)
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                chats[nick] = chat_obj
            # шлём текст в AI
            chat_obj = chats[nick]
            turn = await client.chat.send_message(
                character_id=CHAR_ID,
                chat_id=chat_obj.chat_id,
                text=text, streaming=False
            )
            reply = turn.get_primary_candidate().text
            payload = encode_unicode(f"{AI_NAME}>{nick}: {reply}")
            # пуш всем WS клиентам
            for ws in list(clients):
                try:
                    await ws.send_text(payload)
                except:
                    clients.discard(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy:app", host="0.0.0.0", port=WS_PORT)
