"""Тесты для протокола обмена сообщениями."""

import pytest
import struct
import json

from blender_mcp.protocol import (
    encode_message_to_bytes,
    decode_message_from_bytes,
    read_exact,
    validate_message_structure,
    RequestMessage,
    ResponseMessage,
    ErrorMessage,
    MAX_MESSAGE_SIZE,
    PROTOCOL_VERSION,
)


def test_encode_decode_roundtrip():
    """Проверить кодирование и декодирование сообщения."""
    original = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "test-123",
        "status": "ok",
        "data": {"key": "value"},
    }
    
    encoded = encode_message_to_bytes(original)
    decoded = decode_message_from_bytes(encoded[4:])  # Пропустить 4 байта длины
    
    assert decoded == original


def test_encode_message_length_prefix():
    """Проверить что первые 4 байта - длина сообщения."""
    msg = {"test": "data"}
    encoded = encode_message_to_bytes(msg)
    
    json_part = encoded[4:]
    expected_length = len(json_part)
    actual_length = struct.unpack(">I", encoded[:4])[0]
    
    assert actual_length == expected_length


def test_request_message_creation():
    """Проверить создание запроса."""
    req = RequestMessage(
        command="create_object",
        args={"type": "cube"},
        token="secret",
    )
    
    assert req.command == "create_object"
    assert req.args == {"type": "cube"}
    assert req.token == "secret"
    assert req.protocol_version == PROTOCOL_VERSION


def test_request_message_to_dict():
    """Проверить сериализацию запроса."""
    req = RequestMessage(
        command="test_cmd",
        args={"x": 1},
        request_id="req-001",
        token="tok",
    )
    
    d = req.to_dict()
    
    assert d["command"] == "test_cmd"
    assert d["args"] == {"x": 1}
    assert d["request_id"] == "req-001"
    assert d["token"] == "tok"
    assert d["protocol_version"] == PROTOCOL_VERSION


def test_response_message_creation():
    """Проверить создание ответа."""
    resp = ResponseMessage(
        request_id="req-001",
        data={"result": "success"},
    )
    
    assert resp.request_id == "req-001"
    assert resp.data == {"result": "success"}
    assert resp.status == "ok"


def test_error_message_creation():
    """Проверить создание сообщения об ошибке."""
    err = ErrorMessage(
        request_id="req-001",
        code="OBJECT_NOT_FOUND",
        message="Объект не найден",
        details={"name": "Cube"},
    )
    
    assert err.code == "OBJECT_NOT_FOUND"
    assert err.message == "Объект не найден"
    assert err.details == {"name": "Cube"}
    assert err.status == "error"


def test_validate_valid_request():
    """Проверить валидацию корректного запроса."""
    valid_request = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "test-id",
        "command": "create_object",
        "args": {},
    }
    
    # Не должно вызывать исключений
    validate_message_structure(valid_request, "request")


def test_validate_invalid_request_no_command():
    """Проверить что запрос без command отклоняется."""
    invalid = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "test-id",
    }
    
    with pytest.raises(ValueError, match="command"):
        validate_message_structure(invalid, "request")


def test_validate_invalid_request_wrong_version():
    """Проверить что неверная версия протокола отклоняется."""
    invalid = {
        "protocol_version": 999,
        "request_id": "test-id",
        "command": "test",
    }
    
    with pytest.raises(ValueError, match="Несовместимая версия протокола"):
        validate_message_structure(invalid, "request")


def test_validate_valid_response():
    """Проверить валидацию корректного ответа."""
    valid_response = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "test-id",
        "status": "ok",
        "data": {"result": True},
    }
    
    validate_message_structure(valid_response, "response")


def test_validate_error_response():
    """Проверить валидацию ответа с ошибкой."""
    error_response = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "test-id",
        "status": "error",
        "error": {
            "code": "TEST_ERROR",
            "message": "Test message",
        },
    }
    
    validate_message_structure(error_response, "response")


def test_max_message_size():
    """Проверить ограничение размера сообщения."""
    huge_data = {"data": "x" * (MAX_MESSAGE_SIZE + 1)}
    
    with pytest.raises(ValueError, match="слишком большое"):
        encode_message_to_bytes(huge_data)
