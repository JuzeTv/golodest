import os
import asyncio
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфигурация через ENV ────────────────────────────────────────────────────
CHAR_ID   = os.environ['CHAR_ID']                    # ваш CharacterAI character_id
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')    # отображаемое имя бота
API_TOKEN = os.environ['API_TOKEN']                  # ваш API-токен CharacterAI
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI()

# Health-check для Render (любой HTTP GET на "/")
@app.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return "OK"

# Хранилище чатов: nick → PyCharacterAI.Chat объект
chats: Dict[str, any] = {}

# Сделаем клиент один раз при старте
@app.on_event("startup")
async def startup_event():
    global client
    client = await get_client(token=API_TOKEN)

def encode_unicode(s: str) -> str:
    return "".join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape")

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            # raw формат: "Nick;\\uXXXX..."
            nick, enc = raw.split(";", 1)
            text = decode_unicode(enc)

            # Новая ветка?
            if nick not in chats:
                try:
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                except SessionClosedError:
                    # сессия закончилась — переинициализируем client
                    await startup_event()
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                chats[nick] = chat_obj

                # шлём начальное приветствие
                greet = greeting.get_primary_candidate().text
                await ws.send_text(encode_unicode(f"{AI_NAME}>{nick}:{greet}"))

            # Отправляем сообщение игрока
            chat_obj = chats[nick]
            turn = await client.chat.send_message(
                character_id=CHAR_ID,
                chat_id=chat_obj.chat_id,
                message=text,
                streaming=False
            )
            reply = turn.get_primary_candidate().text
            await ws.send_text(encode_unicode(f"{AI_NAME}>{nick}:{reply}"))

    except WebSocketDisconnect:
        # игрок отключился — уходим без ошибки
        pass
