import csv
from pathlib import Path


class Anonymizer:
    """
    Attribue des identifiants anonymes (E-001, E-002…) aux élèves
    et persiste la fiche de correspondance dans un CSV séparé.
    """

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._mapping: dict[str, str] = {}  # nom → copy_id
        self._correspondence_path = session_dir / "correspondence.csv"

    def register(self, name: str) -> str:
        """Enregistre un élève et retourne son identifiant anonyme."""
        name = name.strip()
        if name in self._mapping:
            return self._mapping[name]
        copy_id = f"E-{len(self._mapping) + 1:03d}"
        self._mapping[name] = copy_id
        self._save()
        return copy_id

    def register_batch(self, names: list[str]) -> dict[str, str]:
        """Enregistre une liste d'élèves et retourne le mapping complet."""
        for name in names:
            self.register(name)
        return dict(self._mapping)

    def get_id(self, name: str) -> str | None:
        return self._mapping.get(name.strip())

    @property
    def correspondence_path(self) -> Path:
        return self._correspondence_path

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    def _save(self) -> None:
        with open(self._correspondence_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["nom", "id_anonyme"])
            for name, copy_id in self._mapping.items():
                writer.writerow([name, copy_id])
