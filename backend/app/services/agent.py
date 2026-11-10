from __future__ import annotations

import json

import anthropic
from anthropic import beta_tool
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import settings
from app.services.schema_context import describe_datasets
from app.services.sql_runner import UnsafeQueryError, run_readonly_query

ROWS_SHOWN_TO_MODEL = 50
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """You are a data analyst. You answer questions about the user's uploaded \
datasets by querying a PostgreSQL database with the run_sql tool.

How to work:
- Write PostgreSQL. Always schema-qualify and double-quote table names exactly as listed, \
e.g. SELECT ... FROM user_data."sales_2024".
- Use only the tables and columns listed below. If the data can't answer the question, say so.
- Run as many queries as you need. If one fails, read the error and fix it.
- Aggregate in SQL rather than pulling raw rows. Add a LIMIT when listing rows.
- The user sees one query's result as a chart or table: the last query you ran with \
show_to_user=true. Use it for the query whose rows best support your answer (readable \
column aliases, one row per category or time period). Set show_to_user=false for \
exploratory or side checks, such as counting nulls or peeking at values.
- Order the shown query's columns as: the label (category or period) first, then the \
main measure the question is about, then supporting measures, with counts last.
- For results over time, return one row per period with an ISO date or YYYY-MM label \
first, sorted ascending, and include empty periods as 0 (e.g. with generate_series) \
so gaps aren't hidden.

Final answer: a short, direct answer in plain language (a few sentences at most), with the \
key numbers. Don't paste the SQL or the full table; the user sees those separately.

Available datasets:
"""


class AgentNotConfiguredError(Exception):
    pass


class AgentError(Exception):
    pass


def _client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise AgentNotConfiguredError(
            "ANTHROPIC_API_KEY is not set. Add it to the .env file in the project root "
            "and restart the server."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def ask(question: str, session: Session, dataset_ids: list[int] | None = None) -> dict:
    schema = describe_datasets(session, dataset_ids)
    if not schema:
        raise AgentError("No datasets found. Upload a CSV first.")

    queries: list[dict] = []

    @beta_tool
    def run_sql(sql: str, show_to_user: bool = True) -> str:
        """Run one read-only PostgreSQL SELECT query against the user's datasets and
        return the result rows as JSON (or an error message to fix and retry).

        Args:
            sql: A single SELECT (or WITH ... SELECT) statement.
            show_to_user: True if this result should be the chart/table shown with your
                answer; false for exploratory or side-check queries.
        """
        try:
            result = run_readonly_query(sql)
        except (UnsafeQueryError, DBAPIError) as e:
            message = str(getattr(e, "orig", None) or e).strip()
            queries.append({"sql": sql, "error": message, "shown": False})
            return f"ERROR: {message}"

        queries.append({**result, "error": None, "shown": show_to_user})
        preview = {
            "columns": result["columns"],
            "rows": result["rows"][:ROWS_SHOWN_TO_MODEL],
            "total_rows_returned": len(result["rows"]),
            "truncated": result["truncated"],
        }
        return json.dumps(preview, default=str)

    runner = _client().beta.messages.tool_runner(
        model=settings.agent_model,
        max_tokens=16000,
        max_iterations=MAX_TOOL_ROUNDS,
        system=SYSTEM_PROMPT + schema,
        tools=[run_sql],
        output_config={"effort": "medium"},
        # If a safety classifier declines, retry on a fallback model in the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": question}],
    )
    final = runner.until_done()

    if final.stop_reason == "refusal":
        raise AgentError("The model declined to answer this question.")

    answer = "".join(b.text for b in final.content if b.type == "text").strip()
    if not answer:
        answer = "I couldn't finish the analysis within the allowed number of steps."

    successful = [q for q in queries if q["error"] is None]
    shown = [q for q in successful if q["shown"]] or successful
    return {
        "question": question,
        "answer": answer,
        "result": shown[-1] if shown else None,
        "queries": queries,
        "model": final.model,
    }
