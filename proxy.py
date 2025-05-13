# proxy.py
import os
import re
import asyncio
from typing import Dict
from mcrcon import MCRcon
from http import HTTPStatus
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфиг из ENV ─────────────────────────────────────────────────────────────
RCON_HOST     = os.environ['RCON_HOST']
RCON_PORT     = int(os.environ.get('RCON_PORT', 25575))
RCON_PASS     = os.environ['RCON_PASS']
CHAR_ID       = os.environ['CHAR_ID']
API_TOKEN     = os.environ['API_TOKEN']
AI_NAME       = os.environ.get('AI_NAME', 'Голо-Джон')
WS_PORT       = int(os.environ.get('PORT', 8765))
POLL_LOGS_CMD = os.environ.get('POLL_LOGS_CMD', 'logs last')
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI()
chat_re = re.compile(r'^<([^>]+)>\s*!(.+)$')

# Для WebSocket
clients: set[WebSocket] = set()
# Для хранения чат-веток
chats: Dict[str, any] = {}
# RCON-клиент и CharacterAI-клиент
rcon: MCRcon | None = None
client = None

@app.get("/", response_class=PlainTextResponse)
@app.head("/", response_class=PlainTextResponse)
async def healthcheck():
    return "OK"

@app.on_event("startup")
async def startup():
    global rcon, client
    # 1) Подключаемся к CharacterAI
    client = await get_client(token=API_TOKEN)
    # 2) Создаём RCON в основном потоке
    rcon = MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT)
    rcon.connect()
    print("RCON connected")
    # 3) Запускаем задачу опроса логов
    asyncio.create_task(rcon_worker())

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            # raw = "Nick"
            nick = raw
            # Кладём в очередь обработки: просто вызываем сразу
            # Обрабатываем на лету, без отдельной очереди
            await process_player(nick)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)

def encode_unicode(s: str) -> str:
    return "".join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

async def process_player(nick: str):
    """
    Получаем последнее !-сообщение от nick из RCON-логов и шлём в CharacterAI и обратно.
    """
    global rcon, client, chats
    # 1) Читаем логи в executor, чтобы не блокировать loop
    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(None, rcon.command, POLL_LOGS_CMD)
    text = None
    for line in reversed(resp.splitlines()):
        m = chat_re.match(line)
        if m and m.group(1) == nick:
            text = m.group(2).strip()
            break
    if not text:
        return
    # 2) Ветка чата
    if nick not in chats:
        try:
            chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
        except SessionClosedError:
            client = await get_client(token=API_TOKEN)
            chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
        chats[nick] = chat_obj
    chat_obj = chats[nick]
    # 3) Отправляем текст в AI
    turn = await client.chat.send_message(
        character_id=CHAR_ID,
        chat_id=chat_obj.chat_id,
        text=text,
        streaming=False
    )
    reply = turn.get_primary_candidate().text
    # 4) Кодируем и отправляем всем WS-клиентам
    payload = encode_unicode(f"{AI_NAME}>{nick}: {reply}")
    for ws in list(clients):
        try:
            await ws.send_text(payload)
        except:
            clients.discard(ws)

async def rcon_worker():
    """
    Фоновый патруль очереди: ничего не делает,
    поскольку обрабатываем сразу при ws.receive.
    Можно здесь реализовать таймауты или пулл/queue.
    """
    # Просто держим RCON открыт
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy:app", host="0.0.0.0", port=WS_PORT)
