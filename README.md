# Blender MCP Server

Управление Blender через Model Context Protocol (MCP) для интеграции с AI-ассистентами.

## Архитектура

```
┌─────────────────┐      TCP       ┌─────────────────┐
│   MCP Client    │ ◄────────────► │  Blender Addon  │
│  (AI Assistant) │     9999       │  (inside Blender)│
└────────┬────────┘                └─────────────────┘
         │
         │ stdio
         ▼
┌─────────────────┐
│  MCP Server     │
│  (blender-mcp)  │
└─────────────────┘
```

## Компоненты

1. **MCP Server** (`src/blender_mcp/`) - внешний сервер для AI-клиентов
2. **Blender Addon** (`blender_addon/`) - аддон внутри Blender
3. **TCP Protocol** - бинарный протокол с 4-байтовым заголовком

## Установка

### 1. Установить MCP сервер

```bash
pip install -e .
```

Или использовать напрямую:

```bash
python -m blender_mcp.mcp_server
```

### 2. Установить аддон в Blender

1. В Blender: Edit → Preferences → Add-ons
2. Нажать "Install from Disk"
3. Выбрать `blender_addon/blender_mcp_addon` (папку или zip)
4. Активировать галочкой "Interface: Blender MCP Server"

### 3. Запустить сервер в Blender

1. Открыть панель MCP в 3D Viewport → Sidebar → MCP
2. Настроить порт (по умолчанию 9999)
3. Опционально: установить токен
4. Нажать "Start Server"

## Использование

### Через MCP CLI

```bash
# Проверить подключение
mcp call blender-mcp ping

# Создать куб
mcp call blender-mcp create_object '{"type": "cube"}'

# Применить материал
mcp call blender-mcp apply_material '{"object_name": "Cube", "base_color": [1,0,0,1]}'

# Настроить камеру
mcp call blender-mcp set_camera '{"location": [0, -10, 5], "target": [0, 0, 0]}'

# Рендер
mcp call blender-mcp render_scene '{"filepath": "/tmp/render.png"}'

# Экспорт в FBX
mcp call blender-mcp export_fbx '{"filepath": "/tmp/scene.fbx"}'

# Экспорт в GLB
mcp call blender-mcp export_gltf '{"filepath": "/tmp/scene.glb"}'

# Получить информацию о сцене
mcp call blender-mcp get_scene_info
```

### Через Claude Desktop

Добавить в конфиг `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blender": {
      "command": "blender-mcp-server",
      "env": {
        "BLENDER_MCP_HOST": "127.0.0.1",
        "BLENDER_MCP_PORT": "9999",
        "BLENDER_MCP_TOKEN": "your-secret-token"
      }
    }
  }
}
```

## Доступные команды

| Команда | Описание |
|---------|----------|
| `ping` | Проверка подключения |
| `get_blender_info` | Информация о версии Blender |
| `create_object` | Создать 3D объект (cube, sphere, cylinder, cone, plane, torus, empty) |
| `apply_material` | Применить PBR материал |
| `add_light` | Добавить источник света (POINT, SUN, SPOT, AREA) |
| `set_camera` | Настроить камеру |
| `render_scene` | Выполнить рендер сцены |
| `render_preview` | Быстрый превью-рендер с возвратом изображения |
| `export_fbx` | Экспорт в FBX для Unity |
| `export_gltf` | Экспорт в glTF/GLB |
| `get_scene_info` | Список объектов сцены |
| `transform_object` | Изменить позицию/вращение/масштаб |
| `delete_objects` | Удалить объекты |
| `execute_batch` | Пакетное выполнение команд |

## Безопасность

### Токен аутентификации

По умолчанию токен генерируется автоматически при первом запуске. Для установки своего токена:

```bash
export BLENDER_MCP_TOKEN="your-secret-token"
```

Или в конфиге MCP клиента.

### Разрешённые пути

Для экспорта и рендера используйте только разрешённые директории:

```bash
export BLENDER_MCP_OUTPUT_DIR="$HOME/blender_mcp_output"
```

## Конфигурация

Переменные окружения:

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BLENDER_MCP_HOST` | `127.0.0.1` | Хост для подключения |
| `BLENDER_MCP_PORT` | `9999` | Порт TCP сервера |
| `BLENDER_MCP_TOKEN` | (авто) | Токен аутентификации |
| `BLENDER_MCP_TIMEOUT` | `60.0` | Тайм-аут команд (сек) |
| `BLENDER_MCP_OUTPUT_DIR` | `~/blender_mcp_output` | Директория для файлов |

## Совместимость

- **Blender**: 4.0+ (поддержка BLENDER_EEVEE и BLENDER_EEVEE_NEXT)
- **Python**: 3.10+
- **MCP SDK**: 2.0+

## Лицензия

GPL-2.0

## Разработка

```bash
# Установить зависимости для разработки
pip install -e ".[dev]"

# Запустить тесты
pytest tests/

# Проверка типов
mypy src/blender_mcp/

# Линтинг
ruff check src/blender_mcp/
```

## Структура проекта

```
blender-mcp/
├── pyproject.toml          # Конфигурация пакета
├── README.md               # Документация
├── src/blender_mcp/        # MCP сервер
│   ├── __init__.py
│   ├── mcp_server.py       # MCP инструменты
│   ├── client.py           # TCP клиент
│   ├── protocol.py         # Протокол сообщений
│   ├── config.py           # Конфигурация
│   └── errors.py           # Типы ошибок
├── blender_addon/          # Аддон для Blender
│   └── blender_mcp_addon/
│       ├── __init__.py     # Точка входа
│       ├── tcp_server.py   # TCP сервер
│       ├── dispatcher.py   # Диспетчер команд
│       ├── blender_tools.py# Blender API функции
│       ├── protocol_helper.py # Протокол
│       └── ui.py           # UI панель
└── tests/                  # Тесты
    └── test_protocol.py
```
