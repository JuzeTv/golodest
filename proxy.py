import os
import asyncio
from http import HTTPStatus
import websockets
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфиг через ENV ──────────────────────────────────────────────────────────
CHAR_ID   = os.environ['CHAR_ID']
API_TOKEN = os.environ['API_TOKEN']
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')
PORT      = int(os.environ.get('PORT', 8765))
# ────────────────────────────────────────────────────────────────────────────────

def encode_unicode(s: str) -> str:
    return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

# Словарь для веток чата
chats: dict[str, any] = {}
client = None

async def handler(ws, path):
    global client, chats
    async for raw in ws:
        # raw формат: "Nick;\\uXXXX..."
        try:
            nick, enc = raw.split(';', 1)
        except ValueError:
            continue
        text = decode_unicode(enc)

        # новая ветка?
        if nick not in chats:
            try:
                chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
            except SessionClosedError:
                client = await get_client(token=API_TOKEN)
                chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
            chats[nick] = chat_obj
            greet = greeting.get_primary_candidate().text
            await ws.send(encode_unicode(f"{AI_NAME}>{nick}: {greet}"))

        # отправляем сообщение и ждём ответ
        chat_obj = chats[nick]
        turn = await client.chat.send_message(
            character_id=CHAR_ID,
            chat_id=chat_obj.chat_id,
            text=text,
            streaming=False
        )
        reply = turn.get_primary_candidate().text
        await ws.send(encode_unicode(f"{AI_NAME}>{nick}: {reply}"))

async def process_request(path, request_headers):
    # Любой HTTP-запрос не на /ws сразу 200 OK
    if path != '/ws':
        return HTTPStatus.OK, [], b'OK'
    # Иначе — это WebSocket Upgrade, передаём рукопожатие дальше
    return None

async def main():
    global client
    client = await get_client(token=API_TOKEN)
    server = await websockets.serve(
        handler,
        '0.0.0.0',
        PORT,
        process_request=process_request
    )
    print(f"WebSocket listening on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
