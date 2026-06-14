"""
PipelineProgressUI — Affichage temps réel des étapes du pipeline Hakili.

Utilisation dans app.py :
    progress_ui = PipelineProgressUI(logo_b64=..., test_label=...)
    result = run_single_copy(..., on_progress=progress_ui.update)
    progress_ui.finish()
"""
from __future__ import annotations

import streamlit as st

# ── Définition des étapes ────────────────────────────────────────────────────

STEPS: list[tuple[str, str, int]] = [
    # (key, label affiché, % à l'entrée de l'étape)
    ("ingestion",      "Chargement des fichiers ..",       8),
    ("transcription",  "Lecture de la copie ..",    28),
    ("correction",     "Correction intelligente ..", 55),
    ("rag",            "Récupération du contexte programme ..",        68),
    ("diagnostic",     "Diagnostic pédagogique approfondi ..",         80),
    ("remediation",    "Plan de remédiation ..",          90),
    ("export",         "Finalisation ..",                  98),
]

_STEP_INDEX: dict[str, int] = {key: i for i, (key, _, _) in enumerate(STEPS)}

# ── Helpers HTML ─────────────────────────────────────────────────────────────

_STEP_ICON_PENDING  = '<span style="color:#9bb8d4;font-size:15px;">○</span>'
_STEP_ICON_ACTIVE   = '<span style="color:#4a90e2;font-size:15px;" class="hk-spin">◌</span>'
_STEP_ICON_DONE     = '<span style="color:#27ae60;font-size:15px;">●</span>'


def _step_html(key: str, label: str, state: str) -> str:
    """state: 'pending' | 'active' | 'done'"""
    icon = {"pending": _STEP_ICON_PENDING, "active": _STEP_ICON_ACTIVE, "done": _STEP_ICON_DONE}[state]
    text_color = {
        "pending": "#7a98b8",
        "active":  "#001e4a",
        "done":    "#2a7a4a",
    }[state]
    weight = "600" if state == "active" else "400"
    bar = (
        '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
        f'background:#4a90e2;margin-left:8px;animation:hk-blink 0.9s ease-in-out infinite;"></span>'
        if state == "active" else ""
    )
    return (
        f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;'
        f'border-bottom:1px solid #f0f4fa;">'
        f'{icon}'
        f'<span style="font-size:13px;font-weight:{weight};color:{text_color};flex:1;">{label}</span>'
        f'{bar}'
        f'</div>\n'
    )


def _progress_bar_html(pct: int) -> str:
    pct = max(0, min(100, pct))
    label_color = "#ffffff" if pct > 12 else "#001e4a"
    return f"""
<div style="background:#dde8f5;border-radius:20px;height:22px;overflow:hidden;margin:18px 0 6px 0;
            box-shadow:inset 0 1px 3px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(90deg,#1a4a8a 0%,#4a90e2 60%,#74b3f5 100%);
              height:100%;width:{pct}%;border-radius:20px;
              transition:width 0.6s cubic-bezier(.4,0,.2,1);
              display:flex;align-items:center;justify-content:flex-end;padding-right:10px;">
    <span style="font-size:11px;font-weight:700;color:{label_color};letter-spacing:0.5px;">{pct}%</span>
  </div>
</div>
<div style="text-align:right;font-size:10.5px;color:#7090b8;font-weight:500;letter-spacing:0.3px;">
  {pct}% complété
</div>
"""


_CSS = """
<style>
@keyframes hk-pulse {
  0%,100% { opacity:1; transform:scale(1); filter:drop-shadow(0 0 6px #4a90e220); }
  50%       { opacity:.85; transform:scale(1.03); filter:drop-shadow(0 0 18px #4a90e260); }
}
@keyframes hk-blink {
  0%,100% { opacity:1; } 50% { opacity:.3; }
}
@keyframes hk-fadein {
  from { opacity:0; transform:scale(0.97); } to { opacity:1; transform:scale(1); }
}
@keyframes hk-overlay-in {
  from { opacity:0; } to { opacity:1; }
}
@keyframes hk-spin {
  from { transform:rotate(0deg); } to { transform:rotate(360deg); }
}
@keyframes hk-spin-done {
  from { transform:rotate(0deg); } to { transform:rotate(360deg); }
}

/* Overlay plein écran — fond grisé avec flou */
.hk-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  background: rgba(0, 20, 55, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: hk-overlay-in 0.3s ease;
}

/* Carte modale centrée */
.hk-card {
  position: relative;
  background: #ffffff;
  border: 1.5px solid #dde8f5;
  border-radius: 16px;
  padding: 32px 36px;
  width: 520px;
  max-width: 92vw;
  box-shadow: 0 24px 64px rgba(0, 20, 74, 0.22), 0 4px 16px rgba(0,0,0,0.08);
  animation: hk-fadein 0.35s cubic-bezier(.2,.8,.3,1);
}
.hk-close {
  position: absolute;
  top: 14px; right: 16px;
  width: 28px; height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: #a0b8d4;
  transition: background 0.15s, color 0.15s;
  line-height: 1;
  padding: 0;
  text-decoration: none;
}
.hk-close:hover {
  background: #f0f4fa;
  color: #c0392b;
}
.hk-logo-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}
.hk-logo-ring {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
}
.hk-logo-ring img {
  width: 72px;
  height: 72px;
  object-fit: contain;
  animation: hk-pulse 2s ease-in-out infinite;
  position: relative;
  z-index: 1;
}
.hk-logo-ring svg {
  position: absolute;
  top: 0; left: 0;
  width: 88px; height: 88px;
  animation: hk-spin 1.6s linear infinite;
}
.hk-logo-ring-done svg {
  animation: none;
}
.hk-logo-ring-done .hk-ring-arc {
  stroke: #27ae60;
  stroke-dasharray: none;
}
.hk-ring-arc {
  fill: none;
  stroke: #4a90e2;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-dasharray: 48 208;
}
.hk-title {
  text-align: center;
  font-size: 19px;
  font-weight: 700;
  color: #001e4a;
  letter-spacing: 0.3px;
  margin-bottom: 4px;
}
.hk-subtitle {
  text-align: center;
  font-size: 12px;
  color: #7090b8;
  margin-bottom: 24px;
  font-weight: 400;
}
.hk-spin {
  display: inline-block;
  animation: hk-blink 0.7s ease-in-out infinite;
}
</style>
"""


class PipelineProgressUI:
    """
    Gère l'affichage temps réel du pipeline dans l'interface Streamlit.

    Passe `self.update` comme callback à `run_single_copy(on_progress=...)`.
    Appelle `self.finish()` une fois le pipeline terminé.
    """

    def __init__(self, logo_b64: str = "", test_label: str = "", student_name: str = "") -> None:
        self._logo_b64 = logo_b64
        self._test_label = test_label or "Correction IA"
        self._student_name = student_name
        self._current_step: str | None = None
        self._done_steps: set[str] = set()
        self._pct: int = 0
        self._placeholder = st.empty()
        self._render()

    def update(self, step_key: str, pct: int | None = None) -> None:
        """Appelé par le pipeline à chaque étape — step_key = clé STEPS."""
        if self._current_step and self._current_step != step_key:
            self._done_steps.add(self._current_step)
        self._current_step = step_key
        if pct is not None:
            self._pct = pct
        else:
            # Prendre le % de l'étape dans STEPS
            idx = _STEP_INDEX.get(step_key, 0)
            self._pct = STEPS[idx][2]
        self._render()

    def finish(self) -> None:
        """Marque toutes les étapes comme terminées et affiche 100%."""
        if self._current_step:
            self._done_steps.add(self._current_step)
        self._current_step = None
        self._pct = 100
        self._render(done=True)

    def clear(self) -> None:
        self._placeholder.empty()

    # ── Rendu interne ─────────────────────────────────────────────────────────

    def _render(self, done: bool = False) -> None:
        logo_html = ""
        if self._logo_b64:
            ring_class = "hk-logo-ring-done" if done else "hk-logo-ring"
            # SVG spinner : cercle de rayon 42, circonférence ≈ 264 → dasharray 66/198 = arc 25%
            arc_color = "#27ae60" if done else "#4a90e2"
            spin_style = "" if done else ""
            logo_html = (
                f'<div class="hk-logo-wrap">'
                f'<div class="{ring_class}">'
                f'<svg viewBox="0 0 88 88" xmlns="http://www.w3.org/2000/svg"'
                f' style="animation:{"none" if done else "hk-spin 1.6s linear infinite"};">'
                f'<circle class="hk-ring-arc" cx="44" cy="44" r="41"'
                f' stroke="{arc_color}"'
                f' stroke-dasharray="{"258 0" if done else "66 198"}"'
                f' stroke-width="3" fill="none" stroke-linecap="round"'
                f' transform="rotate(-90 44 44)"/>'
                f'</svg>'
                f'<img src="data:image/png;base64,{self._logo_b64}" />'
                f'</div>'
                f'</div>'
            )

        if done:
            title = "Analyse terminée"
            subtitle = "Tous les résultats sont disponibles ci-dessous."
        else:
            student_part = f" · {self._student_name}" if self._student_name else ""
            title = "Analyse en cours…"
            subtitle = f"{self._test_label}{student_part}"

        steps_html = ""
        for key, label, _ in STEPS:
            if key in self._done_steps:
                state = "done"
            elif key == self._current_step:
                state = "active"
            else:
                state = "pending"
            steps_html += _step_html(key, label, state)

        progress_html = _progress_bar_html(self._pct)

        if done:
            finish_banner = (
                '<div style="background:#e8f8ee;border:1px solid #a8ddb8;border-radius:6px;'
                'padding:10px 16px;margin-top:16px;text-align:center;font-size:13px;'
                'font-weight:600;color:#1a6b3a;">'
                '✓ &nbsp; Analyse complète — rapport disponible</div>'
            )
        else:
            finish_banner = (
                '<div style="text-align:center;margin-top:14px;font-size:11.5px;color:#9bb8d4;">'
                'Veuillez patienter — ne fermez pas cette fenêtre</div>'
            )

        close_btn = (
            "" if done else
            '<a class="hk-close" href="javascript:window.location.reload()" '
            'title="Annuler l\'analyse">&#x2715;</a>\n'
        )
        html = (
            f"{_CSS}\n"
            f'<div class="hk-overlay">\n'
            f'<div class="hk-card">\n'
            f"{close_btn}"
            f"{logo_html}\n"
            f'<div class="hk-title">{title}</div>\n'
            f'<div class="hk-subtitle">{subtitle}</div>\n'
            f"{progress_html}\n"
            f'<div style="margin-top:18px;">\n{steps_html}\n</div>\n'
            f"{finish_banner}\n"
            f"</div>\n"
            f"</div>\n"
        )
        self._placeholder.markdown(html, unsafe_allow_html=True)
