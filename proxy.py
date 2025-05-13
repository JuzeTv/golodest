# proxy.py
import os
import asyncio
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Настройки из ENV ─────────────────────────────────────────────────────────
CHAR_ID   = os.environ['CHAR_ID']
API_TOKEN = os.environ['API_TOKEN']
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI()

# GET/HEAD /                      ← health-check от Render
@app.get("/", response_class=PlainTextResponse)
@app.head("/", response_class=PlainTextResponse)
async def healthcheck():
    return "OK"

# GET/HEAD /ws                   ← чтобы HEAD/GET на /ws тоже не падали
@app.get("/ws", response_class=PlainTextResponse)
@app.head("/ws", response_class=PlainTextResponse)
async def ws_healthcheck():
    return "OK"

# хранилище чат-веток: nick → Chat
chats: Dict[str, any] = {}
client = None

# при старте инициализируем CharacterAI-клиент
@app.on_event("startup")
async def startup_event():
    global client
    client = await get_client(token=API_TOKEN)

def encode_unicode(s: str) -> str:
    return "".join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape")

# WebSocket-эндпоинт для CC-ПК
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            # формат raw: "Nick;\uXXXX\uYYYY..."
            try:
                nick, enc = raw.split(";", 1)
            except ValueError:
                continue
            text = decode_unicode(enc)

            # создаём ветку, если её нет
            if nick not in chats:
                try:
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                except SessionClosedError:
                    await startup_event()
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                chats[nick] = chat_obj
                greet = greeting.get_primary_candidate().text
                payload = encode_unicode(f"{AI_NAME}>{nick}: {greet}")
                await ws.send_text(payload)

            # отправляем текст и ждём ответа
            chat_obj = chats[nick]
            turn = await client.chat.send_message(
                character_id=CHAR_ID,
                chat_id=chat_obj.chat_id,
                text=text,
                streaming=False
            )
            reply = turn.get_primary_candidate().text
            payload = encode_unicode(f"{AI_NAME}>{nick}: {reply}")
            await ws.send_text(payload)

    except WebSocketDisconnect:
        # клиент отключился, просто завершаем
        pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8765))
    uvicorn.run("proxy:app", host="0.0.0.0", port=port)
