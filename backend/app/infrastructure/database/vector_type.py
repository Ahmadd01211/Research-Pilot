"""Minimal pgvector column type; SQL queries cast validated literals explicitly."""

from typing import Any

from sqlalchemy.types import UserDefinedType


class Vector768(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **_kw: Any) -> str:
        return "vector(768)"
