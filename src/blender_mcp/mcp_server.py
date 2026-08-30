"""
MCP-сервер для управления Blender.

Использует MCP SDK v2 с высокоуровневым API.
Подключается к Blender через TCP-клиент.
Все логи отправляются в stderr, stdout используется транспортом MCP.
"""

import asyncio
import logging
import sys
from typing import Any, Optional

from mcp.server import MCPServer

from blender_mcp.client import BlenderClient
from blender_mcp.config import ClientConfig
from blender_mcp.errors import BlenderNotConnectedError, InternalError

# Настроить логирование в stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Создать MCP сервер
mcp = MCPServer("blender-mcp")

# Глобальный клиент
_client: Optional[BlenderClient] = None
_client_lock = asyncio.Lock()


def get_client() -> BlenderClient:
    """Получить или создать TCP-клиент."""
    global _client
    if _client is None:
        _client = BlenderClient()
    return _client


async def ensure_blender_connected() -> BlenderClient:
    """Убедиться, что клиент подключён к Blender."""
    client = get_client()
    if not client.is_connected:
        try:
            await client.connect()
        except BlenderNotConnectedError as e:
            logger.error(f"Blender не подключён: {e}")
            raise
    return client


@mcp.tool()
async def ping() -> dict[str, Any]:
    """
    Проверить подключение к Blender.
    
    Возвращает информацию о статусе подключения и версии Blender.
    """
    try:
        client = await ensure_blender_connected()
        result = await client.ping()
        return {
            "status": "connected",
            "blender_version": result.get("blender_version", "unknown"),
            "addon_version": result.get("addon_version", "unknown"),
            "protocol_version": result.get("protocol_version", 1),
        }
    except BlenderNotConnectedError:
        return {
            "status": "disconnected",
            "message": "Blender не подключён. Убедитесь, что аддон запущен в Blender.",
        }


@mcp.tool()
async def get_blender_info() -> dict[str, Any]:
    """
    Получить информацию о Blender и аддоне.
    
    Возвращает версию Blender, версию аддона, статус диспетчера команд.
    """
    try:
        client = await ensure_blender_connected()
        result = await client.get_blender_info()
        return result
    except BlenderNotConnectedError as e:
        return {"error": str(e)}


@mcp.tool()
async def create_object(
    object_type: str = "cube",
    name: Optional[str] = None,
    location: list[float] = [0.0, 0.0, 0.0],
    rotation: list[float] = [0.0, 0.0, 0.0],
    scale: list[float] = [1.0, 1.0, 1.0],
) -> dict[str, Any]:
    """
    Создать 3D объект в сцене Blender.
    
    Args:
        object_type: Тип объекта (cube, sphere, cylinder, cone, plane, torus, empty)
        name: Имя объекта (по умолчанию генерируется автоматически)
        location: Позиция [x, y, z]
        rotation: Вращение в радианах [x, y, z]
        scale: Масштаб [x, y, z]
    """
    client = await ensure_blender_connected()
    args = {
        "type": object_type,
        "location": location,
        "rotation": rotation,
        "scale": scale,
    }
    if name:
        args["name"] = name
    
    result = await client.send_command("create_object", args)
    logger.info(f"Создан объект: {result.get('name', 'unknown')}")
    return result


@mcp.tool()
async def apply_material(
    object_name: str,
    base_color: list[float] = [0.8, 0.8, 0.8, 1.0],
    roughness: float = 0.5,
    metallic: float = 0.0,
    material_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Применить PBR материал к объекту.
    
    Args:
        object_name: Имя объекта
        base_color: Цвет [r, g, b, a] (0-1)
        roughness: Шероховатость (0-1)
        metallic: Металличность (0-1)
        material_name: Имя материала (по умолчанию генерируется)
    """
    client = await ensure_blender_connected()
    args = {
        "object_name": object_name,
        "base_color": base_color,
        "roughness": roughness,
        "metallic": metallic,
    }
    if material_name:
        args["material_name"] = material_name
    
    result = await client.send_command("apply_material", args)
    logger.info(f"Применён материал к {object_name}")
    return result


@mcp.tool()
async def add_light(
    light_type: str = "point",
    name: Optional[str] = None,
    location: list[float] = [0.0, 0.0, 5.0],
    energy: float = 100.0,
    color: list[float] = [1.0, 1.0, 1.0],
) -> dict[str, Any]:
    """
    Добавить источник света в сцену.
    
    Args:
        light_type: Тип света (POINT, SUN, SPOT, AREA)
        name: Имя источника
        location: Позиция [x, y, z]
        energy: Энергия/мощность
        color: Цвет [r, g, b] (0-1)
    """
    client = await ensure_blender_connected()
    args = {
        "type": light_type.upper(),
        "location": location,
        "energy": energy,
        "color": color,
    }
    if name:
        args["name"] = name
    
    result = await client.send_command("add_light", args)
    logger.info(f"Добавлен свет: {result.get('name', 'unknown')}")
    return result


@mcp.tool()
async def set_camera(
    location: list[float] = [0.0, -10.0, 5.0],
    target: Optional[list[float]] = None,
    rotation: Optional[list[float]] = None,
    lens: float = 35.0,
) -> dict[str, Any]:
    """
    Настроить камеру.
    
    Args:
        location: Позиция камеры [x, y, z]
        target: Точка взгляда [x, y, z] (если None, используется rotation)
        rotation: Вращение [x, y, z] в радианах (если target не задан)
        lens: Фокусное расстояние в мм
    """
    client = await ensure_blender_connected()
    args = {
        "location": location,
        "lens": lens,
    }
    if target is not None:
        args["target"] = target
    if rotation is not None:
        args["rotation"] = rotation
    
    result = await client.send_command("set_camera", args)
    logger.info(f"Камера настроена: {result.get('name', 'unknown')}")
    return result


@mcp.tool()
async def render_scene(
    filepath: str,
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    engine: str = "EEVEE",
    samples: int = 128,
    overwrite: bool = True,
) -> dict[str, Any]:
    """
    Выполнить рендер сцены.
    
    Args:
        filepath: Путь для сохранения изображения
        resolution_x: Ширина в пикселях
        resolution_y: Высота в пикселях
        engine: Движок рендера (CYCLES или EEVEE)
        samples: Количество сэмплов (для CYCLES)
        overwrite: Перезаписывать ли существующий файл
    """
    client = await ensure_blender_connected()
    args = {
        "filepath": filepath,
        "resolution_x": resolution_x,
        "resolution_y": resolution_y,
        "engine": engine.upper(),
        "samples": samples,
        "overwrite": overwrite,
    }
    
    # Использовать увеличенный тайм-аут для рендера
    result = await client.send_command("render_scene", args, timeout=300.0)
    logger.info(f"Рендер сохранён: {filepath}")
    return result


@mcp.tool()
async def export_fbx(
    filepath: str,
    objects: Optional[list[str]] = None,
    apply_transform: bool = True,
    overwrite: bool = True,
) -> dict[str, Any]:
    """
    Экспортировать сцену в FBX для Unity.
    
    Args:
        filepath: Путь для сохранения файла
        objects: Список имён объектов (None = все объекты)
        apply_transform: Применить трансформации
        overwrite: Перезаписывать ли файл
    """
    client = await ensure_blender_connected()
    args = {
        "filepath": filepath,
        "apply_transform": apply_transform,
        "overwrite": overwrite,
    }
    if objects:
        args["objects"] = objects
    
    result = await client.send_command("export_fbx", args, timeout=60.0)
    logger.info(f"FBX экспортирован: {filepath}")
    return result


@mcp.tool()
async def export_gltf(
    filepath: str,
    objects: Optional[list[str]] = None,
    export_format: str = "GLB",
    overwrite: bool = True,
) -> dict[str, Any]:
    """
    Экспортировать сцену в glTF/GLB.
    
    Args:
        filepath: Путь для сохранения файла
        objects: Список имён объектов (None = все объекты)
        export_format: Формат (GLB или GLTF)
        overwrite: Перезаписывать ли файл
    """
    client = await ensure_blender_connected()
    args = {
        "filepath": filepath,
        "export_format": export_format.upper(),
        "overwrite": overwrite,
    }
    if objects:
        args["objects"] = objects
    
    result = await client.send_command("export_gltf", args, timeout=60.0)
    logger.info(f"glTF экспортирован: {filepath}")
    return result


@mcp.tool()
async def get_scene_info() -> dict[str, Any]:
    """
    Получить информацию о текущей сцене.
    
    Возвращает список всех объектов с их параметрами.
    """
    client = await ensure_blender_connected()
    result = await client.send_command("get_scene_info")
    return result


@mcp.tool()
async def execute_batch(
    commands: list[dict[str, Any]],
    stop_on_error: bool = True,
) -> dict[str, Any]:
    """
    Выполнить пакет команд.
    
    Args:
        commands: Список команд вида [{"command": "...", "args": {...}}, ...]
        stop_on_error: Остановить при первой ошибке
    
    Пример:
        [
            {"command": "create_object", "args": {"type": "cube"}},
            {"command": "apply_material", "args": {"object_name": "Cube", "base_color": [1,0,0,1]}}
        ]
    """
    client = await ensure_blender_connected()
    args = {
        "commands": commands,
        "stop_on_error": stop_on_error,
    }
    
    result = await client.send_command("execute_batch", args, timeout=120.0)
    logger.info(f"Выполнено batch-команд: {len(commands)}")
    return result


@mcp.tool()
async def transform_object(
    object_name: str,
    location: Optional[list[float]] = None,
    rotation: Optional[list[float]] = None,
    scale: Optional[list[float]] = None,
    mode: str = "absolute",
) -> dict[str, Any]:
    """
    Изменить трансформацию объекта.
    
    Args:
        object_name: Имя объекта
        location: Новая позиция [x, y, z]
        rotation: Новое вращение [x, y, z] в радианах
        scale: Новый масштаб [x, y, z]
        mode: Режим (absolute или relative)
    """
    client = await ensure_blender_connected()
    args = {
        "object_name": object_name,
        "mode": mode,
    }
    if location is not None:
        args["location"] = location
    if rotation is not None:
        args["rotation"] = rotation
    if scale is not None:
        args["scale"] = scale
    
    result = await client.send_command("transform_object", args)
    logger.info(f"Трансформирован объект: {object_name}")
    return result


@mcp.tool()
async def delete_objects(object_names: list[str]) -> dict[str, Any]:
    """
    Удалить объекты из сцены.
    
    Args:
        object_names: Список имён объектов для удаления
    """
    client = await ensure_blender_connected()
    args = {"object_names": object_names}
    
    result = await client.send_command("delete_objects", args)
    logger.info(f"Удалено объектов: {len(object_names)}")
    return result


@mcp.tool()
async def render_preview(
    resolution: int = 512,
    engine: str = "EEVEE",
) -> dict[str, Any]:
    """
    Выполнить быстрый превью-рендер.
    
    Возвращает изображение и метаданные.
    
    Args:
        resolution: Размер стороны в пикселях
        engine: Движок ренера
    """
    client = await ensure_blender_connected()
    args = {
        "resolution": resolution,
        "engine": engine.upper(),
    }
    
    result = await client.send_command("render_preview", args, timeout=60.0)
    logger.info("Превью-рендер выполнен")
    return result


def main_sync() -> None:
    """Точка входа для console script."""
    mcp.run()


if __name__ == "__main__":
    main_sync()
