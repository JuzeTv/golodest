# proxy.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from PyCharacterAI import CharacterAI, Client
from PyCharacterAI.enums import ChatRole

app = FastAPI()

# Ваш токен CharacterAI и (опционально) прокси
CAI_TOKEN = os.getenv("CAI_TOKEN")  # поставьте его в ENV

client = Client(token=CAI_TOKEN)
cai = CharacterAI(client)

# Хранилище chat_id для каждого ника
sessions: Dict[str, str] = {}

class MessageIn(BaseModel):
    payload: str  # "Nickname; Сообщение"

class MessageOut(BaseModel):
    response: str  # текст ответа персонажа

@app.post("/chat", response_model=MessageOut)
async def chat(msg: MessageIn):
    try:
        nick, text = msg.payload.split(";", 1)
        nick = nick.strip()
        text = text.strip()
    except ValueError:
        raise HTTPException(400, "Неверный формат, ожидается 'Nickname; Сообщение'")

    # Подготовка формата для CharacterAI: "Nick: сообщение"
    full = f"{nick}: {text}"

    # Получаем или создаём сессию
    if nick not in sessions:
        # Здесь ID вашего персонажа. Узнаётся через cai.get_characters()
        CHARACTER_ID = os.getenv("CHARACTER_ID")
        chat = await cai.create_chat(character=CHARACTER_ID)
        sessions[nick] = chat.chat_id
    else:
        chat = await cai.get_chat(chat_id=sessions[nick])

    # Отправляем от лица игрока
    await chat.send_message(full, author=ChatRole.USER)

    # Получаем последний ответ
    last = await chat.get_latest_response()
    answer = last["text"]  # сам текст ответа

    return MessageOut(response=answer)
