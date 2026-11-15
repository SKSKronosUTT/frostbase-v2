import uuid
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import DATABASE_URL

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def new_id() -> str:
    return uuid.uuid4().hex[:24]


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(conn, query: str, params: Iterable[Any] | None = None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def fetch_one(conn, query: str, params: Iterable[Any] | None = None) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()


def fetch_value(conn, query: str, params: Iterable[Any] | None = None):
    row = fetch_one(conn, query, params)
    return next(iter(row.values())) if row else None


def execute(conn, query: str, params: Iterable[Any] | None = None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        return cur


def jsonb(value):
    return Jsonb(value)


def init_db() -> None:
    sql = SCHEMA_FILE.read_text()
    with connect() as conn:
        conn.execute(sql)
        conn.commit()
