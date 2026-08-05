"""`copie` et `document` passent de SQLAlchemy à Django (D-CEO-40).

⚠ **Sur une base qui porte déjà ces deux tables — la production Neon — cette
migration doit être appliquée avec `--fake` :**

    python manage.py migrate suivi 0007 --fake

Les tables existent depuis les migrations Alembic ; il n'y a rien à créer, seul
l'état de Django doit apprendre qu'il en est désormais responsable. Sur une base
neuve (tests, poste de développement) elle s'applique normalement et les crée.

**Si quelqu'un l'applique sans `--fake` sur la production, elle échoue** sur
« relation "copie" existe déjà », la transaction est annulée et rien n'est
perdu. C'est le bon comportement : bruyant plutôt que silencieux.

Pourquoi `DeleteModel` en état seulement : `Copie` existait déjà dans l'état de
Django, en `managed = False`. Django ne sait pas transformer un modèle non géré
en modèle géré — il produit un `AlterModelOptions` qui ne crée aucune table, et
on s'en aperçoit à la première base neuve, quand `document` reçoit une clé
étrangère vers une table absente. On retire donc l'ancien modèle de l'état sans
toucher à la base, puis on le recrée pour de bon.
"""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("suivi", "0006_session_corpus"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="Copie")],
            database_operations=[],
        ),
        migrations.CreateModel(
            name="Copie",
            fields=[
                ("copy_id", models.CharField(max_length=255, primary_key=True, serialize=False)),
                ("identifiant_hakili", models.CharField(max_length=255)),
                ("classe", models.CharField(max_length=50)),
                ("annee_scolaire", models.CharField(max_length=50)),
                ("date_soumission", models.DateField(default=django.utils.timezone.localdate)),
                ("notes_finales", models.FloatField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "copie",
                "verbose_name_plural": "copies",
                "db_table": "copie",
            },
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type", models.CharField(choices=[("scan", "scan"), ("rapport", "rapport"), ("remediation", "remédiation")], max_length=50)),
                ("fichier", models.BinaryField()),
                ("date_creation", models.DateField(default=django.utils.timezone.localdate)),
                ("copie", models.ForeignKey(db_column="copy_id", on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="suivi.copie")),
            ],
            options={
                "verbose_name": "document",
                "verbose_name_plural": "documents",
                "db_table": "document",
            },
        ),
    ]
