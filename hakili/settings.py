"""
Configuration Django — Hakili Lab.

Voir docs/architecture_cible.md pour le motif de la sortie de Streamlit.

Choix délibéré : ce module ne lit PAS `src/core/config.py`.
--------------------------------------------------------
`Settings()` (pydantic-settings) exige `anthropic_api_key` sans valeur par
défaut : l'importer ici ferait échouer `manage.py migrate` sur une machine sans
clé LLM, alors qu'une migration n'a aucun besoin d'appeler un modèle. Django lit
donc l'environnement directement. Les deux configurations coexistent pour des
besoins différents — le pipeline garde la sienne, inchangée.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# `.env` partagé avec le pipeline (mêmes DATABASE_URL et DEBUG).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv absent : on se contente de l'environnement
    pass


def _bool_env(nom: str, defaut: bool = False) -> bool:
    valeur = os.environ.get(nom)
    if valeur is None:
        return defaut
    return valeur.strip().lower() in {"1", "true", "yes", "oui", "on"}


# ── Sécurité ──────────────────────────────────────────────────────────────────

DEBUG = _bool_env("DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        # Jamais de clé de repli en production : elle invaliderait les sessions
        # et les jetons signés. Échouer bruyamment plutôt que démarrer affaibli.
        raise RuntimeError(
            "DJANGO_SECRET_KEY est obligatoire hors DEBUG. En générer une avec :\n"
            "  python -c \"from django.core.management.utils import "
            'get_random_secret_key as k; print(k())"'
        )
    SECRET_KEY = "dev-uniquement-ne-jamais-utiliser-en-production"

# HTTPS obligatoire dès qu'un code d'accès transite — l'application porte des
# données scolaires nominatives d'élèves mineurs (voir point ouvert #4 de
# docs/v2_roadmap.md : obligations à vérifier auprès de la CIL du Burkina Faso).
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # `SECURE_HSTS_PRELOAD` est délibérément laissé à False, et `check --deploy`
    # le signalera : l'inscription aux listes de préchargement des navigateurs est
    # une porte à sens unique — le domaine devra servir en HTTPS pour toujours, et
    # la radiation prend des mois. Elle n'a par ailleurs aucun sens sur un
    # sous-domaine mutualisé (`*.railway.app`, `*.onrender.com`), où l'en-tête est
    # hérité. À réexaminer le jour où un domaine propre est acquis.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Railway / Render

# ── Accès libre — DÉVELOPPEMENT UNIQUEMENT ───────────────────────────────────
# Ouvre l'application sans connexion, le temps que les Google Sheets soient
# configurés : sans eux, personne ne peut se connecter et rien n'est testable.
#
# Verrouillé sur DEBUG, délibérément. L'application porte des données scolaires
# nominatives d'élèves mineurs : hors DEBUG, ce réglage est IGNORÉ et l'oubli est
# journalisé bruyamment, plutôt que de laisser une base d'élèves accessible à qui
# connaît l'URL.
ACCES_LIBRE = _bool_env("HAKILI_ACCES_LIBRE", False)
if ACCES_LIBRE and not DEBUG:
    import logging as _logging

    _logging.getLogger(__name__).error(
        "HAKILI_ACCES_LIBRE est demandé hors DEBUG : IGNORÉ. Ce réglage ouvrirait "
        "l'accès aux données nominatives d'élèves mineurs à toute personne "
        "connaissant l'URL. Retirez-le de l'environnement de production."
    )
    ACCES_LIBRE = False

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
] or (["*"] if DEBUG else [])

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# ── Applications ──────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Applications Hakili
    "referentiel",  # importé du classeur, jamais saisi à la main
    "suivi",        # modèles de suivi, alimentés par l'usage
    "comptes",      # authentification adossée au Sheet personnel
    "suivi_web",    # écrans de suivi (migration depuis Streamlit)
    "correction_web",  # flux de correction : dépôt, validation, diagnostic
]

# Le Sheet personnel fait foi pour l'accès (D-CEO-21). `ModelBackend` reste en
# second pour que `createsuperuser` garde un chemin de secours si les Sheets sont
# injoignables — un compte local ne contourne rien : il n'a aucune affectation,
# donc aucun élève accessible.
AUTHENTICATION_BACKENDS = [
    "comptes.backends.SheetBackend",
    "django.contrib.auth.backends.ModelBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sert les fichiers statiques sans nginx devant : Railway et Render n'en
    # fournissent pas. Doit rester juste après SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hakili.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates_django"],
        "APP_DIRS": True,
        "OPTIONS": {
            "builtins": ["correction_web.templatetags.maths"],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "comptes.views.contexte_utilisateur",
            ],
        },
    },
]

WSGI_APPLICATION = "hakili.wsgi.application"
ASGI_APPLICATION = "hakili.asgi.application"


# ── Base de données — Neon Postgres (inchangée, décision du 2026-07-30) ───────

def _config_base(url: str) -> dict:
    """Traduit une URL de connexion en configuration Django.

    Écrit à la main plutôt qu'avec `dj-database-url` : quinze lignes ne justifient
    pas une dépendance de plus, et les paramètres de requête de l'URL Neon
    (`sslmode=require`, `channel_binding`) doivent être conservés tels quels.

    SQLite est accepté (`sqlite:///chemin.db`, `sqlite://:memory:`) pour que les
    tests et l'intégration continue tournent sans base Postgres à disposition —
    la production reste sur Neon (décision du 2026-07-30).
    """
    parts = urlparse(url)

    if parts.scheme.startswith("sqlite"):
        # Convention SQLAlchemy, délibérément : `DATABASE_URL` est partagée avec
        # le pipeline, qui construit son moteur SQLAlchemy depuis la même valeur.
        # Une seule URL doit donc convenir aux deux ORM.
        #   sqlite:///:memory:        → en mémoire
        #   sqlite:///chemin/rel.db   → relatif
        #   sqlite:////chemin/abs.db  → absolu (quatre barres)
        reste = url.split("://", 1)[1] if "://" in url else ""
        chemin = reste[1:] if reste.startswith("/") else reste
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:" if chemin in {":memory:", ""} else chemin,
        }

    options = dict(parse_qsl(parts.query))
    # Neon impose TLS ; ne jamais laisser une connexion en clair par omission.
    options.setdefault("sslmode", "require")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/"),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "OPTIONS": options,
        # Équivalents Django de ce qui a été appris à la dure côté SQLAlchemy
        # (D-CEO-19) : Neon met la base en veille après inactivité, et les
        # connexions gardées ouvertes meurent sans prévenir, ce qui provoquait
        # des écritures silencieusement perdues.
        #   CONN_HEALTH_CHECKS  <-> pool_pre_ping
        #   CONN_MAX_AGE        <-> pool_recycle
        "CONN_MAX_AGE": 300,
        "CONN_HEALTH_CHECKS": True,
    }


DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {"default": _config_base(DATABASE_URL)}
else:
    # Sans DATABASE_URL, `makemigrations` et les tests hors base fonctionnent
    # quand même — seules les commandes qui touchent réellement la base
    # échoueront, avec un message clair.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.dummy",
        }
    }


# ── Authentification ──────────────────────────────────────────────────────────
# Le modèle utilisateur Django remplace la connexion nom + PIN en clair dans un
# Google Sheet (D-CEO-25). Migration traitée dans un chantier dédié : les rôles
# (enseignant / responsable / administrateur) deviendront des groupes Django.

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/connexion/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/connexion/"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 h — une journée de travail en centre
SESSION_EXPIRE_AT_BROWSER_CLOSE = True


# ── Localisation ──────────────────────────────────────────────────────────────

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"  # UTC+0 — les dates de transition doivent être
USE_I18N = True                   # justes localement : elles portent les indicateurs
USE_TZ = True                     # de rétention à 45 jours et 3 mois.


# ── Fichiers statiques ────────────────────────────────────────────────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [d for d in [BASE_DIR / "static"] if d.exists()]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # En développement, pas de manifeste : il exigerait un `collectstatic`
        # avant chaque lancement.
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



# ── Journalisation ────────────────────────────────────────────────────────────
# Le pipeline écrit déjà dans logs/ avec rotation quotidienne (D-CEO-19).
# Django journalise sur la sortie standard, que Railway/Render collectent.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name} — {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
