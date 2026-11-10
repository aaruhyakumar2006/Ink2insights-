import sys
import os

# Automatically add project root to python path for all tests
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    import dotenv
    dotenv.load_dotenv(os.path.join(ROOT_DIR, "backend", ".env"))
except ImportError:
    pass

import pytest

@pytest.fixture
def client(tmp_path):
    """Reusable test client fixture for API & asset tests."""
    from backend.app import create_app
    from backend import database
    from backend.services.auth_service import create_access_token

    db_file = str(tmp_path / "test_client.db")
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    database.create_camp("Test Camp", 100, "Today", camp_id="camp_test_01", community_id="comm_test", db_path=db_file)
    token = create_access_token(user_id="doc_test", role="admin", org_id="comm_test")
    with app.test_client() as c:
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        yield c

