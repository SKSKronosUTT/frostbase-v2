import json
import logging

from app.core.logging import JsonFormatter, request_id_ctx, setup_logging


def test_json_formatter_includes_request_id_and_extra():
    setup_logging("DEBUG")
    token = request_id_ctx.set("req-123")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hola",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.status_code = 200
    payload = json.loads(JsonFormatter().format(record))
    request_id_ctx.reset(token)

    assert payload["message"] == "hola"
    assert payload["request_id"] == "req-123"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200


def test_json_formatter_serializes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="fallo",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError" in payload["exception"]
