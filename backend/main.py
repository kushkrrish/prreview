"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import hashlib
import hmac
import logging

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Header, HTTPException, Request, status
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


def verify_github_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verifies that the incoming HTTP POST request genuinely came from GitHub using HMAC SHA-256."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    # Calculate HMAC signature over the raw request payload
    expected_signature = hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header.split("sha256=")[1]
    # Use compare_digest to prevent timing attacks
    return hmac.compare_digest(expected_signature, received_signature)
@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health() -> dict[str, str]:
    """Return process health for load balancers and uptime probes."""
    return {"status": "ok"}


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """Receives Pull Request webhooks from GitHub, validates security signature,

    and enqueues background processing via ARQ + Redis.
    """
    # 1. Read raw request body before parsing JSON (Required for HMAC SHA256 validation)
    raw_body = await request.body()

    # 2. Verify HMAC Signature
    if not verify_github_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejecting GitHub Webhook: Invalid HMAC Signature")
        raise HTTPException(status_code=403, detail="Invalid HMAC Signature")

    # 3. Handle Pull Request Events
    if x_github_event == "pull_request":
        payload = await request.json()
        action = payload.get("action")

        # Process PRs when opened, updated (synchronize), or reopened
        if action in ["opened", "synchronize", "reopened"]:
            logger.info("Received PR event '%s' for PR #%s", action, payload.get("number"))

            # Enqueue payload to Redis for ARQ background processing
            redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job("process_pull_request", payload)

            return {
                "status": "accepted",
                "message": f"PR action '{action}' queued for async review.",
            }

    return {"status": "ignored", "message": f"Event '{x_github_event}' ignored"}


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


if __name__ == "__main__":
    main()