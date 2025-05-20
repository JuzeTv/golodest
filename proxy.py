# proxy.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── ВСТАВЬТЕ СЮДА СВОИ ДАННЫЕ ──────────────────────────────
CAI_TOKEN    = "b7f78883b597e751f7d8b3bd39bd254124eb3013"
CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"
# ──────────────────────────────────────────────────────────────

app = FastAPI()

# Хранилище chat_id для каждого игрока (по никам)
sessions: Dict[str, str] = {}

class MessageIn(BaseModel):
    payload: str  # формат "Никнейм; Сообщение"

class MessageOut(BaseModel):
    response: str

client = None  # будет инициализирован на старте

@app.on_event("startup")
async def startup_event():
    global client
    # инициализация PyCharacterAI-клиента
    client = await get_client(token=CAI_TOKEN)

@app.post("/chat", response_model=MessageOut)
async def chat(msg: MessageIn):
    # разбираем "Nick; text"
    try:
        nick, text = msg.payload.split(";", 1)
        nick, text = nick.strip(), text.strip()
    except ValueError:
        raise HTTPException(400, "Неверный формат: ожидается 'Никнейм; Сообщение'")

    # получаем или создаём чат для этого ника
    if nick not in sessions:
        chat_obj, _greeting = await client.chat.create_chat(CHARACTER_ID)
        sessions[nick] = chat_obj.chat_id
    else:
        chat_obj = await client.chat.get_chat(CHARACTER_ID, sessions[nick])

    # отправляем сообщение в CharacterAI
    try:
        answer = await client.chat.send_message(
            CHARACTER_ID,
            sessions[nick],
            f"{nick}: {text}"
        )
    except SessionClosedError:
        # если сессия закрыта — создаём заново
        chat_obj, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nick] = chat_obj.chat_id
        answer = await client.chat.send_message(
            CHARACTER_ID,
            sessions[nick],
            f"{nick}: {text}"
        )

    # вытаскиваем текст ответа
    resp_text = answer.get_primary_candidate().text
    return MessageOut(response=resp_text)
