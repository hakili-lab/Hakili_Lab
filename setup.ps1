# Hakili Lab — Script de setup PowerShell (Windows)
# Usage : .\setup.ps1

Write-Host "=== Hakili Lab — Installation ===" -ForegroundColor Cyan

# Creer l'environnement virtuel
python -m venv .venv
if (-not $?) { Write-Error "Echec creation venv"; exit 1 }

# Activer et installer
.\.venv\Scripts\pip.exe install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
if (-not $?) { Write-Error "Echec installation dependances"; exit 1 }

# Copier .env si absent
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Fichier .env cree. Ouvrez-le et renseignez vos cles API." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Installation terminee." -ForegroundColor Green
Write-Host "Pour lancer l'interface : .\.venv\Scripts\streamlit.exe run src\ui\app.py"
