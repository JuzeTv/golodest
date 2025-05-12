import os
import asyncio
import json
import websockets
from PyCharacterAI import get_client
from threading import Thread
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфиг из ENV ────────────────────────────────────────────────────────────
CHAR_ID   = os.environ['CHAR_ID']
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')
PORT      = int(os.environ.get('PORT', 8765))
API_TOKEN = os.environ['API_TOKEN']
# ────────────────────────────────────────────────────────────────────────────────

# Unicode <-> \uXXXX
def encode_unicode(s: str) -> str:
    return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

async def main():
    # 1) Авторизуемся в CharacterAI
    client = await get_client(token=API_TOKEN)
    # nick -> Chat-объект
    chats: dict[str, any] = {}

    # 2) Запускаем WebSocket-сервер на порту PORT
    async def handler(ws, path):
        try:
            async for raw in ws:
                # raw = "Nick;\\u...."
                nick, enc = raw.split(';',1)
                text = decode_unicode(enc)

                # если новой ветки — создаём чат и шлём привет
                if nick not in chats:
                    try:
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    except SessionClosedError:
                        client = await get_client(token=API_TOKEN)
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    chats[nick] = chat_obj
                    greet = greeting.get_primary_candidate().text
                    out = f"{AI_NAME}>{nick}:{greet}"
                    await ws.send(encode_unicode(out))

                # отправляем сообщение в существующий чат
                chat_obj = chats[nick]
                turn = await client.chat.send_message(
                    character_id=CHAR_ID,
                    chat_id=chat_obj.chat_id,
                    message=text,
                    streaming=False
                )
                reply = turn.get_primary_candidate().text
                out = f"{AI_NAME}>{nick}:{reply}"
                await ws.send(encode_unicode(out))

        except websockets.exceptions.ConnectionClosed:
            pass

    server = await websockets.serve(handler, '0.0.0.0', PORT)
    print(f"WebSocket server listening on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
