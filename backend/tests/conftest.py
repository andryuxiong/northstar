"""Keep automated verification isolated from the personal Northstar database."""

import os
from pathlib import Path


TEST_DATA_DIR = Path(__file__).resolve().parent / ".data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_DATABASE = TEST_DATA_DIR / "northstar-test.db"

for suffix in ("", "-shm", "-wal"):
    (Path(f"{TEST_DATABASE}{suffix}")).unlink(missing_ok=True)
(TEST_DATA_DIR / "integrations-test.json").unlink(missing_ok=True)

# This runs before test modules import app.settings/app.db.session.
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["INTEGRATION_CONFIG_PATH"] = str(TEST_DATA_DIR / "integrations-test.json")
