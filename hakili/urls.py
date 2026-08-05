"""Routage racine — Hakili Lab.

Django porte toute l'interface depuis le retrait de Streamlit (D-CEO-28 puis
D-CEO-39) : écrans de suivi, flux de correction (dépôt de copie, pipeline,
validation enseignant), et l'admin pour le référentiel importé.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("comptes.urls")),
    path("", include("correction_web.urls")),
    path("", include("suivi_web.urls")),
]

admin.site.site_header = "Hakili Lab — administration"
admin.site.site_title = "Hakili Lab"
admin.site.index_title = "Référentiel et suivi des élèves"
