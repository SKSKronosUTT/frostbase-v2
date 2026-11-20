"""Utilidades de búsqueda segura para SQL ``ILIKE``."""


def escape_like(value: str) -> str:
    """Escapa comodines de LIKE para que se traten como texto literal."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
