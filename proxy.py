import json
import asyncio
from fastapi import FastAPI, Request
from PyCharacterAI import Client
import httpx

app = FastAPI()

# Загрузка или инициализация данных
try:
    with open("colors.json", "r") as f:
        colors = json.load(f)
except FileNotFoundError:
    colors = {}

try:
    with open("sessions.json", "r") as f:
        sessions = json.load(f)
except FileNotFoundError:
    sessions = {}

CHARACTER_ID = "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"  # Замените на ID вашего персонажа
TOKEN = "b7f78883b597e751f7d8b3bd39bd254124eb3013"  # Замените на ваш токен CharacterAI
MC_SERVER_URL = "http://pulsar.minerent.net:25609/proxy-response"  # Замените на URL вашего Minecraft-сервера

client = Client()

@app.on_event("startup")
async def startup_event():
    await client.authenticate(TOKEN)
    me = await client.account.fetch_me()
    app.state.me_id = me.id

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.body()
    text = data.decode('utf-8')
    if ";" not in text:
        return {"error": "Invalid format"}
    nick, message = text.split(";", 1)

    # Обработка команды изменения цвета
    if message.startswith("!color set="):
        color = message.split("=", 1)[1]
        colors[nick] = color
        with open("colors.json", "w") as f:
            json.dump(colors, f)
        return {"status": "color saved"}

    # Форматирование сообщения для CharacterAI
    formatted_message = f"{nick}: {message}"

    # Получение или создание сессии чата
    if nick not in sessions:
        chat, _ = await client.chat.create_chat(CHARACTER_ID)
        sessions[nick] = chat.external_id
        with open("sessions.json", "w") as f:
            json.dump(sessions, f)
    else:
        chat = await client.chat.get_chat(CHARACTER_ID, history_external_id=sessions[nick])

    # Отправка сообщения и получение ответа
    response = await chat.send(formatted_message)
    ai_response = response['replies'][0]['text']

    # Отправка ответа обратно в Minecraft
    payload = {
        "message": f">{nick}: {ai_response}",
        "color": colors.get(nick, "f")
    }
    async with httpx.AsyncClient() as http_client:
        await http_client.post(MC_SERVER_URL, json=payload)

    return {"status": "message sent"}
