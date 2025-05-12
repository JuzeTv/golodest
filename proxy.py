import os
import asyncio
import websockets
from http import HTTPStatus
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError

# ─── Конфигурация из переменных окружения ────────────────────────────────────
CHAR_ID   = os.environ['CHAR_ID']                       # ID вашего персонажа
AI_NAME   = os.environ.get('AI_NAME', 'Голо-Джон')       # Отображаемое имя бота
PORT      = int(os.environ.get('PORT', 8765))            # Порт, на котором слушаем
API_TOKEN = os.environ['API_TOKEN']                      # Ваш API-токен CharacterAI
# ────────────────────────────────────────────────────────────────────────────────

def encode_unicode(s: str) -> str:
    """Преобразует строку в формат \\uXXXX."""
    return ''.join(f"\\u{ord(c):04X}" for c in s)

def decode_unicode(s: str) -> str:
    """Декодирует строку из формата \\uXXXX обратно в обычный текст."""
    return s.encode('utf-8').decode('unicode_escape')

async def main():
    # 1) Аутентифицируемся в CharacterAI
    client = await get_client(token=API_TOKEN)
    # Хранилище активных чатов: nick -> Chat-объект
    chats: dict[str, any] = {}

    # 2) Обработчик не-WebSocket запросов (health-checks)
    async def process_request(path, request_headers):
        connection = request_headers.get('Connection', '')
        upgrade    = request_headers.get('Upgrade', '')
        # Если нет заголовка Upgrade: websocket — считаем это health-check и отвечаем OK
        if 'upgrade' not in connection.lower() or upgrade.lower() != 'websocket':
            return HTTPStatus.OK, [], b'OK'
        # Иначе — это настоящий WebSocket-handshake
        return None  

    # 3) Основной WebSocket-handler
    async def handler(ws, path):
        try:
            async for raw in ws:
                # Формат входящего: "Nick;\\uXXXX..."
                nick, enc_msg = raw.split(';', 1)
                text = decode_unicode(enc_msg)

                # Если новая ветка — создаём чат и шлём привет
                if nick not in chats:
                    try:
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    except SessionClosedError:
                        # При истёкшей сессии — реавторизуемся и повторяем
                        client = await get_client(token=API_TOKEN)
                        chat_obj, greeting = await client.chat.create_chat(CHAR_ID)
                    chats[nick] = chat_obj
                    greet_text = greeting.get_primary_candidate().text
                    payload = f"{AI_NAME}>{nick}:{greet_text}"
                    await ws.send(encode_unicode(payload))

                # Отправляем сообщение в существующий чат и получаем ответ
                chat_obj = chats[nick]
                turn = await client.chat.send_message(
                    character_id=CHAR_ID,
                    chat_id=chat_obj.chat_id,
                    message=text,
                    streaming=False
                )
                reply = turn.get_primary_candidate().text

                # Шлём ответ обратно в CC
                out = f"{AI_NAME}>{nick}:{reply}"
                await ws.send(encode_unicode(out))

        except websockets.exceptions.ConnectionClosed:
            # Клиент отключился — просто выходим
            pass

    # 4) Запускаем WebSocket-сервер с поддержкой health-checks
    server = await websockets.serve(
        handler,
        '0.0.0.0',
        PORT,
        process_request=process_request
    )
    print(f"WebSocket server listening on port {PORT}")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
