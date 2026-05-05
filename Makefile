# Hakili Lab — Makefile cross-platform (Windows + Unix)
# Windows : installer make via `winget install GnuWin32.Make` ou utiliser setup.ps1

.PHONY: setup test run lint clean

ifeq ($(OS),Windows_NT)
    PYTHON     = .venv\Scripts\python.exe
    PIP        = .venv\Scripts\pip.exe
    ACTIVATE   = .venv\Scripts\activate.bat
    SEP        = \\
else
    PYTHON     = .venv/bin/python
    PIP        = .venv/bin/pip
    ACTIVATE   = .venv/bin/activate
    SEP        = /
endif

setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "Environnement pret. Copiez .env.example en .env et renseignez vos cles API."

run:
	$(PYTHON) -m streamlit run src/ui/app.py

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/ --ignore-missing-imports

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cache Python nettoye."
