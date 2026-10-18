"""Execute a SqlUi read statement and return its rows as plain Python records.

One read path for every mode: query rows, optional many-to-many entity reload
and optional ``read_schema`` validation. Values stay as SQLAlchemy loads them.
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Row, RowMapping, Select, select
from sqlalchemy.orm import DeclarativeBase, Session

from streamlit_pydantic_crud.config_types import ManyToManyFields, SessionSource
from streamlit_pydantic_crud.helpers.sa_model import m2m_load_options, pk_attr, pk_name


def read_records(
    conn: SessionSource,
    stmt: Select[Any],
    model: type[DeclarativeBase],
    read_schema: type[BaseModel] | None = None,
    many_to_many_fields: ManyToManyFields | None = None,
) -> list[dict[str, Any]]:
    """Run `stmt` and return one dict per row, in query order.

    Keys are the statement's column labels, or the `read_schema` fields when
    given; the primary key of `model` is always present. With
    `many_to_many_fields` each row's entity is reloaded with those
    relationships; the query row's columns still win over the entity's.
    """
    with conn.session as s:
        rows = s.execute(stmt).all()
        entities: dict[Any, object] = {}
        if many_to_many_fields and rows:
            entities = load_entities(s, rows, model, many_to_many_fields)
        pk = pk_name(model)
        return [
            to_record(row, entities.get(row._mapping.get(pk)), pk, read_schema)
            for row in rows
        ]


def load_entities(
    s: Session,
    rows: Sequence[Row[Any]],
    model: type[DeclarativeBase],
    many_to_many_fields: ManyToManyFields,
) -> dict[Any, object]:
    """Load the `model` entities of `rows` with their M2M relationships, by PK."""
    pk = pk_name(model)
    ids = [row._mapping[pk] for row in rows]
    stmt = (
        select(model)
        .where(pk_attr(model).in_(ids))
        .options(*m2m_load_options(model, many_to_many_fields))
    )
    return {getattr(entity, pk): entity for entity in s.execute(stmt).scalars()}


def to_record(
    row: Row[Any],
    entity: object | None,
    pk: str,
    read_schema: type[BaseModel] | None,
) -> dict[str, Any]:
    """Build the record of one query `row`, overlaid on its reloaded `entity`.

    The row's columns (joined labels included) win over the entity's attributes.
    """
    mapping = row._mapping
    if read_schema is not None:
        source = row if entity is None else RowOverEntity(mapping, entity)
        record = read_schema.model_validate(source, from_attributes=True).model_dump()
    else:
        record = dict(mapping)
        if entity is not None:
            record.update(
                (key, value)
                for key, value in vars(entity).items()
                if not key.startswith("_") and key not in record
            )
    if pk not in record and pk in mapping:
        record[pk] = mapping[pk]
    return record


class RowOverEntity:
    """Attributes of a reloaded entity, overridden by its query row's columns.

    Labels keep the query value; relationships and properties come from the entity.
    """

    __slots__ = ("_entity", "_row")

    def __init__(self, row: RowMapping, entity: object) -> None:
        self._row = row
        self._entity = entity

    def __getattr__(self, name: str) -> Any:
        """Return the row's column `name`, else the entity's attribute."""
        if name in self._row:
            return self._row[name]
        return getattr(self._entity, name)
