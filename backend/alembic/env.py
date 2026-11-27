from logging.config import fileConfig

from alembic import context

from app.core.database import DATABASE_URL, Base, engine

# Import ONLY active SQLAlchemy models so Alembic discovers the active schema
# and ignores legacy unmounted models in app.models.commerce / app.models.flash_sale.
import app.models.auth  # noqa: F401
import app.models.finance  # noqa: F401
import app.models.organisation  # noqa: F401
import app.models.payments  # noqa: F401
import app.models.retail  # noqa: F401
import app.models.rossmann  # noqa: F401
import app.models.simulation  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without exposing secrets."""
    context.configure(
        url=DATABASE_URL.render_as_string(hide_password=True),
        target_metadata=target_metadata,
        literal_binds=False,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the application's configured engine."""
    connectable = config.attributes.get("connection", None)

    if connectable is not None:
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    with engine.connect() as connection:
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
