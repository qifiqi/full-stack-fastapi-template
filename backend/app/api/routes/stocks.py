from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep
from app.crud import get_stock_metadata, search_stock_metadata

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search")
def search_stocks(
    session: SessionDep,
    keyword: str = Query(min_length=1, max_length=64),
    market_type: str | None = None,
    limit: int = 20,
) -> Any:
    """Search stock metadata by code or name."""
    rows = search_stock_metadata(
        session=session, keyword=keyword, market_type=market_type, limit=limit
    )
    return {
        "data": [
            {
                "id": r.id,
                "stock_code": r.stock_code,
                "market_type": r.market_type,
                "name": r.name,
                "exchange": r.exchange,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/{market_type}/{code}")
def read_stock(session: SessionDep, market_type: str, code: str) -> Any:
    """Get stock metadata incl. the raw source payload."""
    stock = get_stock_metadata(
        session=session, stock_code=code, market_type=market_type
    )
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {
        "id": stock.id,
        "stock_code": stock.stock_code,
        "market_type": stock.market_type,
        "name": stock.name,
        "exchange": stock.exchange,
        "raw": stock.raw,
        "updated_at": stock.updated_at,
    }
