from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import fetch_one, get_conn
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    user = fetch_one(
        conn,
        "SELECT * FROM users WHERE id = %s AND active = true",
        (user_id,),
    )
    if not user:
        raise HTTPException(status_code=401, detail="El usuario no está activo")
    return user


def current_admin(user=Depends(current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Se requiere acceso de administrador")
    return user
