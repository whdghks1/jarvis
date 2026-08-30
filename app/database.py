from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()
engine_options: dict = {"pool_pre_ping": True}
if settings.database_url == "sqlite+pysqlite:///:memory:":
    engine_options.update(
        connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
engine = create_engine(settings.database_url, **engine_options)

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_schema() -> None:
    # Import model modules so SQLAlchemy registers every table before create_all.
    from app.conversation import models as conversation_models  # noqa: F401
    from app.action import models as action_models  # noqa: F401
    from app.memory import models as memory_models  # noqa: F401
    from app.profile import models as profile_models  # noqa: F401
    from app.security import models as security_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
