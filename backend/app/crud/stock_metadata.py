from typing import Any

from sqlmodel import Session, col, or_, select

from app.models import StockMetadata, StockMetadataCreate, StockMetadataUpdate


def upsert_stock_metadata(
    *,
    session: Session,
    metadata_in: StockMetadataCreate,
    raw: dict[str, Any] | None = None,
) -> StockMetadata:
    db_obj = session.exec(
        select(StockMetadata).where(
            StockMetadata.stock_code == metadata_in.stock_code,
            StockMetadata.market_type == metadata_in.market_type,
        )
    ).first()
    if db_obj:
        update = metadata_in.model_dump(exclude_unset=True)
        if raw is not None:
            update["raw"] = raw
        db_obj.sqlmodel_update(update)
    else:
        db_obj = StockMetadata.model_validate(metadata_in, update={"raw": raw})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_stock_metadata(
    *, session: Session, stock_code: str, market_type: str
) -> StockMetadata | None:
    statement = select(StockMetadata).where(
        StockMetadata.stock_code == stock_code,
        StockMetadata.market_type == market_type,
    )
    return session.exec(statement).first()


def search_stock_metadata(
    *, session: Session, keyword: str, market_type: str | None = None, limit: int = 20
) -> list[StockMetadata]:
    pattern = f"%{keyword}%"
    statement = select(StockMetadata).where(
        or_(
            col(StockMetadata.stock_code).like(pattern),
            col(StockMetadata.name).like(pattern),
        )
    )
    if market_type:
        statement = statement.where(StockMetadata.market_type == market_type)
    statement = statement.order_by(col(StockMetadata.stock_code).asc()).limit(limit)
    return list(session.exec(statement).all())


def update_stock_metadata(
    *, session: Session, db_stock: StockMetadata, metadata_in: StockMetadataUpdate
) -> Any:
    stock_data = metadata_in.model_dump(exclude_unset=True)
    db_stock.sqlmodel_update(stock_data)
    session.add(db_stock)
    session.commit()
    session.refresh(db_stock)
    return db_stock
