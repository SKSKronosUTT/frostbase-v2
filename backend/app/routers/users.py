from fastapi import APIRouter, Depends, HTTPException, Query

import psycopg

from ..db import execute, fetch_all, fetch_one, get_conn, new_id
from ..responses import ok
from ..schemas import UserIn, UserUpdate
from ..security import hash_password
from ..serializers import admin_dto, driver_dto, user_dto

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(role: str | None = Query(default=None), active: bool | None = None, conn=Depends(get_conn)):
    filters = []
    params = []
    if role == "driver":
        filters.append("is_admin = false")
    elif role == "admin":
        filters.append("is_admin = true")
    if active is not None:
        filters.append("active = %s")
        params.append(active)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = fetch_all(conn, f"SELECT * FROM users {where} ORDER BY first_name, last_name", params)
    return ok([user_dto(conn, row) for row in rows])


@router.get("/drivers")
def list_drivers(active: bool | None = None, conn=Depends(get_conn)):
    if active is None:
        rows = fetch_all(conn, "SELECT * FROM users WHERE is_admin = false ORDER BY first_name")
    else:
        rows = fetch_all(
            conn,
            "SELECT * FROM users WHERE is_admin = false AND active = %s ORDER BY first_name",
            (active,),
        )
    return ok([driver_dto(conn, row) for row in rows])


@router.get("/admins")
def list_admins(conn=Depends(get_conn)):
    rows = fetch_all(conn, "SELECT * FROM users WHERE is_admin = true ORDER BY first_name")
    return ok([admin_dto(conn, row) for row in rows])


@router.get("/{user_id}")
def get_user(user_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return ok(user_dto(conn, row))


@router.post("")
def create_user(payload: UserIn, conn=Depends(get_conn)):
    user_id = new_id()
    try:
        execute(
            conn,
            """
            INSERT INTO users(
                id, first_name, last_name, middle_name, email, phone, birthdate,
                password_hash, is_admin, id_truck_default, active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            """,
            (
                user_id,
                payload.first_name,
                payload.last_name,
                payload.middle_name,
                payload.email.lower(),
                payload.phone,
                payload.birth_date,
                hash_password(payload.password),
                payload.is_admin,
                payload.id_truck_default or None,
            ),
        )
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un usuario con este correo")
    row = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    return ok(user_dto(conn, row))


@router.put("/{user_id}")
def update_user(user_id: str, payload: UserUpdate, conn=Depends(get_conn)):
    existing = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return ok(user_dto(conn, existing))
    assignments = []
    values = []
    for field, value in changes.items():
        if field == "password":
            assignments.append("password_hash = %s")
            values.append(hash_password(value))
        else:
            column = "birthdate" if field == "birth_date" else field
            assignments.append(f"{column} = %s")
            if field in {"id_truck_default"} and value == "":
                value = None
            values.append(value)
    values.append(user_id)
    try:
        execute(conn, f"UPDATE users SET {', '.join(assignments)} WHERE id = %s", values)
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un usuario con este correo")
    row = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    return ok(user_dto(conn, row))


@router.delete("/{user_id}")
def deactivate_user(user_id: str, conn=Depends(get_conn)):
    row = fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    execute(conn, "UPDATE users SET active = false WHERE id = %s", (user_id,))
    row["active"] = False
    return ok(user_dto(conn, row))
