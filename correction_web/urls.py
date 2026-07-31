from django.urls import path

from correction_web import views

app_name = "correction_web"

urlpatterns = [
    path("corrections/", views.liste, name="liste"),
    path("corrections/nouvelle/", views.nouvelle, name="nouvelle"),
    path("corrections/lot/", views.lot, name="lot"),
    path("sujets/", views.sujets, name="sujets"),
    path("sujets/<str:bareme_id>/", views.sujet, name="sujet"),
    path("corrections/<str:jeton>/", views.suivre, name="suivre"),
    path("corrections/<str:jeton>/transcription/", views.valider_transcription, name="valider_transcription"),
    path("corrections/<str:jeton>/notes/", views.valider_notes, name="valider_notes"),
]
