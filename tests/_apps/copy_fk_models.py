"""Consumer-shaped models for the copy dialog harness (`copy_fk_app.py`).

An alert row with a string UUID PK, a foreign key to a template shown by a
`@property`, and a many-to-many relation; the read schema has no FK field.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Column, Engine, ForeignKey, String, Table
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

ID_ALERT = "c3a1e5b2-0000-4000-8000-000000000001"
ID_IOS = "0a7d2c4e-0000-4000-8000-000000000002"
ID_ANDROID = "7f3b9e1d-0000-4000-8000-000000000003"
ID_RULE_LOW = "f19c6a8b-0000-4000-8000-000000000004"
ID_RULE_HIGH = "2b6d8f0a-0000-4000-8000-000000000005"


class Base(DeclarativeBase):
    """Declarative base for the copy harness."""


alert_rule = Table(
    "cf_alert_rule",
    Base.metadata,
    Column("alert_id", ForeignKey("cf_alert.id"), primary_key=True),
    Column("rule_id", ForeignKey("cf_rule.id"), primary_key=True),
)


class Template(Base):
    """Foreign-key target; its option label is the `display_name` property."""

    __tablename__ = "cf_template"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    app_name: Mapped[str] = mapped_column()
    platform: Mapped[str] = mapped_column()

    @property
    def display_name(self) -> str:
        """App name and platform joined, as the selectbox shows them."""
        return f"{self.app_name}_{self.platform}"

    def __str__(self) -> str:
        return self.display_name


class Rule(Base):
    """Target of the many-to-many relationship."""

    __tablename__ = "cf_rule"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_name: Mapped[str] = mapped_column()

    def __str__(self) -> str:
        return self.rule_name


class Alert(Base):
    """The copied row; `note` is a column no read query or schema shows."""

    __tablename__ = "cf_alert"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("cf_template.id"))
    fact_query: Mapped[str] = mapped_column()
    note: Mapped[str | None] = mapped_column()

    template: Mapped[Template] = relationship()
    rules: Mapped[list[Rule]] = relationship(secondary=alert_rule)

    @property
    def app_name(self) -> str:
        """App name of the template; the read schema needs the label as attr."""
        return self.template.app_name

    @property
    def platform(self) -> str:
        """Platform of the template."""
        return self.template.platform

    def __str__(self) -> str:
        return self.fact_query


class AlertRead(BaseModel):
    """Read schema: joined labels and rule names, neither PK nor FK."""

    model_config = ConfigDict(from_attributes=True)

    app_name: str | None = None
    platform: str | None = None
    fact_query: str
    rules: list[str] | None = None

    @field_validator("rules", mode="before")
    @classmethod
    def rule_names(cls, value: list[Rule] | None) -> list[str]:
        """Show the related rules by name."""
        return [rule.rule_name for rule in value or []]


class AlertCreate(BaseModel):
    """Create schema with the required FK and the many-to-many field."""

    template_id: str
    fact_query: str
    note: str | None = None
    rules: list | None = None


def seed(engine: Engine) -> None:
    """Create the tables and insert the fixed rows once."""
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        if s.get(Alert, ID_ALERT):
            return
        ios = Template(id=ID_IOS, app_name="Alpha", platform="ios")
        android = Template(id=ID_ANDROID, app_name="Alpha", platform="android")
        low = Rule(id=ID_RULE_LOW, rule_name="low")
        high = Rule(id=ID_RULE_HIGH, rule_name="high")
        s.add_all([ios, android, low, high])
        s.add(
            Alert(
                id=ID_ALERT,
                template=android,
                fact_query="select 1",
                note="keep me",
                rules=[high],
            )
        )
        s.commit()
