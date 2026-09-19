"""
Standalone connection test. Run this BEFORE touching FastAPI or Alembic
to confirm settings.py, .env, and the running Docker container all agree
with each other.

Run with: python test_connection.py
"""

import asyncio

from sqlalchemy import text

from backend.database.session import engine


async def main() -> None:
    print(f"Connecting to: {engine.url.render_as_string(hide_password=True)}")

    async with engine.connect() as conn:
        version = await conn.scalar(text("SELECT version();"))
        print(f"\n✅ Connected successfully.\nPostgres version: {version}")

        extensions = await conn.execute(
            text("SELECT extname FROM pg_extension ORDER BY extname;")
        )
        ext_names = [row[0] for row in extensions]
        print(f"\nInstalled extensions: {ext_names}")

        for required in ("vector", "timescaledb", "pg_trgm"):
            status = "✅" if required in ext_names else "❌ MISSING"
            print(f"  {required}: {status}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
