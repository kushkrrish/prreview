-- Runs automatically ONCE, on first container start with an empty volume.
-- If you ever need to re-run this against an existing volume, run it manually:
--   docker exec -i agent_db psql -U postgres -d agent_db < init.sql

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
