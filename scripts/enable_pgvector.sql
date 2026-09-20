-- Enables the pgvector extension on the FoodShare Postgres database.
-- Run once via the Supabase SQL editor, or programmatically with:
--   psql "$DATABASE_URL" -f scripts/enable_pgvector.sql
--
-- The Python equivalent (idempotent, called automatically by the indexer):
--   from ai.setup_db import ensure; ensure()
--
-- Note: On Supabase, the `vector` extension is available in every project;
-- creating it just registers it in the current database.

CREATE EXTENSION IF NOT EXISTS vector;
