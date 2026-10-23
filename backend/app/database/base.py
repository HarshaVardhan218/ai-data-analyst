from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared base class for all our SQLAlchemy ORM models.
    Every model (Dataset, and more added later) inherits from this,
    so SQLAlchemy can track them all together as one metadata registry.
    """
    pass
