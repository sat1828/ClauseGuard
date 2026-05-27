"""
pytest configuration for ClauseGuard backend tests.
Sets all required env vars before any imports so pydantic-settings succeeds.
"""
import os
import sys

# Add backend to Python path so imports work without installation
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Stub all required env vars — tests use mocks, not real APIs
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-stub-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-stub-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-stub")
os.environ.setdefault("PINECONE_ENVIRONMENT", "us-east-1-aws")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("LANGCHAIN_API_KEY", "ls__test-stub-key")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_stub")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")

import pytest

# Required for pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
