"""
Протокол обмена сообщениями для Blender-аддона.

Копия protocol.py из внешнего сервера, но без импорта bpy.
Используется внутри аддона для кодирования/декодирования сообщений.
"""

import json
import struct
from typing import Any, Optional

MAX_MESSAGE_SIZE = 8 * 1024 * 1024  # 8 MB
PROTOCOL_VERSION = 1


def encode_message(message_dict: dict[str, Any]) -> bytes:
    """
    Закодировать сообщение в байты.
    
    Формат: 4 байта (длина big-endian) + JSON (UTF-8)
    """
    json_str = json.dumps(message_dict, ensure_ascii=False, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    
    if len(json_bytes) > MAX_MESSAGE_SIZE:
        raise ValueError(f"Сообщение слишком большое: {len(json_bytes)} > {MAX_MESSAGE_SIZE}")
    
    length_prefix = struct.pack(">I", len(json_bytes))
    return length_prefix + json_bytes


def decode_message(data: bytes) -> dict[str, Any]:
    """Декодировать байты в сообщение."""
    try:
        json_str = data.decode("utf-8")
        return json.loads(json_str)
    except UnicodeDecodeError as e:
        raise ValueError(f"Некорректная кодировка UTF-8: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Некорректный JSON: {e}")


def validate_request(data: dict[str, Any]) -> None:
    """Проверить структуру запроса."""
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
    
    if "command" not in data:
        raise ValueError("Отсутствует command в запросе")
    
    if not isinstance(data["command"], str):
        raise ValueError("command должен быть строкой")
    
    if len(data["command"]) > 100:
        raise ValueError("command слишком длинный (>100 символов)")
