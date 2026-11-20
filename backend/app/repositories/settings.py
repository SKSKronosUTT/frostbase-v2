from sqlalchemy.orm import Session

from app.models.setting import Setting


def get(db: Session) -> Setting | None:
    return db.get(Setting, 1)


def get_or_create(db: Session) -> Setting:
    """Devuelve la configuración sin escribir en la base de datos.

    La fila se crea únicamente en el bootstrap. Si no existe (por ejemplo, en
    una lectura IoT concurrente con la primera petición), se devuelve un objeto
    en memoria con los valores por defecto para no abrir una transacción de
    escritura en el camino de ingesta.
    """
    setting = db.get(Setting, 1)
    if setting is None:
        setting = Setting(id=1)
    return setting


def ensure_default(db: Session) -> Setting:
    setting = db.get(Setting, 1)
    if setting is None:
        setting = Setting(id=1)
        db.add(setting)
        db.flush()
    return setting


def save(db: Session, setting: Setting) -> Setting:
    db.add(setting)
    db.flush()
    return setting
