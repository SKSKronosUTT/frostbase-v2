from typing import Any


def ok(data: Any = None):
    return {"status": 0, "type": "Success", "data": data}


def fail(message: str, status: int = 1):
    return {"status": status, "type": "Error", "data": None, "error": message}
