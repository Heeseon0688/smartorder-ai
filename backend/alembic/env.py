from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from app.config import settings
from app.db import Base, normalize_url
from app import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
# Never put database credentials into alembic.ini, CLI output or ConfigParser.
url = normalize_url(settings.migration_database_url or settings.database_url)

def run_migrations_offline():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        # Serialize migrations across overlapping Render deploys (direct Neon URL).
        postgres = connection.dialect.name == 'postgresql'
        if postgres:
            connection.exec_driver_sql('SELECT pg_advisory_lock(839271401)')
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True, render_as_batch=not postgres)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if postgres:
                connection.exec_driver_sql('SELECT pg_advisory_unlock(839271401)')
                connection.commit()
    engine.dispose()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
