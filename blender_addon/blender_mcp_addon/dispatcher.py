"""
Диспетчер команд для выполнения bpy-операций в главном потоке Blender.

Используется CommandDispatcher для обработки команд из очереди.
Все bpy-вызовы происходят только здесь, в главном потоке.
"""

import threading
import queue
from typing import Optional, Any
from dataclasses import dataclass, field


@dataclass
class PendingCommand:
    """Команда, ожидающая выполнения."""
    
    request_id: str
    command: str
    args: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    _event: threading.Event = field(default_factory=threading.Event, repr=False)
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """Дождаться выполнения команды."""
        return self._event.wait(timeout=timeout)
    
    def set_result(self, result: dict[str, Any]) -> None:
        """Установить результат выполнения."""
        self.result = result
        self._event.set()
    
    def set_error(self, code: str, message: str, details: Optional[dict] = None) -> None:
        """Установить ошибку выполнения."""
        self.error = {
            "code": code,
            "message": message,
            "details": details or {},
        }
        self._event.set()


# Реестр разрешённых команд
COMMAND_REGISTRY: dict[str, Any] = {}


def register_command(name: str):
    """Декоратор для регистрации команды."""
    def decorator(func):
        COMMAND_REGISTRY[name] = func
        return func
    return decorator


class CommandDispatcher:
    """
    Диспетчер для выполнения команд в главном потоке Blender.
    
    Получает команды из очереди и выполняет их через зарегистрированные обработчики.
    """
    
    def __init__(self, command_queue: queue.Queue):
        self.command_queue = command_queue
        self._blender_tools = None
    
    def _get_blender_tools(self):
        """Ленивая загрузка BlenderTools."""
        if self._blender_tools is None:
            from .blender_tools import BlenderTools
            self._blender_tools = BlenderTools()
        return self._blender_tools
    
    def execute_command(self, cmd: PendingCommand) -> None:
        """
        Выполнить команду.
        
        Вызывается из главного потока Blender через bpy.app.timers.
        """
        try:
            # Проверить наличие команды в реестре
            if cmd.command not in COMMAND_REGISTRY:
                cmd.set_error(
                    "UNKNOWN_COMMAND",
                    f"Неизвестная команда: {cmd.command}",
                    {"command": cmd.command}
                )
                return
            
            # Получить обработчик
            handler = COMMAND_REGISTRY[cmd.command]
            
            # Выполнить команду
            result = handler(cmd.args)
            cmd.set_result(result)
            
        except Exception as e:
            cmd.set_error(
                "INTERNAL_ERROR",
                str(e),
                {"command": cmd.command, "args": cmd.args}
            )


# Регистрация встроенных команд
@register_command("ping")
def handle_ping(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды ping."""
    import bpy
    from . import get_server_info
    
    info = get_server_info()
    return {
        "blender_version": info["blender_version"],
        "addon_version": info["addon_version"],
        "protocol_version": info["protocol_version"],
    }


@register_command("get_blender_info")
def handle_get_blender_info(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды get_blender_info."""
    from . import get_server_info
    return get_server_info()


@register_command("create_object")
def handle_create_object(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды create_object."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.create_object(
        object_type=args.get("type", "cube"),
        name=args.get("name"),
        location=args.get("location", [0, 0, 0]),
        rotation=args.get("rotation", [0, 0, 0]),
        scale=args.get("scale", [1, 1, 1]),
    )


@register_command("apply_material")
def handle_apply_material(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды apply_material."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.apply_material(
        object_name=args["object_name"],
        base_color=args.get("base_color", [0.8, 0.8, 0.8, 1.0]),
        roughness=args.get("roughness", 0.5),
        metallic=args.get("metallic", 0.0),
        material_name=args.get("material_name"),
    )


@register_command("add_light")
def handle_add_light(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды add_light."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.add_light(
        light_type=args.get("type", "POINT"),
        name=args.get("name"),
        location=args.get("location", [0, 0, 5]),
        energy=args.get("energy", 100.0),
        color=args.get("color", [1, 1, 1]),
    )


@register_command("set_camera")
def handle_set_camera(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды set_camera."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.set_camera(
        location=args.get("location", [0, -10, 5]),
        target=args.get("target"),
        rotation=args.get("rotation"),
        lens=args.get("lens", 35.0),
    )


@register_command("render_scene")
def handle_render_scene(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды render_scene."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.render_scene(
        filepath=args["filepath"],
        resolution_x=args.get("resolution_x", 1920),
        resolution_y=args.get("resolution_y", 1080),
        engine=args.get("engine", "EEVEE"),
        samples=args.get("samples", 128),
        overwrite=args.get("overwrite", True),
    )


@register_command("export_fbx")
def handle_export_fbx(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды export_fbx."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.export_fbx(
        filepath=args["filepath"],
        objects=args.get("objects"),
        apply_transform=args.get("apply_transform", True),
        overwrite=args.get("overwrite", True),
    )


@register_command("export_gltf")
def handle_export_gltf(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды export_gltf."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.export_gltf(
        filepath=args["filepath"],
        objects=args.get("objects"),
        export_format=args.get("export_format", "GLB"),
        overwrite=args.get("overwrite", True),
    )


@register_command("get_scene_info")
def handle_get_scene_info(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды get_scene_info."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.get_scene_info()


@register_command("execute_batch")
def handle_execute_batch(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды execute_batch."""
    tools = CommandDispatcher(None)._get_blender_tools()
    commands = args.get("commands", [])
    stop_on_error = args.get("stop_on_error", True)
    return tools.execute_batch(commands, stop_on_error)


@register_command("transform_object")
def handle_transform_object(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды transform_object."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.transform_object(
        object_name=args["object_name"],
        location=args.get("location"),
        rotation=args.get("rotation"),
        scale=args.get("scale"),
        mode=args.get("mode", "absolute"),
    )


@register_command("delete_objects")
def handle_delete_objects(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды delete_objects."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.delete_objects(args.get("object_names", []))


@register_command("render_preview")
def handle_render_preview(args: dict[str, Any]) -> dict[str, Any]:
    """Обработчик команды render_preview."""
    tools = CommandDispatcher(None)._get_blender_tools()
    return tools.render_preview(
        resolution=args.get("resolution", 512),
        engine=args.get("engine", "EEVEE"),
    )
