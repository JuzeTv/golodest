import os
import asyncio
from http import HTTPStatus
import websockets
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# — Конфиг из ENV —
CHAR_ID   = os.environ['CHAR_ID']          # FzR07mdYrvSNH57vhc3ttvF4ZA96tKuRnyiNNzTfzlU
API_TOKEN = os.environ['API_TOKEN']        # b7f78883b597e751f7d8b3bd39bd254124eb3013
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')
PORT      = int(os.environ.get('PORT', 8765))
# ————————

def encode_unicode(s: str) -> str:
    return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    return s.encode('utf-8').decode('unicode_escape')

async def handler(ws, path):
    # Будем кэшировать чат-ветки по нику
    global client, chats
    async for raw in ws:
        try:
            nick, enc = raw.split(';', 1)
        except ValueError:
            continue  # некорректный формат — игнор
        text = decode_unicode(enc)

        # создаём ветку, если новой
        if nick not in chats:
            try:
                chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
            except SessionClosedError:
                client = await get_client(token=API_TOKEN)
                chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
            chats[nick] = chat_obj
            # шлём приветствие
            greet = greeting.get_primary_candidate().text
            payload = encode_unicode(f"{AI_NAME}>{nick}: {greet}")
            await ws.send(payload)

        # шлём сообщение игрока и ждём ответ
        chat_obj = chats[nick]
        turn = await client.chat.send_message(
            character_id=CHAR_ID,
            chat_id=chat_obj.chat_id,
            text=text,
            streaming=False
        )
        reply = turn.get_primary_candidate().text
        payload = encode_unicode(f"{AI_NAME}>{nick}: {reply}")
        await ws.send(payload)

async def process_request(path, request_headers):
    # Ловим HTTP GET/HEAD от Render и отвечаем 200 OK
    conn = request_headers.get('Connection', '')
    upg  = request_headers.get('Upgrade', '')
    if 'upgrade' not in conn.lower() or upg.lower() != 'websocket':
        return HTTPStatus.OK, [], b'OK'
    return None

async def main():
    global client, chats
    client = await get_client(token=API_TOKEN)
    chats = {}
    server = await websockets.serve(
        handler, '0.0.0.0', PORT,
        process_request=process_request
    )
    print(f"WS server listening on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    # запускаем
    asyncio.run(main())
