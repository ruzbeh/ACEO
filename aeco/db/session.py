import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aeco.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    Import all models first so Base.metadata knows about them.
    """
    # Import all models so they register with Base.metadata
    import aeco.models.task  # noqa: F401
    import aeco.models.workflow  # noqa: F401
    import aeco.models.audit  # noqa: F401
    import aeco.models.project  # noqa: F401
    import aeco.models.budget  # noqa: F401
    import aeco.models.decision_ledger  # noqa: F401
    import aeco.models.initiative  # noqa: F401
    import aeco.models.message  # noqa: F401
    import aeco.models.approval  # noqa: F401
    import aeco.models.portfolio_cycle  # noqa: F401
    import aeco.models.campaign_product  # noqa: F401
    from aeco.memory.store import MemoryEntry  # noqa: F401

    from aeco.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized (create_all)")
