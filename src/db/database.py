import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings
from src.db.models import Base

logger = logging.getLogger(__name__)

# Neon (pooler PgBouncer) met la base en veille après inactivité : les
# connexions gardées dans le pool SQLAlchemy deviennent alors mortes sans
# préavis. pool_pre_ping teste chaque connexion (SELECT 1) avant usage et la
# remplace si elle est morte — c'est le correctif de la cause, le retry
# tenacity aux points d'écriture reste un filet pour les erreurs réseau
# transitoires, il est complémentaire et n'est pas retiré.
# pool_recycle=300 recycle toute connexion inactive depuis plus de 5 minutes,
# aligné sur le délai d'auto-suspend par défaut de Neon (5 min sur le palier
# gratuit) : inutile de garder une connexion que Neon aura de toute façon
# fermée de son côté.
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)

logger.info(
    "Engine DB créé (pool_pre_ping=%s, pool_recycle=%s)",
    engine.pool._pre_ping,
    engine.pool._recycle,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crée toutes les tables en base à partir des modèles.

    Utilitaire de confort pour des tests locaux rapides. Alembic
    (migrations/) reste la source de vérité du schéma en pratique —
    cette fonction n'est jamais appelée automatiquement par l'app.
    """
    Base.metadata.create_all(bind=engine)
