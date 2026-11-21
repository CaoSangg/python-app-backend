from typing import Annotated

from pydantic import StringConstraints, field_validator
from sqlmodel import Field, SQLModel


SongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\x00]+$")
]
MIN_DB_INTEGER = -(2**31)
MAX_DB_INTEGER = 2**31 - 1


class SongBase(SQLModel):
    name: str
    artist: str
    year: int | None = None


class Song(SongBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    year: int | None = Field(default=None, index=True)


class SongCreate(SongBase):
    name: SongText
    artist: SongText
    year: int | None = Field(default=None, ge=MIN_DB_INTEGER, le=MAX_DB_INTEGER)

    @field_validator("year", mode="before")
    @classmethod
    def validate_year_type(cls, value: object) -> object:
        if value is None or type(value) in (int, str):
            return value
        raise ValueError("Year must be an integer or null")


class SongRead(SongBase):
    id: int
