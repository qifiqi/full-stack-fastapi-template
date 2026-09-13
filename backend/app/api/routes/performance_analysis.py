"""Performance analysis API: NDJSON streaming endpoints (functional V1)."""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import SessionDep
from app.services.performance_analysis.streaming import (
    ndjson_lines,
    weight_combination_lines,
)

router = APIRouter(prefix="/performance-analysis", tags=["performance-analysis"])


def _ndjson(iterator: Any) -> StreamingResponse:
    return StreamingResponse(
        iterator,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "inline"},
    )


def _error_line(message: str) -> Any:
    import json

    def _gen() -> Any:
        yield (
            json.dumps({"type": "error", "detail": message}, ensure_ascii=False) + "\n"
        )

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "inline"},
    )


@router.post("/analyze")
def analyze(_session: SessionDep, payload: dict[str, Any]) -> Any:
    """Synchronous return analysis (single JSON body)."""
    from app.services.performance_analysis.streaming import (
        analyze_series,
        parse_series,
    )

    try:
        return analyze_series(parse_series(payload))
    except (TypeError, ValueError) as exc:
        return {"error": f"输入序列无效: {exc}"}


@router.post("/v1/analyze")
def analyze_stream(_session: SessionDep, payload: dict[str, Any]) -> Any:
    """NDJSON streaming analysis (one json.dumps line + \\n per record)."""
    try:
        return _ndjson(ndjson_lines(payload))
    except (TypeError, ValueError) as exc:
        return _error_line(f"输入序列无效: {exc}")


@router.post("/v1/weight-combination")
def weight_combination(_session: SessionDep, payload: dict[str, Any]) -> Any:
    """Chunked-streaming weight combination (supports large grids)."""
    try:
        return _ndjson(weight_combination_lines(payload))
    except (TypeError, ValueError) as exc:
        return _error_line(f"输入序列无效: {exc}")
