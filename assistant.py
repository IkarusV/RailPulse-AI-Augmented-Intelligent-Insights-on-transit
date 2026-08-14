from database import execute_readonly
from llm_client import generate_sql, summarize_result
from sql_guard import validate_sql


class QuestionNotAnswerable(ValueError):
    """Raised when the departure snapshot cannot answer a question."""

    pass


# Step 1: plan, validate and run one question

def answer_question(question):
    """Run the complete question-to-answer pipeline.

    Input:
        question: natural-language question from the Streamlit interface.
    Returns:
        Answer text, validated SQL and the supporting result table.
    """

    clean_question = question.strip()
    if not clean_question:
        raise QuestionNotAnswerable("Enter a question about the departure snapshot")
    if len(clean_question) > 1_000:
        raise QuestionNotAnswerable("Keep the question under 1,000 characters")

    # The model proposes SQL but never receives a database connection.
    plan = generate_sql(clean_question)
    if not plan["can_answer"]:
        raise QuestionNotAnswerable(plan["reason"])

    # Application checks run before SQLite sees the query.
    validated_sql = validate_sql(plan["sql"])
    columns, rows = execute_readonly(validated_sql)

    # A second model call summarizes only the returned evidence.
    answer = summarize_result(clean_question, validated_sql, columns, rows)
    return {
        "title": plan["title"],
        "answer": answer,
        "sql": validated_sql,
        "columns": columns,
        "rows": rows,
    }
