from pathlib import Path
from pydantic import model_validator
from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / '.env', extra='ignore', hide_input_in_errors=True)
    app_env: str = 'development'
    database_url: str = 'sqlite:///./smartorder.db'
    frontend_url: str = 'http://localhost:5173'
    allowed_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    seed_demo: bool = False  # legacy flag: enables demo link only, never automatic seeding
    migration_database_url: str = ''
    enable_demo_link: bool = True
    cookie_secure: bool = False
    demo_admin_email: str = 'admin@smartburger.demo'
    demo_admin_password: str = 'SmartBurger!2026'
    openai_api_key: str = ''
    openai_model: str = 'gpt-4.1-mini'

    @model_validator(mode='after')
    def production_guard(self):
        if self.app_env == 'production':
            if self.seed_demo or self.enable_demo_link or not self.cookie_secure:
                raise ValueError('Production requires demo flags=false and COOKIE_SECURE=true')
            if not self.frontend_url.startswith('https://') or self.frontend_url.rstrip('/') not in self.allowed_origins:
                raise ValueError('Production FRONTEND_URL must be HTTPS and present in ALLOWED_ORIGINS')
            if not self.allowed_origins or any(not x.startswith('https://') or '*' in x for x in self.allowed_origins):
                raise ValueError('Production ALLOWED_ORIGINS must contain explicit HTTPS origins')
            if not self.migration_database_url or '-pooler' in (make_url(self.migration_database_url).host or ''):
                raise ValueError('Production requires a direct MIGRATION_DATABASE_URL')
            for value in [self.database_url, self.migration_database_url]:
                if not value:
                    continue
                url = make_url(value)
                if not url.drivername.startswith(('postgres', 'postgresql')) or url.query.get('sslmode') not in ('require','verify-ca','verify-full'):
                    raise ValueError('Production requires PostgreSQL with sslmode=require or stronger')
        return self

settings = Settings()
