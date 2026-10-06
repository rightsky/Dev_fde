import io
import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="fde-test-"))
os.environ.setdefault("FDE_DATABASE_URL", f"sqlite:///{_tmp / 'test.db'}")
os.environ["FDE_STORAGE_DIR"] = str(_tmp / "storage")
os.environ["FDE_ADMIN_USERNAME"] = "admin"
os.environ["FDE_ADMIN_PASSWORD"] = "test-password-1"
os.environ["FDE_SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "test-password-1"})
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
        yield c
