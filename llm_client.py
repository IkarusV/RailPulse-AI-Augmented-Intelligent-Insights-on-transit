import json
import time

import requests

from config import API_KEY, API_STYLE, BASE_URL, MODEL, REQUEST_TIMEOUT_SECONDS
from prompts import ANSWER_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT


class LLMError(RuntimeError):
    """Raised when the model service cannot return a usable answer."""

    pass


class LLMRequestError(LLMError):
    """Raised after an HTTP request fails, with a safe status and message."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


# Step 1: read provider responses

def _responses_text(payload):
    """Extract assistant text from a Responses API payload."""

    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    raise LLMError("The model returned no text response")


def _request_json(path, body):
    """Send one authenticated JSON request to the configured model service."""

    if not API_KEY:
        raise LLMError("LLM_API_KEY is not configured")
    if not BASE_URL:
        raise LLMError("LLM_BASE_URL is not configured")
    if not MODEL:
        raise LLMError("LLM_MODEL is not configured")

    url = f"{BASE_URL}/{path}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "RailPulse-AI/1.0",
    }

    # Retry rate limits and temporary provider failures with a short backoff.
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            if attempt < 2:
                time.sleep(2**attempt)
                continue
            raise LLMRequestError(f"Model service could not be reached: {error}") from error

        if response.status_code < 400:
            try:
                return response.json()
            except requests.JSONDecodeError as error:
                raise LLMRequestError(
                    "Model service returned an invalid JSON response",
                    response.status_code,
                ) from error

        if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
            time.sleep(2**attempt)
            continue

        try:
            payload = response.json()
            detail = payload.get("error", payload)
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("detail") or str(detail)
        except requests.JSONDecodeError:
            detail = response.text.strip()
        detail = str(detail or "No provider error details")[:300]
        raise LLMRequestError(
            f"Model service returned HTTP {response.status_code}: {detail}",
            response.status_code,
        )

    raise LLMRequestError("Model request failed after retries")


# Step 2: support the two common OpenAI-compatible API styles

def _responses_request(instructions, user_input, schema, max_tokens):
    """Call a Responses endpoint and retry one incomplete generation."""

    body = {
        "model": MODEL,
        "instructions": instructions,
        "input": user_input,
        "max_output_tokens": max_tokens,
        "reasoning": {"effort": "low"},
        "store": False,
    }
    if schema:
        body["text"] = {
            "format": {
                "type": "json_schema",
                "name": "railpulse_sql_plan",
                "strict": True,
                "schema": schema,
            }
        }

    payload = _request_json("responses", body)
    if payload.get("status") == "incomplete":
        # Structured SQL is short, but reasoning models can consume the first
        # allowance internally. Retry once rather than exposing a transient failure.
        body["max_output_tokens"] = max(max_tokens * 2, 1_600)
        payload = _request_json("responses", body)
    if payload.get("status") != "completed":
        details = payload.get("incomplete_details") or payload.get("error") or {}
        reason = details.get("reason", "unknown reason") if isinstance(details, dict) else details
        raise LLMError(
            f"Model response did not complete: {payload.get('status')} ({reason})"
        )
    return _responses_text(payload)


def _chat_completions_request(instructions, user_input, schema, max_tokens):
    """Call a Chat Completions endpoint with the same prompt contract."""

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": max_tokens,
    }
    if schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "railpulse_sql_plan",
                "strict": True,
                "schema": schema,
            },
        }

    payload = _request_json("chat/completions", body)
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("The model returned no chat-completion text") from error


def _create_response(instructions, user_input, *, schema=None, max_tokens=700):
    """Route a generation request through the configured API style."""

    if API_STYLE == "responses":
        try:
            return _responses_request(instructions, user_input, schema, max_tokens)
        except LLMRequestError as error:
            # Some compatible providers route Responses and Chat Completions
            # differently. A second protocol keeps transient route failures invisible.
            if error.status_code in {429, 500, 502, 503, 504}:
                return _chat_completions_request(
                    instructions,
                    user_input,
                    schema,
                    max(max_tokens, 1_200),
                )
            raise
    if API_STYLE == "chat_completions":
        return _chat_completions_request(instructions, user_input, schema, max_tokens)
    raise LLMError(
        "LLM_API_STYLE must be 'responses' or 'chat_completions'"
    )


# Step 3: generate and parse a strict SQL plan

def generate_sql(question):
    """Turn one user question into a structured SQL proposal.

    Input:
        question: natural-language question about the departure snapshot.
    Returns:
        Dict with can_answer, title, sql and reason fields.
    """

    schema = {
        "type": "object",
        "properties": {
            "can_answer": {"type": "boolean"},
            "title": {"type": "string"},
            "sql": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["can_answer", "title", "sql", "reason"],
        "additionalProperties": False,
    }
    raw = _create_response(SQL_SYSTEM_PROMPT, question, schema=schema, max_tokens=800)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise LLMError("The model returned invalid structured SQL output") from error


# Step 4: summarize only validated database evidence

def summarize_result(question, sql, columns, rows):
    """Write a short operational answer from validated query results.

    Input:
        question: original user question.
        sql: query accepted by the safety layer.
        columns: result column names.
        rows: values returned by SQLite.
    Returns:
        Grounded natural-language answer.
    """

    result = {
        "question": question,
        "validated_sql": sql,
        "columns": columns,
        "rows": rows,
    }
    return _create_response(
        ANSWER_SYSTEM_PROMPT,
        json.dumps(result, ensure_ascii=False, default=str),
        max_tokens=500,
    )
