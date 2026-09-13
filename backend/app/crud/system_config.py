from sqlmodel import Session, col, func, select

from app.models import SystemConfig, SystemConfigPublic, SystemConfigsPublic


def get_system_config(*, session: Session, key: str) -> SystemConfig | None:
    return session.get(SystemConfig, key)


def get_system_configs(
    *, session: Session, skip: int = 0, limit: int = 100
) -> SystemConfigsPublic:
    count = session.exec(select(func.count()).select_from(SystemConfig)).one()
    statement = (
        select(SystemConfig)
        .order_by(col(SystemConfig.key).asc())
        .offset(skip)
        .limit(limit)
    )
    configs = session.exec(statement).all()
    return SystemConfigsPublic(
        data=[SystemConfigPublic.model_validate(c) for c in configs], count=count
    )


def upsert_system_config(*, session: Session, key: str, value: str) -> SystemConfig:
    db_obj = session.get(SystemConfig, key)
    if db_obj:
        db_obj.value = value
    else:
        db_obj = SystemConfig(key=key, value=value)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj
