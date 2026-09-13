from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")

# SQLite (unit tests) only autoincrements INTEGER primary keys; PG/MySQL get BIGINT.
BIGINT_PK = BigInteger().with_variant(Integer(), "sqlite")


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)
