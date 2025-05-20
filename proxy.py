from fastapi import FastAPI, Request
import json, asyncio
import httpx
from characterai import aiocai

app = FastAPI()

# Загрузка или инициализация данных
try:
    colors = json.load(open("colors.json"))
except FileNotFoundError:
    colors = {}
try:
    sessions = json.load(open("sessions.json"))
except FileNotFoundError:
    sessions = {}

CHAR_ID = "CHARACTER_ID"   # ID персонажа на CharacterAI
client = aiocai.Client("YOUR_TOKEN")  # инициализируем клиент PyCharacterAI

@app.on_event("startup")
async def startup():
    me = await client.get_me()  # получаем информацию о себе
    app.state.me_id = me.id
    # Мы можем заранее открыть соединение, если нужно.

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.body()
    text = data.decode('utf-8')
    if ";" not in text:
        return {"error": "Invalid format"}
    nick, message = text.split(";", 1)

    # Обработка команды цвета
    if message.startswith("!color set="):
        color = message.split("=",1)[1]
        colors[nick] = color
        with open("colors.json","w") as f:
            json.dump(colors, f)  # сохраняем в файл:contentReference[oaicite:14]{index=14}
        return {"status": "color saved"}

    # Обычное сообщение: обращаемся к CharacterAI
    me_id = app.state.me_id
    async with await client.connect() as chat:
        if nick not in sessions:
            # Новая сессия для игрока
            new_chat, answer = await chat.new_chat(CHAR_ID, me_id)  # создаём чат:contentReference[oaicite:15]{index=15}
            sessions[nick] = new_chat.chat_id
            ai_response = answer.text
        else:
            # Существующая сессия
            chat_id = sessions[nick]
            message_obj = await chat.send_message(CHAR_ID, chat_id, message)  # отправляем текст:contentReference[oaicite:16]{index=16}
            ai_response = message_obj.text

    # Сохраняем обновлённые сессии
    with open("sessions.json","w") as f:
        json.dump(sessions, f)

    # Отправляем ответ NPC обратно в Minecraft (HTTP POST)
    mc_url = "http://MC_SERVER_ADDRESS/proxy-response"
    payload = {"message": f">{nick}: {ai_response}", "color": colors.get(nick, "f")}
    async with httpx.AsyncClient() as http_client:
        await http_client.post(mc_url, json=payload)  # асинхронный POST:contentReference[oaicite:17]{index=17}

    return {"status": "message sent"}
