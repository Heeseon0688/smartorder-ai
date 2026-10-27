"""Isolated local/CI E2E server; never reset an application database."""
import os
import secrets
import signal
import subprocess
import sys
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def main():
    if os.environ.get('APP_ENV') != 'test':
        raise SystemExit('E2E server requires APP_ENV=test')
    env={**os.environ,'MIGRATION_DATABASE_URL':''}
    control=None
    schema=None
    process=None
    def stop(*_): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    try:
        if env.get('E2E_DATABASE_URL'):
            url=make_url(env['E2E_DATABASE_URL'])
            if url.drivername in ('postgres','postgresql'): url=url.set(drivername='postgresql+psycopg')
            if url.get_backend_name()!='postgresql': raise SystemExit('E2E_DATABASE_URL must use PostgreSQL')
            schema='smartorder_e2e_'+secrets.token_hex(8)
            control=create_engine(url,hide_parameters=True)
            with control.begin() as conn: conn.exec_driver_sql(f'CREATE SCHEMA {schema}')
            env['DATABASE_URL']=url.update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False)
        for command in ('migrate','seed-demo'):
            subprocess.run([sys.executable,'-m','app.manage',command],env=env,check=True)
        process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--no-access-log'],env=env)
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill();process.wait()
        if control and schema:
            with control.begin() as conn: conn.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
            control.dispose()

if __name__=='__main__':main()
