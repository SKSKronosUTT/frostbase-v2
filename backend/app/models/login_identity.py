"""Identidades de login compartidas entre administradores y conductores.

El correo es el identificador único de acceso. Esta tabla garantiza a nivel de
base de datos que un correo no exista simultáneamente como administrador y
como conductor. Los servicios la mantienen en la misma transacción que crean
o reactivan cuentas.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.time import utcnow

ACCOUNT_TYPES = ("admin", "driver")


class LoginIdentity(Base):
    __tablename__ = "login_identities"
    __table_args__ = (
        UniqueConstraint("email", name="uq_login_identities_email"),
        Index("ix_login_identities_account", "account_type", "account_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
