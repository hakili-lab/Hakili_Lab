from src.models.domain import QuestionGrade, CopyGrade


def test_copy_grade_model():
    grade = CopyGrade(
        student_copy_id="anon_001",
        total_score=8,
        max_score=10,
        questions=[QuestionGrade(question_id="Q1", score=4, max_score=5, comment="Bien")],
    )
    assert grade.questions[0].question_id == "Q1"
