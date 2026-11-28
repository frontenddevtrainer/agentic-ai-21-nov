import os
import tempfile

import pytest

# Tests use a throw-away data directory, re-seeded before every test.
os.environ["DEMO_DATA_DIR"] = tempfile.mkdtemp(prefix="langgraph-demos-test-")


@pytest.fixture(autouse=True)
def fresh_databases():
    from common.db import DATABASES, db_path
    from common.seed import build

    for name in DATABASES:
        build(name)
    db_path("checkpoints").unlink(missing_ok=True)
    yield
