"""
UI панель для управления MCP сервером в Blender.

Добавляет панель в 3D Viewport -> Sidebar -> MCP.
"""

import bpy


class MCP_PT_main_panel(bpy.types.Panel):
    """Основная панель MCP."""
    
    bl_label = "MCP Server"
    bl_idname = "MCP_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.mcp_properties
        
        # Статус сервера
        box = layout.box()
        row = box.row()
        row.label(text="Status:", icon="INFO")
        
        status_icon = "GREEN" if props.server_status == "RUNNING" else "RED"
        if props.server_status == "STARTING":
            status_icon = "TIME"
        elif props.server_status == "STOPPING":
            status_icon = "TRIA_DOWN"
        
        row.label(text=props.server_status, icon=status_icon)
        
        # Настройки подключения
        box = layout.box()
        box.label(text="Settings:")
        box.prop(props, "server_host")
        box.prop(props, "server_port")
        box.prop(props, "server_token")
        
        # Кнопки управления
        row = layout.row(align=True)
        
        if props.server_status == "RUNNING":
            row.operator("mcp.stop_server", icon="TRIA_RIGHT", text="Stop Server")
        else:
            row.operator("mcp.start_server", icon="PLAY", text="Start Server")
        
        # Дополнительная информация
        if props.server_status == "RUNNING":
            box = layout.box()
            box.label(text=f"Host: {props.server_host}:{props.server_port}")
            if props.last_error:
                box.label(text=f"Error: {props.last_error}", icon="ERROR")


class MCP_OT_start_server(bpy.types.Operator):
    """Запустить MCP сервер."""
    
    bl_idname = "mcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Запустить TCP сервер для подключения MCP клиента"
    
    def execute(self, context):
        from . import start_server, get_state
        
        props = context.scene.mcp_properties
        
        success = start_server(
            host=props.server_host,
            port=props.server_port,
            token=props.server_token,
        )
        
        state = get_state()
        props.server_status = state.status
        props.last_error = state.last_error
        
        if success:
            self.report({"INFO"}, f"MCP сервер запущен на {props.server_host}:{props.server_port}")
        else:
            self.report({"ERROR"}, f"Ошибка запуска: {state.last_error}")
        
        return {"FINISHED"}


class MCP_OT_stop_server(bpy.types.Operator):
    """Остановить MCP сервер."""
    
    bl_idname = "mcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Остановить TCP сервер"
    
    def execute(self, context):
        from . import stop_server, get_state
        
        stop_server()
        
        props = context.scene.mcp_properties
        state = get_state()
        props.server_status = state.status
        
        self.report({"INFO"}, "MCP сервер остановлен")
        return {"FINISHED"}


class MCP_OT_ping_server(bpy.types.Operator):
    """Проверить подключение к серверу."""
    
    bl_idname = "mcp.ping_server"
    bl_label = "Ping Server"
    bl_description = "Проверить работу сервера"
    
    def execute(self, context):
        self.report({"INFO"}, "Ping not implemented in UI yet")
        return {"FINISHED"}
