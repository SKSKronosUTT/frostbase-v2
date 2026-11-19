"""Restablece la contraseña de un administrador desde variables de entorno.

Uso (dentro del contenedor):
    docker compose exec app python -m scripts.reset_admin
    docker compose exec app python -m scripts.reset_admin --username admin

La contraseña se toma de ADMIN_PASSWORD salvo que se pase --password.
No imprime la contraseña ni el hash.
"""

import argparse
import sys

from sqlalchemy import select

from app.core.config import MIN_ADMIN_PASSWORD_LENGTH, settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.admin import Admin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--username",
        default=settings.admin_username,
        help="Usuario administrador a restablecer (por defecto ADMIN_USERNAME).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Nueva contraseña. Por defecto se usa ADMIN_PASSWORD.",
    )
    parser.add_argument(
        "--clear-must-change",
        action="store_true",
        help=(
            "No forzar el cambio de contraseña en el próximo login. Por defecto "
            "se mantiene el flag para que el usuario defina una contraseña nueva."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    password = args.password or settings.admin_password

    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        print(
            "ERROR: la contraseña debe tener al menos "
            f"{MIN_ADMIN_PASSWORD_LENGTH} caracteres.",
            file=sys.stderr,
        )
        return 2

    username = args.username.strip().lower()
    with SessionLocal() as db:
        admin = db.scalar(select(Admin).where(Admin.username == username))
        if admin is None:
            print(f"ERROR: no existe el administrador '{username}'.", file=sys.stderr)
            return 1

        admin.password_hash = hash_password(password)
        if args.clear_must_change:
            admin.must_change_password = False
        admin.token_version += 1
        db.add(admin)
        db.commit()

    print(f"Contraseña actualizada para '{username}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
