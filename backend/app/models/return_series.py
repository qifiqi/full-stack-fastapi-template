from datetime import date as Date

from sqlalchemy import BigInteger, Column, Double, ForeignKey
from sqlmodel import Field, SQLModel


class ReturnSeriesPointBase(SQLModel):
    task_result_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("task_result.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    date: Date = Field(primary_key=True)
    index_return: float | None = Field(default=None, sa_type=Double)
    start_return: float | None = Field(default=None, sa_type=Double)


class ReturnSeriesPointCreate(ReturnSeriesPointBase):
    pass


class ReturnSeriesPoint(ReturnSeriesPointBase, table=True):
    __tablename__ = "return_series_point"


class ReturnSeriesPointPublic(ReturnSeriesPointBase):
    pass
