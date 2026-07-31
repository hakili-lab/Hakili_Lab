"""
Administration du référentiel — consultation surtout, correction à la marge.

Le référentiel vient du classeur et y retourne : corriger une ligne ici la ferait
diverger de la source, et le prochain `importer_referentiel` écraserait la
correction. Les écrans sont donc volontairement en lecture pour tout ce que
l'import régénère (signatures, options, coûts, prérequis) et laissés modifiables
là où c'est utile — notamment `Question.reponse_attendue` et `Question.solution`,
les 209 corrigés manquants que quelqu'un devra bien saisir (arbitrage B).

⚠ Un `importer_referentiel` écrase les corrigés saisis ici. Tant que l'arbitrage B
n'est pas rendu, sauvegarder avant de réimporter.
"""
from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from referentiel.models import (
    Competence,
    CoutRemediation,
    OptionQcm,
    Prerequis,
    Question,
    SignatureErreur,
    TypeErreur,
)


@admin.register(TypeErreur)
class TypeErreurAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "coefficient", "remediable", "nb_signatures")
    list_filter = ("remediable",)
    search_fields = ("code", "libelle", "definition")
    readonly_fields = ("code",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("signatures"))

    @admin.display(description="signatures", ordering="_n")
    def nb_signatures(self, obj) -> int:
        return obj._n


class PrerequisInline(admin.TabularInline):
    model = Prerequis
    fk_name = "competence"
    extra = 0
    autocomplete_fields = ("prerequis",)
    verbose_name_plural = "Prérequis directs (régénérés à chaque import)"


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = (
        "code", "libelle", "domaine", "niveau_intro",
        "volume_affiche", "transversale", "nb_questions",
    )
    list_filter = ("domaine", "niveau_intro", "transversale", "volume_estime")
    search_fields = ("code", "libelle", "description")
    inlines = [PrerequisInline]
    ordering = ("domaine", "code")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_nq=Count("questions"))

    @admin.display(description="questions", ordering="_nq")
    def nb_questions(self, obj) -> int:
        return obj._nq

    @admin.display(description="volume horaire", ordering="volume_horaire")
    def volume_affiche(self, obj):
        if obj.volume_horaire is None:
            return format_html('<span style="color:#c0392b;">non disponible</span>')
        if obj.volume_estime:
            # Un volume de repli ne doit jamais passer pour un chiffre du
            # curriculum : c'est lui qui détermine le palier d'un élève.
            return format_html(
                '{} <span style="color:#e67e22;font-size:11px;">estimé</span>',
                f"{obj.volume_horaire:g} h",
            )
        return f"{obj.volume_horaire:g} h"


@admin.register(CoutRemediation)
class CoutRemediationAdmin(admin.ModelAdmin):
    list_display = ("competence", "type_erreur", "cout_affiche", "derivation")
    list_filter = ("estime", "type_erreur", "competence__domaine")
    search_fields = ("competence__code", "competence__libelle")
    autocomplete_fields = ("competence",)

    @admin.display(description="coût", ordering="cout_heures")
    def cout_affiche(self, obj):
        if obj.estime:
            return format_html(
                '{} <span style="color:#e67e22;font-size:11px;">estimé</span>',
                f"{obj.cout_heures:g} h",
            )
        return f"{obj.cout_heures:g} h"

    def has_add_permission(self, request) -> bool:
        return False  # calculé par l'import, jamais saisi

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class OptionQcmInline(admin.TabularInline):
    model = OptionQcm
    extra = 0
    fields = ("lettre", "texte", "correcte", "type_erreur", "erreur")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class SignatureErreurInline(admin.TabularInline):
    model = SignatureErreur
    extra = 0
    fields = ("type_erreur", "production_eleve", "interpretation")
    readonly_fields = fields
    can_delete = False
    verbose_name_plural = "Signatures d'erreur — ce qu'on lit sur la copie"

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "code_question", "niveau_test", "partie", "format",
        "competence", "bareme_affiche", "corrige_affiche", "objet_court",
    )
    list_filter = ("niveau_test", "partie", "format", "competence__domaine")
    search_fields = ("code_question", "objet", "competence__code", "competence__libelle")
    autocomplete_fields = ("competence", "competence_secondaire")
    inlines = [OptionQcmInline, SignatureErreurInline]
    list_select_related = ("competence",)
    # Tout vient du classeur sauf le corrigé, qui n'y est pas : c'est le seul
    # endroit où une saisie manuelle a du sens.
    readonly_fields = (
        "code_question", "niveau_test", "partie", "format", "bareme",
        "bareme_classeur", "code_local", "competence", "competence_secondaire", "objet",
    )
    fieldsets = (
        ("Identification (classeur)", {
            "fields": ("niveau_test", "code_question", "partie", "format", "code_local")
        }),
        ("Barème", {
            "fields": ("bareme", "bareme_classeur"),
            "description": "Barème sur 20 ; « classeur » conserve l'échelle d'origine sur 60.",
        }),
        ("Compétences (classeur)", {"fields": ("competence", "competence_secondaire")}),
        ("Énoncé", {"fields": ("objet",)}),
        ("Corrigé — à saisir", {
            "fields": ("reponse_attendue", "solution"),
            "description": (
                "Le classeur ne fournit de bonne réponse que pour les QCM. "
                "⚠ Un réimport du référentiel écrase ce qui est saisi ici."
            ),
        }),
    )

    @admin.display(description="barème", ordering="bareme")
    def bareme_affiche(self, obj) -> str:
        return f"{obj.bareme:.4f}".rstrip("0").rstrip(".")

    @admin.display(description="corrigé", boolean=True, ordering="reponse_attendue")
    def corrige_affiche(self, obj) -> bool:
        return obj.a_corrige

    @admin.display(description="objet")
    def objet_court(self, obj) -> str:
        return obj.objet[:70] + ("…" if len(obj.objet) > 70 else "")

    def has_add_permission(self, request) -> bool:
        return False  # les questions viennent du classeur

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(SignatureErreur)
class SignatureErreurAdmin(admin.ModelAdmin):
    list_display = ("question", "type_erreur", "competence", "production_courte")
    list_filter = ("type_erreur", "question__niveau_test", "competence__domaine")
    search_fields = ("production_eleve", "interpretation", "question__code_question")
    list_select_related = ("question", "type_erreur", "competence")

    @admin.display(description="ce qu'on lit sur la copie")
    def production_courte(self, obj) -> str:
        return obj.production_eleve[:80] + ("…" if len(obj.production_eleve) > 80 else "")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(OptionQcm)
class OptionQcmAdmin(admin.ModelAdmin):
    list_display = ("question", "lettre", "texte", "correcte", "type_erreur")
    list_filter = ("correcte", "type_erreur", "question__niveau_test")
    search_fields = ("texte", "erreur", "question__code_question")
    list_select_related = ("question", "type_erreur")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
