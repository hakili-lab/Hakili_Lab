"""Script de test ponctuel : relance le diagnostic sur test_n3_3e avec le nouveau prompt."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.domain import CopyGrade
from src.api.claude_client import ClaudeClient
from src.knowledge.curriculum_retriever import CurriculumRetriever

RESULT_FILE = Path("runs/test_n3_3e/result.json")

def main():
    data = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    grade = CopyGrade(**data["grade"])

    print(f"Copie : {grade.copy_id}")
    print(f"Score final : {grade.final_score}/{grade.total_possible}  ({grade.final_score_on_20}/20)")
    questions_echouees = [q for q in grade.questions if (q.teacher_score if q.teacher_score is not None and q.teacher_decision.value == 'refused' else q.score) == 0]
    questions_reussies = [q for q in grade.questions if q not in questions_echouees]
    print(f"Questions réussies : {len(questions_reussies)} | Échouées : {len(questions_echouees)}")
    print()

    # Charge le contexte curriculum pour le test 3e v1
    retriever = CurriculumRetriever()
    failed_ids = [q.rubric_item_id for q in questions_echouees]
    curriculum_context = retriever.get_diagnostic_context(failed_ids, "hakili_3e_v1") or ""
    if curriculum_context:
        print(f"Contexte curriculum chargé : {len(curriculum_context)} caractères")
    else:
        print("Aucun contexte curriculum disponible")
    print()

    print("=" * 60)
    print("LANCEMENT DU DIAGNOSTIC (nouveau prompt)...")
    print("=" * 60)

    client = ClaudeClient()
    response = client.diagnose(grade, curriculum_context)

    if not response.success:
        print(f"ÉCHEC : {response.error}")
        return

    d = response.data
    print(f"\n=== PROFIL ACADÉMIQUE ===")
    print(d.academic_profile or "(vide)")

    print(f"\n=== POINTS FORTS ({len(d.strengths)}) ===")
    for s in d.strengths:
        print(f"  • {s}")

    print(f"\n=== FAIBLESSES ({len(d.weaknesses)}) ===")
    for w in d.weaknesses:
        print(f"  • {w}")

    print(f"\n=== CAUSES RACINES ({len(d.root_causes)}) ===")
    for rc in d.root_causes:
        print(f"\n  [{rc.nature}]")
        print(f"  Erreur visible  : {rc.visible_error}")
        print(f"  Cause cachée    : {rc.hidden_cause}")
        print(f"  Trigger didact. : {rc.pedagogical_trigger}")
        print(f"  Questions liées : {rc.linked_questions}")

    print(f"\n=== COMPÉTENCES ({len(d.skills)}) ===")
    for sk in d.skills:
        note = f" | Note: {sk.note}" if sk.note else ""
        print(f"  [{sk.level}] {sk.name}{note}")
        print(f"           {sk.evidence}")

    print(f"\n=== PLAN DE REMÉDIATION ({len(d.remediation_plan)}) ===")
    for item in d.remediation_plan:
        print(f"\n  Priorité {item.priority} — {item.topic}")
        print(f"  Action   : {item.action}")
        print(f"  Trigger  : {item.pedagogical_trigger}")

    print("\n" + "=" * 60)
    print("JSON COMPLET :")
    print(d.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
