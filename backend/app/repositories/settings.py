from sqlalchemy.orm import Session

from app.models.setting import Setting


def get(db: Session) -> Setting | None:
    return db.get(Setting, 1)


def get_or_create(db: Session) -> Setting:
    setting = db.get(Setting, 1)
    if setting is None:
        setting = Setting(id=1)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def commit(db: Session, setting: Setting) -> Setting:
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting
