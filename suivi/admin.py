"""
Administration du suivi des élèves.

`Transition` est en lecture seule partout, délibérément : un historique qu'on peut
réécrire ne prouve rien, et c'est de lui que sortent les 5 indicateurs du module 9.
L'état d'un problème se change par `Probleme.changer_etat()`, qui écrit la
transition dans la même opération.
"""
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from suivi.models import (
    Copie,
    EtatProbleme,
    Evaluation,
    Probleme,
    Reponse,
    Seance,
    Session,
    Transition,
)

_COULEUR_ETAT = {
    EtatProbleme.HYPOTHESE: "#7f8c8d",
    EtatProbleme.CONFIRME: "#c0392b",
    EtatProbleme.ECARTE: "#95a5a6",
    EtatProbleme.EN_REMEDIATION: "#e67e22",
    EtatProbleme.RESOLU: "#27ae60",
    EtatProbleme.NON_RESOLU: "#c0392b",
    EtatProbleme.REGRESSE: "#d35400",
    EtatProbleme.CLOS: "#2c3e50",
}


class TransitionInline(admin.TabularInline):
    model = Transition
    extra = 0
    fields = ("date", "etat_avant", "etat_apres", "evaluation", "commentaire")
    readonly_fields = fields
    can_delete = False
    verbose_name_plural = "Historique des états (non modifiable)"

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class ProblemeInline(admin.TabularInline):
    model = Probleme
    extra = 0
    fields = ("competence", "type_erreur", "etat", "cout_estime")
    readonly_fields = ("competence", "type_erreur", "cout_estime")
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class EvaluationInline(admin.TabularInline):
    model = Evaluation
    extra = 0
    fields = ("type", "date", "duree_reelle", "support", "copie")
    show_change_link = True


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "identifiant_hakili", "date_debut", "palier",
        "etat", "nb_problemes", "cout_affiche",
    )
    list_filter = ("etat", "palier", "date_debut")
    search_fields = ("identifiant_hakili",)
    inlines = [EvaluationInline, ProblemeInline]
    date_hierarchy = "date_debut"

    @admin.display(description="problèmes")
    def nb_problemes(self, obj) -> str:
        total = obj.problemes.count()
        confirmes = obj.problemes.filter(etat=EtatProbleme.CONFIRME).count()
        return f"{total} ({confirmes} confirmés)"

    @admin.display(description="coût confirmé")
    def cout_affiche(self, obj) -> str:
        return f"{obj.cout_total_confirme:g} h"


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("type", "session", "date", "duree_reelle", "nb_reponses", "copie")
    list_filter = ("type", "date")
    search_fields = ("session__identifiant_hakili",)
    list_select_related = ("session",)
    date_hierarchy = "date"

    @admin.display(description="réponses")
    def nb_reponses(self, obj) -> int:
        return obj.reponses.count()


@admin.register(Probleme)
class ProblemeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "session", "etat_colore", "cout_estime", "nb_transitions")
    list_filter = ("etat", "type_erreur", "competence__domaine")
    search_fields = (
        "session__identifiant_hakili", "competence__code", "competence__libelle",
    )
    list_select_related = ("session", "competence", "type_erreur")
    inlines = [TransitionInline]
    # `etat` en lecture seule : le modifier ici contournerait `changer_etat()` et
    # laisserait l'historique incomplet, donc les indicateurs faux.
    readonly_fields = ("session", "competence", "type_erreur", "etat", "cout_estime")

    @admin.display(description="état", ordering="etat")
    def etat_colore(self, obj):
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            _COULEUR_ETAT.get(obj.etat, "#000"),
            obj.get_etat_display(),
        )

    @admin.display(description="transitions")
    def nb_transitions(self, obj) -> int:
        return obj.transitions.count()

    def has_add_permission(self, request) -> bool:
        return False  # créé par le diagnostic (module 4)


@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ("probleme", "etat_avant", "etat_apres", "date", "evaluation")
    list_filter = ("etat_apres", "date")
    search_fields = ("probleme__session__identifiant_hakili",)
    list_select_related = ("probleme", "evaluation")
    date_hierarchy = "date"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Reponse)
class ReponseAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "question", "correcte", "type_erreur_detecte")
    list_filter = ("correcte", "type_erreur_detecte", "question__niveau_test")
    search_fields = ("evaluation__session__identifiant_hakili", "question__code_question")
    list_select_related = ("evaluation", "question", "type_erreur_detecte")


@admin.register(Seance)
class SeanceAdmin(admin.ModelAdmin):
    list_display = ("date", "session", "tuteur", "duree", "nb_problemes")
    list_filter = ("date", "tuteur")
    search_fields = ("session__identifiant_hakili", "tuteur", "blocage", "deblocage")
    filter_horizontal = ("problemes_travailles",)
    date_hierarchy = "date"

    @admin.display(description="problèmes travaillés")
    def nb_problemes(self, obj) -> int:
        return obj.problemes_travailles.count()


@admin.register(Copie)
class CopieAdmin(admin.ModelAdmin):
    """Consultation uniquement, pour relier une évaluation à un scan existant.

    La table est passée sous Django (D-CEO-40) mais reste en lecture seule ici :
    une copie est produite par le pipeline, pas saisie à la main. La créer depuis
    l'admin donnerait une copie sans scan, sans note et sans document — une ligne
    qui ressemble à une copie sans en être une."""

    list_display = ("copy_id", "identifiant_hakili", "classe", "date_soumission", "notes_finales")
    search_fields = ("copy_id", "identifiant_hakili")
    list_filter = ("classe",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
