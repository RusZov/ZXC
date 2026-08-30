"""
Blender MCP Server - управление Blender через Model Context Protocol.

Пакет предоставляет:
- Внешний MCP-сервер для подключения к AI-клиентам
- TCP-клиент для связи с Blender
- Протокол обмена сообщениями
- Схемы данных и типы ошибок
"""

__version__ = "0.1.0"
__protocol_version__ = 1

from blender_mcp.protocol import (
    RequestMessage,
    ResponseMessage,
    ErrorMessage,
    encode_message_to_bytes,
    decode_message_from_bytes,
    MAX_MESSAGE_SIZE,
)
from blender_mcp.client import BlenderClient
from blender_mcp.config import ClientConfig
from blender_mcp.errors import (
    BlenderMCPError,
    BlenderNotConnectedError,
    AuthFailedError,
    InvalidRequestError,
    UnknownCommandError,
    ObjectNotFoundError,
    CommandTimeoutError,
)

__all__ = [
    "__version__",
    "__protocol_version__",
    "RequestMessage",
    "ResponseMessage",
    "ErrorMessage",
    "encode_message_to_bytes",
    "decode_message_from_bytes",
    "MAX_MESSAGE_SIZE",
    "BlenderClient",
    "ClientConfig",
    "BlenderMCPError",
    "BlenderNotConnectedError",
    "AuthFailedError",
    "InvalidRequestError",
    "UnknownCommandError",
    "ObjectNotFoundError",
    "CommandTimeoutError",
]
