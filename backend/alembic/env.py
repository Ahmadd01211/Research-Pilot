from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings
from app.infrastructure.database.base import Base
from app.modules.documents import models as document_models  # noqa: F401
from app.modules.exports import models as export_models  # noqa: F401
from app.modules.gaps import models as gap_models  # noqa: F401
from app.modules.identity import models  # noqa: F401
from app.modules.matrix import models as matrix_models  # noqa: F401
from app.modules.projects import models as project_models  # noqa: F401
from app.modules.references import models as reference_models  # noqa: F401
from app.modules.writing import models as writing_models  # noqa: F401

engine = create_engine(get_settings().database_url.get_secret_value(), poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
