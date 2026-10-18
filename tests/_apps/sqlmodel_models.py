"""SQLModel table models for the SQLModel harness app and tests.

They live in an importable module: an AppTest rerun of a script defining them
would register the tables again in the global `SQLModel.metadata`.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Rank(StrEnum):
    """String enum stored through SQLModel's default SQLAlchemy Enum."""

    LOW = "low"
    HIGH = "high"


class HeroPowerLink(SQLModel, table=True):
    """Association table of the Hero <-> Power many-to-many relationship."""

    hero_id: int | None = Field(default=None, foreign_key="hero.id", primary_key=True)
    power_id: int | None = Field(default=None, foreign_key="power.id", primary_key=True)


class Team(SQLModel, table=True):
    """Parent table referenced by Hero through a foreign key."""

    id: int | None = Field(default=None, primary_key=True)
    name: str

    heroes: list["Hero"] = Relationship(back_populates="team")

    def __str__(self) -> str:
        return self.name


class Power(SQLModel, table=True):
    """Target table of the many-to-many relationship."""

    id: int | None = Field(default=None, primary_key=True)
    name: str

    def __str__(self) -> str:
        return self.name


class HeroBase(SQLModel):
    """Fields shared by the Hero table and its schemas."""

    name: str
    rank: Rank = Rank.LOW
    active: bool = True
    born: date | None = None
    salary: Decimal = Field(default=Decimal(0), max_digits=10, decimal_places=2)
    team_id: int | None = Field(default=None, foreign_key="team.id")


class Hero(HeroBase, table=True):
    """Table with str (AutoString), enum, date, decimal, JSON, FK and M2M."""

    id: int | None = Field(default=None, primary_key=True)
    meta: dict | None = Field(default=None, sa_column=Column(JSON))

    team: Team | None = Relationship(back_populates="heroes")
    powers: list[Power] = Relationship(link_model=HeroPowerLink)

    def __str__(self) -> str:
        return f"Hero {self.name}"


class HeroCreate(HeroBase):
    """Create schema; the M2M field is named as the relationship."""

    powers: list[int] = []


class HeroRead(HeroBase):
    """Read schema."""

    id: int


class HeroUpdate(HeroBase):
    """Update schema; the M2M field is named as the relationship."""

    id: int
    powers: list[int] = []
