import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.database import init_db


@pytest.fixture(autouse=True, scope="function")
async def _ensure_tables():
    await init_db()
    yield
