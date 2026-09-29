from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy ORM 모델을 도입하는 단계에서 Base.metadata로 교체합니다.
target_metadata = None


def get_database_url() -> str:
    """환경변수로부터 PostgreSQL 접속 URL을 안전하게 만듭니다."""
    password = os.getenv("DC_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "DC_DB_PASSWORD 환경변수가 없습니다. "
            "read -s DC_DB_PASSWORD 후 export DC_DB_PASSWORD를 실행하세요."
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DC_DB_USER", "dc_app"),
        password=password,
        host=os.getenv("DC_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DC_DB_PORT", "5432")),
        database=os.getenv("DC_DB_NAME", "dc_platform"),
    )

    # ConfigParser가 URL의 퍼센트 문자를 보간식으로 오해하지 않게 처리합니다.
    return url.render_as_string(hide_password=False).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_database_url())


def run_migrations_offline() -> None:
    """DB에 접속하지 않고 실행용 SQL을 생성합니다."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB에 접속하여 마이그레이션을 실행합니다."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
