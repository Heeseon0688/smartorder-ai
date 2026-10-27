"""Explicit, non-destructive administration commands. Never seed on startup."""
import argparse
import getpass
import os
import re
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, inspect, select
from .config import settings
from .db import Base, SessionLocal, engine
from .models import Store, Table, AdminUser
from .security import password_hasher
from .seed import seed
import secrets

def alembic_config():
    return Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))

def adopt_legacy():
    """Stamp only an exact known legacy schema. Does not recreate or drop tables."""
    with engine.connect() as connection:
        if 'alembic_version' in inspect(connection).get_table_names():
            raise SystemExit('Already versioned. Use migrate.')
        legacy = MetaData()
        for table in Base.metadata.sorted_tables:
            if table.name != 'websocket_tickets':
                table.to_metadata(legacy)
        differences = compare_metadata(MigrationContext.configure(connection), legacy)
        if differences:
            raise SystemExit('Legacy schema differs; automatic adoption refused. Review schema and backup first.')
    command.stamp(alembic_config(), '0001')
    command.upgrade(alembic_config(), 'head')
    print('Legacy schema adopted; existing rows preserved.')

def bootstrap(args):
    email = (os.environ.get('BOOTSTRAP_ADMIN_EMAIL') or input('Admin email: ')).strip().lower()
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD') or getpass.getpass('New admin password (16+ chars): ')
    if '@' not in email or len(password)<16 or password == settings.demo_admin_password:
        raise SystemExit('Use a valid email and a unique password of at least 16 characters; demo passwords are forbidden.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,79}', args.slug):
        raise SystemExit('Store slug must contain lowercase letters, digits or hyphens.')
    with SessionLocal() as db:
        if db.scalar(select(AdminUser).where(AdminUser.email==email)):
            raise SystemExit('Administrator already exists. No password or data was changed.')
        store = db.scalar(select(Store).where(Store.slug==args.slug))
        if store:
            raise SystemExit('Store already exists. Use a reviewed administrative workflow; no existing store was changed.')
        store = Store(slug=args.slug, name=args.name, description='')
        db.add(store); db.flush()
        db.add(AdminUser(store_id=store.id,email=email,name='관리자',password_hash=password_hasher.hash(password)))
        db.add_all(Table(store_id=store.id,number=n,token=secrets.token_urlsafe(32)) for n in range(1,11))
        from .models import MenuCategory
        db.add_all(MenuCategory(store_id=store.id,name=name,position=i) for i,name in enumerate(['버거','사이드','음료','디저트']))
        db.commit()
    print('Store, categories, 10 QR tables and administrator created. No demo orders or menu data added.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate')
    sub.add_parser('adopt-legacy')
    sub.add_parser('seed-demo')
    boot = sub.add_parser('bootstrap')
    boot.add_argument('--slug',default='smart-burger');boot.add_argument('--name',default='Smart Burger')
    args=parser.parse_args()
    if args.command == 'migrate': command.upgrade(alembic_config(),'head')
    elif args.command == 'adopt-legacy': adopt_legacy()
    elif args.command == 'seed-demo':
        if settings.app_env == 'production': raise SystemExit('Demo seeding is disabled in production.')
        with SessionLocal() as db:
            if db.scalar(select(Store).limit(1)):
                print('Existing store found. Nothing was changed.');return
            seed(db)
        print('Demo data created by explicit request.')
    else: bootstrap(args)

if __name__=='__main__': main()
