# proxy.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

app = FastAPI()

CAI_TOKEN    = os.getenv("CAI_TOKEN")
CHARACTER_ID = os.getenv("CHARACTER_ID")
sessions: Dict[str, str] = {}  # nick → chat_id

class MessageIn(BaseModel):
    payload: str  # "Nickname; Сообщение"

class MessageOut(BaseModel):
    response: str

client = None

@app.on_event("startup")
async def startup_event():
    global client
    # создаём и аутентифицируем клиента один раз
    client = await get_client(token=CAI_TOKEN)

@app.post("/chat", response_model=MessageOut)
async def chat(msg: MessageIn):
    try:
        nick, text = msg.payload.split(";", 1)
        nick, text = nick.strip(), text.strip()
    except ValueError:
        raise HTTPException(400, "Неверный формат, ожидается 'Nickname; Сообщение'")

    # создаём новую сессию для никнейма или берём уже существующую
    if nick not in sessions:
        chat_obj, greeting = await client.chat.create_chat(CHARACTER_ID)
        sessions[nick] = chat_obj.chat_id
    else:
        chat_obj = await client.chat.get_chat(CHARACTER_ID, sessions[nick])

    # отправляем сообщение от игрока (он и так идёт от USER)
    try:
        answer = await client.chat.send_message(
            CHARACTER_ID,
            sessions[nick],
            f"{nick}: {text}"
        )
    except SessionClosedError:
        # если сессия закрыта, можно заново создать
        chat_obj, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nick] = chat_obj.chat_id
        answer = await client.chat.send_message(
            CHARACTER_ID,
            sessions[nick],
            f"{nick}: {text}"
        )

    # берём основной кандидат
    resp_text = answer.get_primary_candidate().text
    return MessageOut(response=resp_text)
