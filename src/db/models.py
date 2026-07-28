import uuid
from datetime import date
from enum import Enum as PyEnum

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, PyEnum):
    """Valeurs alignées sur la colonne `role` du Sheet profs (Google Sheets,
    source de vérité de l'identité — voir src/integrations/google_sheets.py)
    : ce n'est plus un type de colonne SQL depuis que l'identité des profs a
    quitté PostgreSQL, seulement un enum Python pour comparer proprement le
    profil choisi au login au rôle lu dans le Sheet."""
    admin = "administrateur"
    responsable_centre = "responsable"
    enseignant = "enseignant"


class Copie(Base):
    """L'identité de l'élève (nom, prénom, classe administrative, centre,
    contact) vit désormais dans les Google Sheets (src/integrations/
    google_sheets.py) — PostgreSQL ne stocke plus que ce qui concerne la
    correction elle-même : l'identifiant_hakili (texte, calculé depuis les
    Sheets) relie la copie à un élève sans dupliquer son identité en base."""
    __tablename__ = "copie"

    copy_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    identifiant_hakili: Mapped[str] = mapped_column(String(255))
    classe: Mapped[str] = mapped_column(String(50))
    annee_scolaire: Mapped[str] = mapped_column(String(50))
    date_soumission: Mapped[date] = mapped_column(default=date.today)
    notes_finales: Mapped[float | None] = mapped_column()

    documents: Mapped[list["Document"]] = relationship(back_populates="copie")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    copy_id: Mapped[str] = mapped_column(String(255), ForeignKey("copie.copy_id"))
    type: Mapped[str] = mapped_column(String(50))  # "scan", "rapport", "remediation"
    fichier: Mapped[bytes] = mapped_column(BYTEA)
    date_creation: Mapped[date] = mapped_column(default=date.today)

    copie: Mapped["Copie"] = relationship(back_populates="documents")
