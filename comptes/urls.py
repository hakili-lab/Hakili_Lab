from django.urls import path

from comptes import views

app_name = "comptes"

urlpatterns = [
    path("connexion/", views.connexion, name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("casquette/", views.choisir_casquette, name="casquette"),
]
