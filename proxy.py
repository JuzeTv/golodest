import os
import asyncio
import json
import websockets
from threading import Thread
from flask import Flask
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфигурация по ENV ───────────────────────────────────────────────────────
CHAR_ID    = os.environ['FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU']      # e.g. "FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU"
AI_NAME    = os.environ.get('AI_NAME', 'Голо-Джон')
PORT       = int(os.environ.get('PORT', 8765))
API_TOKEN  = os.environ['b7f78883b597e751f7d8b3bd39bd254124eb3013']    # ваш API-токен CharacterAI
# ────────────────────────────────────────────────────────────────────────────────

# Flask для health-check (Render требует «web» сервиса)
app = Flask(__name__)
@app.route('/')
def healthcheck():
    return 'OK', 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Unicode-encode/decode (в формате \uXXXX)
def encode_unicode(s: str) -> str:
    return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

async def main():
    # ─── 1) Аутентифицируемся в CharacterAI ────────────────────────────────────
    client = await get_client(token=API_TOKEN)
    # Словарь: nick -> PyCharacterAI.Chat объект
    chats: dict[str, any] = {}

    # ─── 2) Запускаем Flask в фоне ──────────────────────────────────────────────
    Thread(target=run_flask, daemon=True).start()

    # ─── 3) WebSocket-сервер ────────────────────────────────────────────────────
    async def handler(ws, path):
        # Регистрируем нового клиента
        print("New CC connected")
        try:
            async for raw in ws:
                # raw: "Nick;\\u...encoded text..."
                nick, enc_msg = raw.split(';', 1)
                text = decode_unicode(enc_msg)

                # Если ещё нет чата — создаем новую ветку
                if nick not in chats:
                    try:
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    except SessionClosedError:
                        # Сессия могла закрыться, заново аутентифицируем
                        client = await get_client(token=API_TOKEN)
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    chats[nick] = chat_obj
                    # Можно разослать приветствие:
                    greeting_text = greeting.get_primary_candidate().text
                    payload = f"{AI_NAME}>{nick}:{greeting_text}"
                    enc_out = encode_unicode(payload)
                    await ws.send(enc_out)

                # Отправляем сообщение и ждём ответа
                chat_obj = chats[nick]
                turn = await client.chat.send_message(
                    character_id=CHAR_ID,
                    chat_id=chat_obj.chat_id,
                    message=text,
                    streaming=False
                )
                reply = turn.get_primary_candidate().text

                # Формируем и отсылаем ответ всем CC (broadcast)
                out = f"{AI_NAME}>{nick}:{reply}"
                enc_out = encode_unicode(out)
                await ws.send(enc_out)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            print("CC disconnected")

    server = await websockets.serve(handler, '0.0.0.0', PORT)
    print(f"WebSocket server running on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
