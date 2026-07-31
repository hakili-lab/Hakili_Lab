"""Routage racine — Hakili Lab.

Migration de Streamlit vers Django (D-CEO-28) : les écrans de suivi sont servis
ici, l'admin donne accès au référentiel importé. Le flux de correction (dépôt de
copie, pipeline, validation enseignant) reste sur Streamlit le temps de sa
migration — voir docs/urie_v2_roadmap.md.
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
