from fastapi import APIRouter, Depends, HTTPException

from ..db import fetch_one, get_conn
from ..deps import current_user
from ..responses import ok
from ..schemas import LoginIn
from ..security import create_token, verify_password
from ..serializers import user_dto

router = APIRouter(prefix="/auth", tags=["auth"])


def _login(payload: LoginIn, conn):
    user = fetch_one(
        conn,
        "SELECT * FROM users WHERE lower(email) = lower(%s) AND active = true",
        (payload.email,),
    )
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    dto = user_dto(conn, user)
    dto["token"] = create_token(user["id"])
    return ok(dto)


@router.post("/login")
def login(payload: LoginIn, conn=Depends(get_conn)):
    return _login(payload, conn)


@router.post("/User/login", include_in_schema=False)
def legacy_login(payload: LoginIn, conn=Depends(get_conn)):
    return _login(payload, conn)


@router.get("/me")
def me(user=Depends(current_user), conn=Depends(get_conn)):
    return ok(user_dto(conn, user))
