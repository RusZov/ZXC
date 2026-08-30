"""
Протокол обмена сообщениями между MCP-сервером и Blender-аддоном.

Формат сообщения:
- 4 байта: длина сообщения (big-endian)
- N байт: JSON-тело сообщения

Запрос:
{
    "protocol_version": 1,
    "request_id": "uuid",
    "token": "secret-token",
    "command": "create_object",
    "args": {...}
}

Успешный ответ:
{
    "protocol_version": 1,
    "request_id": "тот же uuid",
    "status": "ok",
    "data": {...}
}

Ошибка:
{
    "protocol_version": 1,
    "request_id": "тот же uuid",
    "status": "error",
    "error": {
        "code": "OBJECT_NOT_FOUND",
        "message": "Объект Cube не найден",
        "details": {}
    }
}
"""

import json
import struct
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

MAX_MESSAGE_SIZE = 8 * 1024 * 1024  # 8 MB
PROTOCOL_VERSION = 1


@dataclass
class RequestMessage:
    """Сообщение запроса."""

    command: str
    args: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token: str = ""
    protocol_version: int = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "token": self.token,
            "command": self.command,
            "args": self.args,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequestMessage":
        """Создать из словаря."""
        return cls(
            protocol_version=data.get("protocol_version", PROTOCOL_VERSION),
            request_id=data.get("request_id", str(uuid.uuid4())),
            token=data.get("token", ""),
            command=data["command"],
            args=data.get("args", {}),
        )


@dataclass
class ResponseMessage:
    """Сообщение успешного ответа."""

    request_id: str
    data: dict[str, Any] = field(default_factory=dict)
    protocol_version: int = PROTOCOL_VERSION
    status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "status": self.status,
            "data": self.data,
        }


@dataclass
class ErrorMessage:
    """Сообщение об ошибке."""

    request_id: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    protocol_version: int = PROTOCOL_VERSION
    status: str = "error"

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "status": self.status,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }


def encode_message_to_bytes(message_dict: dict[str, Any]) -> bytes:
    """
    Закодировать сообщение в байты.
    
    Формат: 4 байта (длина) + JSON (UTF-8)
    """
    json_str = json.dumps(message_dict, ensure_ascii=False, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    
    if len(json_bytes) > MAX_MESSAGE_SIZE:
        raise ValueError(f"Сообщение слишком большое: {len(json_bytes)} > {MAX_MESSAGE_SIZE}")
    
    length_prefix = struct.pack(">I", len(json_bytes))
    return length_prefix + json_bytes


def read_exact(sock: Any, count: int, timeout: Optional[float] = None) -> bytes:
    """
    Прочитать ровно count байт из сокета.
    
    TCP может вернуть меньше байт за один вызов recv(), поэтому читаем циклом.
    """
    import socket
    
    sock.settimeout(timeout)
    data = b""
    while len(data) < count:
        try:
            chunk = sock.recv(count - len(data))
            if not chunk:
                raise ConnectionError("Соединение разорвано при чтении")
            data += chunk
        except socket.timeout:
            raise TimeoutError(f"Тайм-аут при чтении {count} байт")
    return data


def decode_message_from_bytes(data: bytes) -> dict[str, Any]:
    """Декодировать байты в сообщение."""
    try:
        json_str = data.decode("utf-8")
        return json.loads(json_str)
    except UnicodeDecodeError as e:
        raise ValueError(f"Некорректная кодировка UTF-8: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Некорректный JSON: {e}")


def validate_message_structure(data: dict[str, Any], expected_type: str) -> None:
    """Проверить структуру сообщения."""
    if not isinstance(data, dict):
        raise ValueError(f"Ожидался dict, получен {type(data).__name__}")
    
    if "protocol_version" not in data:
        raise ValueError("Отсутствует protocol_version")
    
    if data["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError(
            f"Несовместимая версия протокола: {data['protocol_version']} (ожидалась {PROTOCOL_VERSION})"
        )
    
    if "request_id" not in data:
        raise ValueError("Отсутствует request_id")
    
    if expected_type == "request":
        if "command" not in data:
            raise ValueError("Отсутствует command в запросе")
        if not isinstance(data["command"], str):
            raise ValueError("command должен быть строкой")
        if len(data["command"]) > 100:
            raise ValueError("command слишком длинный (>100 символов)")
    
    elif expected_type == "response":
        if "status" not in data:
            raise ValueError("Отсутствует status в ответе")
        if data["status"] not in ("ok", "error"):
            raise ValueError(f"Некорректный status: {data['status']}")
        
        if data["status"] == "ok" and "data" not in data:
            raise ValueError("Отсутствует data в успешном ответе")
        
        if data["status"] == "error":
            if "error" not in data:
                raise ValueError("Отсутствует error в сообщении об ошибке")
            error = data["error"]
            if not isinstance(error, dict):
                raise ValueError("error должен быть объектом")
            if "code" not in error or "message" not in error:
                raise ValueError("error должен содержать code и message")
