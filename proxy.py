import os
import asyncio
import json
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

@app.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return "OK"

# nick → Chat-объект
chats: Dict[str, any] = {}

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
            nick, enc = raw.split(";", 1)
            text = decode_unicode(enc)

            if nick not in chats:
                try:
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                except SessionClosedError:
                    await startup_event()
                    chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                chats[nick] = chat_obj

                greet = greeting.get_primary_candidate().text
                payload = encode_unicode(f"{AI_NAME}>{nick}:{greet}")
                # обёртываем в JSON-строку
                await ws.send_text(json.dumps(payload))

            chat_obj = chats[nick]
            turn = await client.chat.send_message(
                character_id=CHAR_ID,
                chat_id=chat_obj.chat_id,
                text=text,
                streaming=False
            )
            reply = turn.get_primary_candidate().text
            payload = encode_unicode(f"{AI_NAME}>{nick}:{reply}")
            await ws.send_text(json.dumps(payload))

    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8765)))
