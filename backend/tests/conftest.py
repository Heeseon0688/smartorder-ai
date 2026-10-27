import os
import atexit
import secrets
import tempfile
from pathlib import Path
import pytest

_test_dir = tempfile.TemporaryDirectory(prefix='smartorder-tests-')
if os.environ.get('TEST_DATABASE_URL'):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    url = make_url(os.environ['TEST_DATABASE_URL'])
    if url.drivername in ('postgres','postgresql'): url=url.set(drivername='postgresql+psycopg')
    if url.get_backend_name() != 'postgresql': raise RuntimeError('TEST_DATABASE_URL must use PostgreSQL')
    test_schema = 'smartorder_test_' + secrets.token_hex(8)
    control = create_engine(url, hide_parameters=True)
    with control.begin() as conn: conn.exec_driver_sql(f'CREATE SCHEMA {test_schema}')
    os.environ['DATABASE_URL'] = url.update_query_dict({'options':f'-csearch_path={test_schema}'}).render_as_string(hide_password=False)
    def cleanup_schema():
        engine.dispose()
        with control.begin() as conn: conn.exec_driver_sql(f'DROP SCHEMA {test_schema} CASCADE')
        control.dispose()
    atexit.register(cleanup_schema)
else:
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(_test_dir.name) / 'test.db'}"
os.environ['MIGRATION_DATABASE_URL'] = ''
os.environ['SEED_DEMO'] = 'true'
os.environ['OPENAI_API_KEY'] = ''
os.environ['APP_ENV'] = 'test'
os.environ['DEMO_ADMIN_EMAIL'] = 'admin@smartburger.demo'
os.environ['DEMO_ADMIN_PASSWORD'] = 'SmartBurger!2026'
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine
from app.security import limiter
from app.seed import seed
from app.db import SessionLocal

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    limiter.buckets.clear()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    with TestClient(app) as client:
        yield client

@pytest.fixture
def admin(client):
    response = client.post('/api/auth/login', json={'email':'admin@smartburger.demo','password':'SmartBurger!2026'})
    assert response.status_code == 200
    return client

@pytest.fixture
def customer(client):
    from urllib.parse import urlparse, parse_qs
    import uuid
    url = urlparse(client.get('/api/demo').json()['order_url'])
    token = parse_qs(url.query)['token'][0]
    headers = {'X-Table-Token': token, 'X-Customer-Token': uuid.uuid4().hex, 'Idempotency-Key': str(uuid.uuid4())}
    return '/api/stores/smart-burger/tables/1', headers
