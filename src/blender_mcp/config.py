"""
Конфигурация клиента для подключения к Blender.

Поддерживает переменные окружения:
- BLENDER_MCP_HOST (по умолчанию 127.0.0.1)
- BLENDER_MCP_PORT (по умолчанию 9999)
- BLENDER_MCP_TOKEN (по умолчанию пустой, генерируется при необходимости)
- BLENDER_MCP_TIMEOUT (по умолчанию 60.0)
- BLENDER_MCP_OUTPUT_DIR (по умолчанию ~/blender_mcp_output)
"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ClientConfig:
    """Конфигурация подключения к Blender MCP серверу."""

    host: str = field(default_factory=lambda: os.environ.get("BLENDER_MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("BLENDER_MCP_PORT", "9999")))
    token: str = field(default_factory=lambda: os.environ.get("BLENDER_MCP_TOKEN", ""))
    timeout: float = field(default_factory=lambda: float(os.environ.get("BLENDER_MCP_TIMEOUT", "60.0")))
    output_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("BLENDER_MCP_OUTPUT_DIR", "~/blender_mcp_output")).expanduser()
    )
    max_reconnect_attempts: int = 1
    max_message_size: int = 8 * 1024 * 1024  # 8 MB
    long_command_timeout: float = 300.0  # Для рендера и импорта/экспорта

    def __post_init__(self):
        """Валидация и настройка конфигурации после инициализации."""
        if not self.token:
            self.token = self._generate_token()
        
        self.output_dir = self.output_dir.expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_token(self) -> str:
        """Генерация безопасного токена."""
        return secrets.token_urlsafe(32)

    @property
    def address(self) -> tuple[str, int]:
        """Вернуть адрес как кортеж (host, port)."""
        return (self.host, self.port)

    def mask_token(self) -> str:
        """Вернуть замаскированный токен для логирования."""
        if not self.token:
            return "<empty>"
        if len(self.token) <= 4:
            return "****"
        return f"{self.token[:2]}...{self.token[-2:]}"
