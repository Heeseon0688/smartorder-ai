import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect
from app.config import Settings
from app.db import SessionLocal, normalize_url
from app.models import WebSocketTicket, Store, utcnow
from datetime import timedelta


def test_neon_url_normalization():
    url=normalize_url('postgresql://user:encoded%40password@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require')
    assert url.drivername=='postgresql+psycopg'
    assert url.password=='encoded@password'
    assert url.query['sslmode']=='require'

@pytest.mark.parametrize('changes',[
    {'cookie_secure':False}, {'seed_demo':True}, {'enable_demo_link':True},
    {'database_url':'sqlite:///./example.db'}, {'allowed_origins':['*']},
    {'frontend_url':'http://example.com'},
])
def test_production_guard(changes):
    values=dict(app_env='production',cookie_secure=True,seed_demo=False,enable_demo_link=False,
        database_url='postgresql://u:p@db.example/app?sslmode=require',migration_database_url='postgresql://u:p@db.example/app?sslmode=require',
        frontend_url='https://app.example',allowed_origins=['https://app.example'])
    values.update(changes)
    with pytest.raises(ValueError): Settings(_env_file=None,**values)


def test_ticket_without_browser_cookie_is_single_use(admin):
    from fastapi.testclient import TestClient
    from app.main import app
    ticket=admin.post('/api/auth/ws-ticket').json()['ticket']
    clean=TestClient(app)
    origin={'Origin':'http://localhost:5173'}
    with clean.websocket_connect('/ws',headers=origin) as ws:
        ws.send_json({'role':'admin','ticket':ticket})
        assert ws.receive_json()['type']=='connected'
        with clean.websocket_connect('/ws',headers=origin) as replay:
            replay.send_json({'role':'admin','ticket':ticket})
            with pytest.raises(WebSocketDisconnect) as error: replay.receive_json()
            assert error.value.code==4401
        admin.post('/api/auth/logout')
        ws.send_text('ping')
        with pytest.raises(WebSocketDisconnect): ws.receive_json()


def test_ticket_expiration_and_logout_revocation(admin):
    from fastapi.testclient import TestClient
    from app.main import app
    response=admin.post('/api/auth/ws-ticket')
    assert response.json()['expires_in']==30
    assert response.headers['cache-control']=='no-store'
    with SessionLocal() as db:
        ticket=db.scalar(select(WebSocketTicket));ticket.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    with TestClient(app).websocket_connect('/ws',headers={'Origin':'http://localhost:5173'}) as ws:
        ws.send_json({'role':'admin','ticket':response.json()['ticket']})
        with pytest.raises(WebSocketDisconnect):ws.receive_json()
    admin.post('/api/auth/ws-ticket')
    admin.post('/api/auth/logout')
    with SessionLocal() as db: assert db.scalar(select(WebSocketTicket)) is None


def run_manage(directory,*args):
    env={**os.environ,'APP_ENV':'test','DATABASE_URL':f'sqlite:///{directory}/migration.db','MIGRATION_DATABASE_URL':'','OPENAI_API_KEY':''}
    return subprocess.run([sys.executable,'-m','app.manage',*args],env=env,capture_output=True,text=True,check=True)


def test_migration_explicit_seed_and_preserved_rows(tmp_path):
    from sqlalchemy import create_engine,text
    run_manage(tmp_path,'migrate')
    engine=create_engine(f'sqlite:///{tmp_path}/migration.db')
    with engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM stores')).scalar()==0
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0002'
    run_manage(tmp_path,'seed-demo')
    with engine.connect() as c:
        orders=c.execute(text('SELECT COUNT(*),SUM(total) FROM orders')).one()
    run_manage(tmp_path,'migrate')
    run_manage(tmp_path,'seed-demo')
    with engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*),SUM(total) FROM orders')).one()==orders
    engine.dispose()


def test_existing_legacy_adoption_is_additive(tmp_path):
    from sqlalchemy import create_engine,text
    env={**os.environ,'APP_ENV':'test','DATABASE_URL':f'sqlite:///{tmp_path}/migration.db','MIGRATION_DATABASE_URL':''}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0001'],env=env,check=True,capture_output=True)
    run_manage(tmp_path,'seed-demo')
    engine=create_engine(env['DATABASE_URL'])
    with engine.begin() as c:
        before=c.execute(text('SELECT COUNT(*),SUM(total) FROM orders')).one()
        c.execute(text('DROP TABLE alembic_version'))  # only this test's temporary database
    run_manage(tmp_path,'adopt-legacy')
    with engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*),SUM(total) FROM orders')).one()==before
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0002'
    engine.dispose()


def test_valid_production_configuration():
    value=Settings(_env_file=None,app_env='production',cookie_secure=True,seed_demo=False,enable_demo_link=False,
        database_url='postgresql://u:p@db-pooler.example/app?sslmode=require',
        migration_database_url='postgresql://u:p@db.example/app?sslmode=require',
        frontend_url='https://app.example',allowed_origins=['https://app.example'])
    assert value.cookie_secure


def test_bootstrap_with_menu_adds_catalog_without_orders_or_demo_account(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL','owner@example.com')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','a-unique-owner-passphrase')
    run_manage(tmp_path,'migrate')
    run_manage(tmp_path,'bootstrap','--with-menu')
    engine=create_engine(f'sqlite:///{tmp_path}/migration.db')
    with engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM menus')).scalar()==16
        assert c.execute(text('SELECT COUNT(*) FROM tables')).scalar()==10
        assert c.execute(text('SELECT COUNT(*) FROM orders')).scalar()==0
        assert c.execute(text('SELECT email FROM admin_users')).scalars().all()==['owner@example.com']
    with pytest.raises(subprocess.CalledProcessError):
        run_manage(tmp_path,'bootstrap','--with-menu')  # never overwrites an existing store/admin
    engine.dispose()
