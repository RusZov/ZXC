"""
Типы ошибок для Blender MCP.

Все ошибки наследуются от BlenderMCPError и имеют:
- code: машинно-читаемый код ошибки
- message: понятное сообщение для пользователя
- details: дополнительные данные (опционально)
"""

from typing import Any, Optional


class BlenderMCPError(Exception):
    """Базовый класс всех ошибок Blender MCP."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать ошибку в словарь для JSON-ответа."""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class BlenderNotConnectedError(BlenderMCPError):
    """Blender не подключён или аддон не запущен."""

    def __init__(self, message: str = "Blender не подключён. Убедитесь, что аддон запущен."):
        super().__init__(message, code="BLENDER_NOT_CONNECTED")


class AuthFailedError(BlenderMCPError):
    """Ошибка аутентификации (неверный токен)."""

    def __init__(self, message: str = "Неверный токен аутентификации."):
        super().__init__(message, code="AUTH_FAILED")


class InvalidRequestError(BlenderMCPError):
    """Некорректный формат запроса."""

    def __init__(self, message: str = "Некорректный формат запроса.", details: Optional[dict] = None):
        super().__init__(message, code="INVALID_REQUEST", details=details)


class UnknownCommandError(BlenderMCPError):
    """Команда не найдена в реестре."""

    def __init__(self, command: str):
        super().__init__(
            f"Неизвестная команда: {command}",
            code="UNKNOWN_COMMAND",
            details={"command": command},
        )


class ObjectNotFoundError(BlenderMCPError):
    """Объект не найден в сцене."""

    def __init__(self, object_name: str):
        super().__init__(
            f"Объект '{object_name}' не найден в сцене.",
            code="OBJECT_NOT_FOUND",
            details={"object_name": object_name},
        )


class CollectionNotFoundError(BlenderMCPError):
    """Коллекция не найдена."""

    def __init__(self, collection_name: str):
        super().__init__(
            f"Коллекция '{collection_name}' не найдена.",
            code="COLLECTION_NOT_FOUND",
            details={"collection_name": collection_name},
        )


class MaterialNotFoundError(BlenderMCPError):
    """Материал не найден."""

    def __init__(self, material_name: str):
        super().__init__(
            f"Материал '{material_name}' не найден.",
            code="MATERIAL_NOT_FOUND",
            details={"material_name": material_name},
        )


class FileNotFoundError(BlenderMCPError):
    """Файл не найден."""

    def __init__(self, filepath: str):
        super().__init__(
            f"Файл не найден: {filepath}",
            code="FILE_NOT_FOUND",
            details={"filepath": filepath},
        )


class PathNotAllowedError(BlenderMCPError):
    """Путь находится вне разрешённой директории."""

    def __init__(self, path: str, allowed_root: str):
        super().__init__(
            f"Путь '{path}' находится вне разрешённой директории '{allowed_root}'.",
            code="PATH_NOT_ALLOWED",
            details={"path": path, "allowed_root": allowed_root},
        )


class FileAlreadyExistsError(BlenderMCPError):
    """Файл уже существует и overwrite=False."""

    def __init__(self, filepath: str):
        super().__init__(
            f"Файл уже существует: {filepath}",
            code="FILE_ALREADY_EXISTS",
            details={"filepath": filepath},
        )


class UnsupportedFormatError(BlenderMCPError):
    """Неподдерживаемый формат файла."""

    def __init__(self, format_name: str, supported: list[str]):
        super().__init__(
            f"Неподдерживаемый формат '{format_name}'. Поддерживаются: {', '.join(supported)}.",
            code="UNSUPPORTED_FORMAT",
            details={"format": format_name, "supported": supported},
        )


class UnsupportedInBlenderVersionError(BlenderMCPError):
    """Функция не поддерживается в этой версии Blender."""

    def __init__(
        self,
        feature: str,
        blender_version: tuple[int, int, int],
        alternatives: Optional[list[str]] = None,
    ):
        version_str = ".".join(map(str, blender_version))
        details: dict[str, Any] = {
            "feature": feature,
            "blender_version": version_str,
        }
        if alternatives:
            details["alternatives"] = alternatives
        super().__init__(
            f"Функция '{feature}' не поддерживается в Blender {version_str}.",
            code="UNSUPPORTED_IN_BLENDER_VERSION",
            details=details,
        )


class RenderFailedError(BlenderMCPError):
    """Рендер не удался."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="RENDER_FAILED", details=details)


class ImportFailedError(BlenderMCPError):
    """Импорт модели не удался."""

    def __init__(self, filepath: str, reason: str):
        super().__init__(
            f"Импорт не удался: {filepath}. Причина: {reason}",
            code="IMPORT_FAILED",
            details={"filepath": filepath, "reason": reason},
        )


class ExportFailedError(BlenderMCPError):
    """Экспорт модели не удался."""

    def __init__(self, filepath: str, reason: str):
        super().__init__(
            f"Экспорт не удался: {filepath}. Причина: {reason}",
            code="EXPORT_FAILED",
            details={"filepath": filepath, "reason": reason},
        )


class CommandTimeoutError(BlenderMCPError):
    """Превышено время выполнения команды."""

    def __init__(self, command: str, timeout: float):
        super().__init__(
            f"Превышено время выполнения команды '{command}' ({timeout} сек).",
            code="COMMAND_TIMEOUT",
            details={"command": command, "timeout": timeout},
        )


class BatchLimitExceededError(BlenderMCPError):
    """Превышен лимит команд в batch-запросе."""

    def __init__(self, limit: int, actual: int):
        super().__init__(
            f"Превышен лимит команд в batch-запросе: {actual} > {limit}.",
            code="BATCH_LIMIT_EXCEEDED",
            details={"limit": limit, "actual": actual},
        )


class InternalError(BlenderMCPError):
    """Внутренняя ошибка сервера."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="INTERNAL_ERROR", details=details)
