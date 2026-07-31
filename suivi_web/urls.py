from django.urls import path

from suivi_web import views

app_name = "suivi_web"

# Les élèves et les copies sont désignés par un jeton signé, jamais par
# `identifiant_hakili` ni `copy_id` en clair — voir suivi_web/jetons.py.
urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("eleve/<str:jeton>/", views.eleve_detail, name="eleve_detail"),
    path("document/<str:jeton>/<str:doc_type>/", views.document, name="document"),
    path("parcours/<str:jeton>/", views.session_detail, name="session_detail"),
    path("parcours/<str:jeton>/inscrire/", views.inscrire, name="inscrire"),
    path("personnel/", views.personnel, name="personnel"),
    path("statistiques/", views.statistiques, name="statistiques"),
]
