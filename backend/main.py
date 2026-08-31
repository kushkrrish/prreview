"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import close_database, init_database
from backend.settings import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown logic for the application lifecycle."""
    logger.info("Starting AI PR Review Agent (environment=%s)", settings.ENVIRONMENT)
    await init_database()
    yield
    logger.info("Shutting down AI PR Review Agent")
    await close_database()


app = FastAPI(
    title="AI PR Review Agent",
    description="Production-grade AI-powered pull request review system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return process health for load balancers and uptime probes."""
    return {"status": "ok"}


def main() -> None:
    """Run the development server from the command line."""
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT in {"development", "dev"},
    )


if __name__ == "__main__":
    main()

