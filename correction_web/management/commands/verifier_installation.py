"""
Contrôle avant mise en service, et essai de correction de bout en bout.

    python manage.py verifier_installation
    python manage.py verifier_installation --copie chemin/vers/copie.pdf --test urie_3eme

Sans argument, la commande ne fait que vérifier la configuration — aucune API
n'est appelée, rien n'est écrit. Avec `--copie`, elle exécute une correction
complète sur une vraie copie : c'est le seul contrôle qui prouve que la chaîne
tient de bout en bout, et c'est le préalable au retrait de Streamlit
(voir docs/urie_v2_roadmap.md).
"""
from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Vérifie la configuration, et optionnellement corrige une copie réelle."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--copie", type=str, default="", help="Chemin d'une copie à corriger")
        parser.add_argument("--test", type=str, default="", help="Identifiant du test du catalogue")
        parser.add_argument("--eleve", type=str, default="", help="identifiant_hakili de l'élève")

    def handle(self, *args, **options) -> None:
        self.echecs: list[str] = []

        self.stdout.write(self.style.MIGRATE_HEADING("\nConfiguration"))
        self._verifier_django()
        self._verifier_base()
        self._verifier_sheets()
        self._verifier_cles_ia()
        self._verifier_referentiel()
        self._verifier_stockage()

        if options["copie"]:
            self.stdout.write(self.style.MIGRATE_HEADING("\nEssai de correction"))
            self._essai_reel(options)

        self.stdout.write("")
        if self.echecs:
            self.stdout.write(
                self.style.ERROR(f"{len(self.echecs)} point(s) à corriger avant mise en service :")
            )
            for echec in self.echecs:
                self.stdout.write(f"  · {echec}")
        else:
            self.stdout.write(self.style.SUCCESS("Tout est en place."))

    # ── Contrôles ────────────────────────────────────────────────────────────

    def _ok(self, libelle: str, detail: str = "") -> None:
        self.stdout.write(f"  {self.style.SUCCESS('OK')}    {libelle}" + (f" — {detail}" if detail else ""))

    def _alerte(self, libelle: str, detail: str = "") -> None:
        self.stdout.write(f"  {self.style.WARNING('note')}  {libelle}" + (f" — {detail}" if detail else ""))

    def _echec(self, libelle: str, detail: str = "") -> None:
        self.stdout.write(f"  {self.style.ERROR('MANQUE')} {libelle}" + (f" — {detail}" if detail else ""))
        self.echecs.append(f"{libelle}{f' ({detail})' if detail else ''}")

    def _verifier_django(self) -> None:
        from django.conf import settings

        if settings.DEBUG:
            self._alerte(
                "DEBUG est actif",
                "acceptable en local, à désactiver en production",
            )
        else:
            self._ok("DEBUG désactivé")
            if not settings.ALLOWED_HOSTS:
                self._echec(
                    "DJANGO_ALLOWED_HOSTS vide",
                    "l'application refusera toutes les requêtes",
                )
            else:
                self._ok("Domaines autorisés", ", ".join(settings.ALLOWED_HOSTS))
            if not settings.CSRF_TRUSTED_ORIGINS:
                self._alerte(
                    "DJANGO_CSRF_TRUSTED_ORIGINS vide",
                    "les formulaires échoueront derrière un proxy HTTPS",
                )

        if os.environ.get("DJANGO_SECRET_KEY"):
            self._ok("Clé secrète Django définie")
        elif settings.DEBUG:
            self._alerte("Clé secrète de développement", "obligatoire hors DEBUG")

    def _verifier_base(self) -> None:
        from django.db import connection

        try:
            with connection.cursor() as curseur:
                curseur.execute("SELECT 1")
            self._ok("Base joignable", connection.settings_dict.get("HOST") or "locale")
        except Exception as exc:  # noqa: BLE001
            self._echec("Base injoignable", str(exc)[:120])
            return

        from django.db.migrations.executor import MigrationExecutor

        executeur = MigrationExecutor(connection)
        en_attente = executeur.migration_plan(executeur.loader.graph.leaf_nodes())
        if en_attente:
            self._echec(
                f"{len(en_attente)} migration(s) non appliquée(s)", "lancer manage.py migrate"
            )
        else:
            self._ok("Migrations à jour")

    def _verifier_sheets(self) -> None:
        try:
            from src.integrations import google_sheets

            eleves = google_sheets.get_eleves()
            personnel = google_sheets.get_personnel()
        except Exception as exc:  # noqa: BLE001
            self._echec("Google Sheets injoignables", str(exc)[:120])
            return

        self._ok("Sheet élèves", f"{len(eleves)} élèves")

        sans_pin = [p for p in personnel if not str(p.get("pin") or "").strip()]
        self._ok("Sheet personnel", f"{len(personnel)} personnes")
        if sans_pin:
            self._alerte(
                f"{len(sans_pin)} personne(s) sans code PIN",
                "elles ne pourront pas se connecter",
            )

    def _verifier_cles_ia(self) -> None:
        from src.core.config import settings as config

        # Claude est le filet de secours de toutes les étapes et le seul provider
        # de l'extraction de barème : son absence bloque toute correction.
        if config.anthropic_api_key:
            self._ok("Clé Anthropic")
        else:
            self._echec(
                "ANTHROPIC_API_KEY absente",
                "aucune correction ne peut démarrer",
            )

        optionnelles = [
            ("Gemini (transcription)", config.google_api_key),
            ("DeepSeek (correction)", config.deepseek_api_key),
            ("Mistral (remédiation)", config.mistral_api_key),
        ]
        for libelle, cle in optionnelles:
            if cle:
                self._ok(f"Clé {libelle}")
            else:
                self._alerte(
                    f"Clé {libelle} absente", "le pipeline basculera sur Claude, plus cher"
                )

    def _verifier_referentiel(self) -> None:
        from referentiel.models import Competence, Question, TypeErreur

        try:
            n_comp, n_types, n_quest = (
                Competence.objects.count(),
                TypeErreur.objects.count(),
                Question.objects.count(),
            )
        except Exception as exc:  # noqa: BLE001
            self._echec("Référentiel illisible", str(exc)[:120])
            return

        if n_comp == 0:
            self._alerte(
                "Référentiel non importé",
                "lancer manage.py importer_referentiel",
            )
        else:
            self._ok(
                "Référentiel importé",
                f"{n_comp} compétences, {n_types} types d'erreur, {n_quest} questions",
            )

        from src.knowledge.test_registry import get_registry

        tests = get_registry().available_tests()
        if tests:
            self._ok("Tests proposables", f"{len(tests)}")
        else:
            self._echec("Aucun test proposable", "le catalogue est vide")

    def _verifier_stockage(self) -> None:
        from src.core.config import settings as config

        dossier = Path(config.runs_dir)
        try:
            dossier.mkdir(parents=True, exist_ok=True)
            temoin = dossier / ".ecriture_test"
            temoin.write_text("ok", encoding="utf-8")
            temoin.unlink()
        except Exception as exc:  # noqa: BLE001
            self._echec(f"Dossier {dossier} non inscriptible", str(exc)[:120])
            return

        self._ok(f"Dossier {dossier} inscriptible")
        self._alerte(
            "Fichiers intermédiaires sur disque local",
            "sans volume persistant, une correction en cours est perdue au redéploiement",
        )

        import shutil

        if shutil.which("xelatex"):
            self._ok("XeLaTeX disponible")
        else:
            self._alerte("XeLaTeX absent", "les rapports PDF passeront par le rendu de repli")

    # ── Essai réel ───────────────────────────────────────────────────────────

    def _essai_reel(self, options: dict) -> None:
        """Exécute une correction complète — c'est le contrôle qui manque avant de
        retirer Streamlit."""
        chemin = Path(options["copie"]).expanduser().resolve()
        if not chemin.exists():
            self._echec("Copie introuvable", str(chemin))
            return

        from src.knowledge.test_registry import get_registry

        registre = get_registry()
        test = registre.get_test(options["test"]) if options["test"] else None
        if test is None:
            disponibles = ", ".join(registre.available_tests())
            self._echec("Test inconnu", f"choisir parmi : {disponibles}")
            return

        identifiant = options["eleve"]
        if not identifiant:
            self._echec("--eleve manquant", "identifiant_hakili de l'élève")
            return

        from src.pipeline.pipeline import run_phase_a, run_phase_b

        def progression(etape: str, pourcentage: int) -> None:
            self.stdout.write(f"    {pourcentage:3d}%  {etape}")

        self.stdout.write("  Phase A — transcription et correction")
        resultat = run_phase_a(
            copy_id=f"verif-{chemin.stem}",
            identifiant_hakili=identifiant,
            student_name="Essai de vérification",
            file_paths=[chemin],
            rubric=test.rubric,
            subject_text=test.subject_text,
            bareme_id=test.bareme_id,
            official_answers=test.official_answers,
            on_progress=progression,
        )
        if resultat.grade is None:
            self._echec("Phase A échouée", " · ".join(resultat.errors)[:200])
            return
        self._ok(
            "Phase A",
            f"{len(resultat.grade.questions)} questions corrigées, "
            f"score IA {resultat.grade.total_score:g}/{resultat.grade.total_possible:g}",
        )

        # Toutes les notes acceptées : on vérifie la chaîne, pas le jugement.
        resultat.grade.compute_final_score()

        self.stdout.write("  Phase B — diagnostic et rapport")
        resultat = run_phase_b(result=resultat, on_progress=progression)
        if resultat.errors:
            self._echec("Phase B échouée", " · ".join(resultat.errors)[:200])
            return

        self._ok("Phase B", f"note finale {resultat.grade.final_score_on_20}/20")
        if resultat.pdf_path:
            self._ok("Rapport PDF", str(resultat.pdf_path))
        else:
            self._alerte("Aucun rapport PDF produit")
        if resultat.diagnostic and resultat.diagnostic.competency_gaps:
            self._ok(
                "Diagnostic ancré",
                f"{len(resultat.diagnostic.competency_gaps)} lacunes rattachées au programme",
            )
