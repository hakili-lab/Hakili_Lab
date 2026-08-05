# Hakili Lab — Makefile cross-platform (Windows + Unix)
# Windows : installer make via `winget install GnuWin32.Make` ou utiliser setup.ps1

.PHONY: setup run verifier importer test test-django lint collectstatic clean

ifeq ($(OS),Windows_NT)
    PYTHON     = .venv\Scripts\python.exe
    PIP        = .venv\Scripts\pip.exe
else
    PYTHON     = .venv/bin/python
    PIP        = .venv/bin/pip
endif

setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "Environnement pret. Copiez .env.example en .env et renseignez vos cles."

# Interface web Django — la seule depuis le retrait de Streamlit (D-CEO-39).
run:
	$(PYTHON) manage.py runserver

# Controle avant mise en service : configuration, base, Sheets, cles, referentiel.
# Ajouter un essai de correction reel :
#   make verifier ARGS="--copie copie.pdf --test urie_3eme --eleve HAK-..."
verifier:
	$(PYTHON) manage.py verifier_installation $(ARGS)

importer:
	$(PYTHON) manage.py importer_referentiel

test:
	$(PYTHON) -m pytest tests/ -v --tb=short
	$(PYTHON) manage.py test

test-django:
	$(PYTHON) manage.py test

lint:
	$(PYTHON) -m ruff check src/ tests/ hakili/ comptes/ suivi_web/ correction_web/ referentiel/ suivi/
	$(PYTHON) -m mypy src/ --ignore-missing-imports

collectstatic:
	$(PYTHON) manage.py collectstatic --noinput

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cache Python nettoye."
