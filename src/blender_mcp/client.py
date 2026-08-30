"""
TCP-клиент для подключения к Blender MCP серверу.

Использует асинхронный подход с asyncio для неблокирующей работы.
Поддерживает автоматическое переподключение при разрыве соединения.
"""

import asyncio
import json
import logging
import socket
import struct
from typing import Any, Optional

from blender_mcp.config import ClientConfig
from blender_mcp.errors import (
    AuthFailedError,
    BlenderNotConnectedError,
    CommandTimeoutError,
    InvalidRequestError,
    UnknownCommandError,
    InternalError,
)
from blender_mcp.protocol import (
    encode_message_to_bytes,
    decode_message_from_bytes,
    read_exact,
    validate_message_structure,
    MAX_MESSAGE_SIZE,
    PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)


class BlenderClient:
    """
    Асинхронный TCP-клиент для связи с Blender.
    
    Подключается к TCP-серверу внутри Blender-аддона и передаёт команды.
    Все bpy-операции выполняются в главном потоке Blender через очередь.
    """

    def __init__(self, config: Optional[ClientConfig] = None):
        self.config = config or ClientConfig()
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._reconnect_attempts = 0

    @property
    def is_connected(self) -> bool:
        """Проверить состояние подключения."""
        return self._connected and self._socket is not None

    async def connect(self) -> None:
        """
        Подключиться к Blender серверу.
        
        Raises:
            BlenderNotConnectedError: Если не удалось подключиться.
        """
        if self._connected:
            return
        
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)  # Тайм-аут подключения
            self._socket.connect(self.config.address)
            self._socket.settimeout(None)  # Сбросить тайм-аут для дальнейшей работы
            self._connected = True
            self._reconnect_attempts = 0
            logger.info(f"Подключено к Blender на {self.config.host}:{self.config.port}")
        except (socket.error, ConnectionRefusedError, OSError) as e:
            self._connected = False
            self._socket = None
            raise BlenderNotConnectedError(
                f"Не удалось подключиться к Blender ({self.config.host}:{self.config.port}): {e}"
            )

    async def disconnect(self) -> None:
        """Отключиться от Blender сервера."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            finally:
                self._socket = None
        self._connected = False
        logger.info("Отключено от Blender")

    async def _ensure_connected(self) -> None:
        """Убедиться, что подключение активно. При необходимости переподключиться."""
        if not self.is_connected:
            if self._reconnect_attempts < self.config.max_reconnect_attempts:
                self._reconnect_attempts += 1
                logger.info(f"Попытка переподключения ({self._reconnect_attempts}/{self.config.max_reconnect_attempts})")
                await self.connect()
            else:
                raise BlenderNotConnectedError("Превышено количество попыток переподключения")

    async def send_command(
        self,
        command: str,
        args: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Отправить команду в Blender и получить ответ.
        
        Args:
            command: Имя команды (например, "create_object")
            args: Аргументы команды
            timeout: Тайм-аут выполнения (по умолчанию из конфига)
            
        Returns:
            Данные из успешного ответа
            
        Raises:
            BlenderNotConnectedError: Если Blender не подключён
            CommandTimeoutError: Если превышен тайм-аут
            UnknownCommandError: Если команда неизвестна
            AuthFailedError: Если неверный токен
            InvalidRequestError: Если запрос некорректен
            InternalError: Внутренняя ошибка сервера
        """
        async with self._lock:
            await self._ensure_connected()
            
            if not self._socket:
                raise BlenderNotConnectedError("Сокет не инициализирован")
            
            effective_timeout = timeout or self.config.timeout
            
            # Создать сообщение запроса
            request_data = {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": f"{command}_{asyncio.get_event_loop().time()}",
                "token": self.config.token,
                "command": command,
                "args": args or {},
            }
            
            # Кодировать и отправить
            message_bytes = encode_message_to_bytes(request_data)
            
            try:
                self._socket.sendall(message_bytes)
            except (socket.error, BrokenPipeError, ConnectionResetError) as e:
                self._connected = False
                raise BlenderNotConnectedError(f"Соединение разорвано при отправке: {e}")
            
            # Прочитать ответ
            try:
                response_data = await self._read_response(effective_timeout)
            except TimeoutError:
                raise CommandTimeoutError(command, effective_timeout)
            
            # Проверить структуру ответа
            try:
                validate_message_structure(response_data, "response")
            except ValueError as e:
                raise InvalidRequestError(str(e))
            
            # Обработать статус
            if response_data["status"] == "error":
                error_info = response_data["error"]
                code = error_info.get("code", "INTERNAL_ERROR")
                message = error_info.get("message", "Неизвестная ошибка")
                details = error_info.get("details", {})
                
                error_map = {
                    "AUTH_FAILED": AuthFailedError,
                    "UNKNOWN_COMMAND": UnknownCommandError,
                    "INVALID_REQUEST": InvalidRequestError,
                    "BLENDER_NOT_CONNECTED": BlenderNotConnectedError,
                    "COMMAND_TIMEOUT": CommandTimeoutError,
                }
                
                error_class = error_map.get(code, InternalError)
                if code == "UNKNOWN_COMMAND":
                    raise error_class(command)
                elif code == "COMMAND_TIMEOUT":
                    raise CommandTimeoutError(command, effective_timeout)
                else:
                    raise error_class(message, code, details)
            
            return response_data.get("data", {})

    async def _read_response(self, timeout: float) -> dict[str, Any]:
        """
        Прочитать ответ от сервера.
        
        Использует единый тайм-аут на всю операцию чтения.
        """
        if not self._socket:
            raise BlenderNotConnectedError("Сокет не инициализирован")
        
        # Установить общий тайм-аут на сокет
        self._socket.settimeout(timeout)
        
        try:
            # Прочитать длину сообщения (4 байта)
            length_data = read_exact(self._socket, 4, timeout=timeout)
            message_length = struct.unpack(">I", length_data)[0]
            
            if message_length > MAX_MESSAGE_SIZE:
                raise ValueError(f"Сообщение слишком большое: {message_length} > {MAX_MESSAGE_SIZE}")
            
            if message_length == 0:
                raise ValueError("Пустое сообщение")
            
            # Прочитать тело сообщения
            body_data = read_exact(self._socket, message_length, timeout=timeout)
            
            # Декодировать JSON
            return decode_message_from_bytes(body_data)
            
        except TimeoutError:
            raise
        except (socket.timeout, socket.error, BrokenPipeError, ConnectionResetError) as e:
            self._connected = False
            raise BlenderNotConnectedError(f"Соединение разорвано при чтении: {e}")
        finally:
            self._socket.settimeout(None)  # Сбросить тайм-аут

    async def ping(self) -> dict[str, Any]:
        """Проверить подключение к Blender."""
        return await self.send_command("ping", timeout=5.0)

    async def get_blender_info(self) -> dict[str, Any]:
        """Получить информацию о версии Blender и аддона."""
        return await self.send_command("get_blender_info", timeout=5.0)

    async def close(self) -> None:
        """Закрыть соединение (алиас для disconnect)."""
        await self.disconnect()

    async def __aenter__(self) -> "BlenderClient":
        """Войти в контекстный менеджер."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Выйти из контекстного менеджера."""
        await self.disconnect()
