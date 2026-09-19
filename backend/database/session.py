from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.settings import settings

# echo=True prints every SQL statement to your terminal -- useful while
# building, turn off (settings.environment == "production") later.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT in ("development", "dev"),
    pool_pre_ping=True,  # detects and replaces dead connections automatically
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db)` in any route."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
