-- ClauseGuard Database Initialisation
-- Runs automatically when the postgres container starts for the first time.
-- Enables the pgvector extension (required for vector similarity search).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
