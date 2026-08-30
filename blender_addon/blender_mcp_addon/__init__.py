"""
Blender MCP Addon - сервер для управления Blender через MCP протокол.

Аддон запускает TCP-сервер, который принимает команды от внешнего MCP-сервера.
Все bpy-операции выполняются в главном потоке Blender через bpy.app.timers.

Установка:
1. Edit -> Preferences -> Add-ons -> Install from Disk
2. Выбрать blender_mcp_addon.zip
3. Активировать галочкой
4. Открыть панель MCP в 3D Viewport -> Sidebar -> MCP
5. Нажать Start Server
"""

bl_info = {
    "name": "Blender MCP Server",
    "author": "Blender MCP Contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > MCP",
    "description": "MCP сервер для управления Blender через AI",
    "category": "Interface",
}

import bpy
import logging
import threading
import queue
from typing import Optional, Any

from .tcp_server import MCPAddonServer
from .dispatcher import CommandDispatcher, PendingCommand
from .ui import MCP_PT_main_panel, MCP_OT_start_server, MCP_OT_stop_server, MCP_OT_ping_server

# Глобальные переменные модуля
_mcp_server: Optional[MCPAddonServer] = None
_command_queue: queue.Queue = queue.Queue()
_dispatcher: Optional[CommandDispatcher] = None
_logger: Optional[logging.Logger] = None

# Состояние для отображения в UI
class ServerState:
    status: str = "STOPPED"  # STOPPED, STARTING, RUNNING, ERROR
    host: str = "127.0.0.1"
    port: int = 9999
    token: str = ""
    last_error: str = ""
    last_command: str = ""
    connections_count: int = 0
    queue_size: int = 0

_state = ServerState()


def get_logger() -> logging.Logger:
    """Получить логгер аддона."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("blender_mcp")
        _logger.setLevel(logging.INFO)
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            _logger.addHandler(handler)
    return _logger


def get_state() -> ServerState:
    """Получить текущее состояние сервера."""
    return _state


def process_command_queue() -> float:
    """
    Обработать очередь команд в главном потоке Blender.
    
    Вызывается через bpy.app.timers.register().
    Возвращает интервал до следующего вызова (0.01 сек).
    """
    global _dispatcher
    
    if _dispatcher is None:
        return 0.01
    
    # Обработать не более 5 команд за один проход
    processed = 0
    max_per_cycle = 5
    
    while processed < max_per_cycle and not _command_queue.empty():
        try:
            cmd = _command_queue.get_nowait()
            if isinstance(cmd, PendingCommand):
                _dispatcher.execute_command(cmd)
                processed += 1
        except queue.Empty:
            break
        except Exception as e:
            get_logger().error(f"Ошибка при выполнении команды: {e}")
    
    return 0.01  # Вызывать каждые 10 мс


def start_server(host: str = "127.0.0.1", port: int = 9999, token: str = "") -> bool:
    """
    Запустить TCP-сервер.
    
    Args:
        host: Хост для прослушивания
        port: Порт для прослушивания
        token: Токен аутентификации
        
    Returns:
        True если сервер запущен успешно
    """
    global _mcp_server, _dispatcher, _state
    
    log = get_logger()
    
    if _mcp_server is not None and _state.status == "RUNNING":
        log.warning("Сервер уже запущен")
        return False
    
    try:
        _state.status = "STARTING"
        _state.host = host
        _state.port = port
        _state.token = token
        _state.last_error = ""
        
        # Создать диспетчер
        _dispatcher = CommandDispatcher(_command_queue)
        
        # Зарегистрировать таймер для обработки очереди
        bpy.app.timers.register(process_command_queue, first_interval=0.01)
        log.info("Таймер диспетчера зарегистрирован")
        
        # Запустить TCP-сервер в отдельном потоке
        _mcp_server = MCPAddonServer(
            host=host,
            port=port,
            token=token,
            command_queue=_command_queue,
            dispatcher=_dispatcher,
        )
        
        server_thread = threading.Thread(target=_mcp_server.run, daemon=True)
        server_thread.start()
        
        _state.status = "RUNNING"
        log.info(f"Сервер запущен на {host}:{port}")
        return True
        
    except Exception as e:
        _state.status = "ERROR"
        _state.last_error = str(e)
        log.error(f"Ошибка запуска сервера: {e}")
        return False


def stop_server() -> None:
    """Остановить TCP-сервер."""
    global _mcp_server, _dispatcher, _state
    
    log = get_logger()
    
    if _mcp_server is None:
        return
    
    try:
        _state.status = "STOPPING"
        
        # Остановить сервер
        _mcp_server.stop()
        _mcp_server = None
        
        # Удалить таймер
        if bpy.app.timers.is_registered(process_command_queue):
            bpy.app.timers.unregister(process_command_queue)
        
        # Очистить очередь
        while not _command_queue.empty():
            try:
                _command_queue.get_nowait()
            except queue.Empty:
                break
        
        _dispatcher = None
        _state.status = "STOPPED"
        _state.connections_count = 0
        _state.queue_size = 0
        log.info("Сервер остановлен")
        
    except Exception as e:
        _state.last_error = str(e)
        _state.status = "ERROR"
        log.error(f"Ошибка остановки сервера: {e}")


def get_server_info() -> dict[str, Any]:
    """Получить информацию о сервере и Blender."""
    import bpy
    
    return {
        "blender_version": ".".join(map(str, bpy.app.version)),
        "addon_version": ".".join(map(str, bl_info["version"])),
        "protocol_version": 1,
        "status": _state.status,
        "host": _state.host,
        "port": _state.port,
        "dispatcher_active": _dispatcher is not None,
    }


class MCP_PG_properties(bpy.types.PropertyGroup):
    """Группа свойств для хранения состояния аддона."""
    
    server_status: bpy.props.StringProperty(
        name="Status",
        default="STOPPED",
    )
    server_host: bpy.props.StringProperty(
        name="Host",
        default="127.0.0.1",
    )
    server_port: bpy.props.IntProperty(
        name="Port",
        default=9999,
        min=1,
        max=65535,
    )
    server_token: bpy.props.StringProperty(
        name="Token",
        default="",
        subtype="PASSWORD",
    )
    last_error: bpy.props.StringProperty(
        name="Last Error",
        default="",
    )


classes = (
    MCP_PG_properties,
    MCP_PT_main_panel,
    MCP_OT_start_server,
    MCP_OT_stop_server,
    MCP_OT_ping_server,
)


def register() -> None:
    """Зарегистрировать аддон."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.mcp_properties = bpy.props.PointerProperty(type=MCP_PG_properties)
    get_logger().info("Blender MCP Addon зарегистрирован")


def unregister() -> None:
    """От_unregister_ить аддон."""
    # Остановить сервер при выгрузке
    stop_server()
    
    # Удалить свойства
    if hasattr(bpy.types.Scene, "mcp_properties"):
        del bpy.types.Scene.mcp_properties
    
    # Удалить классы
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    get_logger().info("Blender MCP Addon удалён")


if __name__ == "__main__":
    register()
