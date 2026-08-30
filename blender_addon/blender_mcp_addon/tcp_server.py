"""
TCP-сервер для приёма команд от MCP-клиента.

Работает в отдельном потоке, не вызывает bpy напрямую.
Команды помещаются в очередь для обработки в главном потоке Blender.
"""

import socket
import threading
import json
import struct
import logging
import queue
from typing import Optional, Any

from .protocol_helper import (
    encode_message,
    decode_message,
    validate_request,
    PROTOCOL_VERSION,
    MAX_MESSAGE_SIZE,
)
from .dispatcher import CommandDispatcher, PendingCommand

logger = logging.getLogger("blender_mcp.tcp_server")


class ClientHandler(threading.Thread):
    """Поток для обработки одного клиентского подключения."""

    def __init__(
        self,
        sock: socket.socket,
        token: str,
        command_queue: queue.Queue,
        dispatcher: "CommandDispatcher",
    ):
        super().__init__(daemon=True)
        self.sock = sock
        self.token = token
        self.command_queue = command_queue
        self.dispatcher = dispatcher
        self.client_addr = sock.getpeername()

    def run(self) -> None:
        """Обработать клиентское подключение."""
        logger.info(f"Подключение от {self.client_addr}")
        
        try:
            while True:
                # Прочитать длину сообщения
                length_data = self._read_exact(4)
                if not length_data:
                    break
                    
                message_length = struct.unpack(">I", length_data)[0]
                
                if message_length > MAX_MESSAGE_SIZE:
                    self._send_error("MESSAGE_TOO_LARGE", f"Сообщение {message_length} байт превышает лимит {MAX_MESSAGE_SIZE}")
                    continue
                
                # Прочитать тело сообщения
                body_data = self._read_exact(message_length)
                if not body_data:
                    break
                
                # Декодировать JSON
                try:
                    request = json.loads(body_data.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    self._send_error("INVALID_JSON", f"Некорректный JSON: {e}")
                    continue
                
                # Проверить структуру запроса
                try:
                    validate_request(request)
                except ValueError as e:
                    self._send_error("INVALID_REQUEST", str(e))
                    continue
                
                # Проверить токен
                if self.token and request.get("token") != self.token:
                    self._send_error("AUTH_FAILED", "Неверный токен")
                    continue
                
                # Создать команду для очереди
                cmd = PendingCommand(
                    request_id=request["request_id"],
                    command=request["command"],
                    args=request.get("args", {}),
                )
                
                # Поставить в очередь
                self.command_queue.put(cmd)
                
                # Дождаться выполнения
                cmd.wait(timeout=300.0)  # 5 минут максимум
                
                # Отправить ответ
                if cmd.result is not None:
                    self._send_response(cmd.request_id, cmd.result)
                elif cmd.error is not None:
                    self._send_error_response(cmd.request_id, cmd.error)
                else:
                    self._send_error(cmd.request_id, "TIMEOUT", "Превышено время ожидания выполнения")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки клиента {self.client_addr}: {e}")
        finally:
            try:
                self.sock.close()
            except Exception:
                pass
            logger.info(f"Отключение {self.client_addr}")

    def _read_exact(self, count: int) -> Optional[bytes]:
        """Прочитать ровно count байт."""
        data = b""
        while len(data) < count:
            try:
                chunk = self.sock.recv(count - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                return None
            except Exception:
                return None
        return data

    def _send_response(self, request_id: str, data: dict[str, Any]) -> None:
        """Отправить успешный ответ."""
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "status": "ok",
            "data": data,
        }
        self._send_message(response)

    def _send_error_response(self, request_id: str, error: dict[str, Any]) -> None:
        """Отправить ответ с ошибкой."""
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "status": "error",
            "error": error,
        }
        self._send_message(response)

    def _send_error(self, request_id: str, code: str, message: str) -> None:
        """Отправить ошибку."""
        self._send_error_response(request_id, {"code": code, "message": message})

    def _send_message(self, message: dict[str, Any]) -> None:
        """Отправить сообщение клиенту."""
        try:
            encoded = encode_message(message)
            self.sock.sendall(encoded)
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")


class MCPAddonServer:
    """TCP-сервер для MCP-команд."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        command_queue: queue.Queue,
        dispatcher: CommandDispatcher,
    ):
        self.host = host
        self.port = port
        self.token = token
        self.command_queue = command_queue
        self.dispatcher = dispatcher
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.clients: list[ClientHandler] = []
        self._lock = threading.Lock()

    def run(self) -> None:
        """Запустить сервер."""
        logger.info(f"Запуск сервера на {self.host}:{self.port}")
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(1.0)  # Для возможности остановки
        self.running = True
        
        logger.info(f"Сервер слушает {self.host}:{self.port}")
        
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                client_sock.settimeout(60.0)
                
                handler = ClientHandler(
                    client_sock,
                    self.token,
                    self.command_queue,
                    self.dispatcher,
                )
                handler.start()
                
                with self._lock:
                    self.clients.append(handler)
                    
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    logger.error("Ошибка сокета сервера")
                break
            except Exception as e:
                logger.error(f"Ошибка accept: {e}")
                break

    def stop(self) -> None:
        """Остановить сервер."""
        logger.info("Остановка сервера")
        self.running = False
        
        # Закрыть серверный сокет
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        
        # Закрыть клиентские подключения
        with self._lock:
            for client in self.clients:
                try:
                    client.sock.close()
                except Exception:
                    pass
            self.clients.clear()
        
        logger.info("Сервер остановлен")

    def get_connections_count(self) -> int:
        """Получить количество активных подключений."""
        with self._lock:
            return len([c for c in self.clients if c.is_alive()])
