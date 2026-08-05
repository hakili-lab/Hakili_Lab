from django.apps import AppConfig


class CorrectionWebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "correction_web"
    verbose_name = "Correction de copies"

    def ready(self) -> None:
        """Installe le dépôt de copies pour le pipeline.

        Le pipeline (`src/`) ne connaît pas Django : il écrit dans le dépôt qu'on
        lui installe ici (D-CEO-40). C'est le seul endroit où les deux se
        rencontrent, et il est volontairement minuscule.

        L'import est local pour la raison habituelle des `ready()` : au moment où
        Django charge cette classe, le registre des modèles n'est pas encore
        prêt, et `depot.py` importe `suivi.models`.
        """
        from src.pipeline.depot import installer_depot

        from correction_web.depot import DepotDjango

        installer_depot(DepotDjango())
