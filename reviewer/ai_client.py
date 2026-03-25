"""
ai_client.py

Handles communication with the OpenRouter API to grade student submissions.

Grade mapping used throughout this project:
  Numeric (German) | Letter (A–F) | Percentage range
  1.0              | A            | 90–100 %
  1.3              | A            | 80–90 %
  1.7              | B            | 80–90 %
  2.0              | B            | 70–80 %
  2.3              | B            | 70–80 %
  2.7              | C            | 60–70 %
  3.0              | C            | 60–70 %
  3.3              | C            | 50–60 %
  3.7              | D            | 50–60 %
  4.0              | D            | 40–50 %
  4.3              | E            | 30–40 %
  4.7              | E            | 20–30 %
  5.0              | F            |  0–10 %
"""

import json
import os
import requests

# ---------------------------------------------------------------------------
# Grade table — single source of truth
# ---------------------------------------------------------------------------

GRADE_TABLE = {
    "1.0": {"letter": "A", "percentage": "90–100 %"},
    "1.3": {"letter": "A", "percentage": "80–90 %"},
    "1.7": {"letter": "B", "percentage": "80–90 %"},
    "2.0": {"letter": "B", "percentage": "70–80 %"},
    "2.3": {"letter": "B", "percentage": "70–80 %"},
    "2.7": {"letter": "C", "percentage": "60–70 %"},
    "3.0": {"letter": "C", "percentage": "60–70 %"},
    "3.3": {"letter": "C", "percentage": "50–60 %"},
    "3.7": {"letter": "D", "percentage": "50–60 %"},
    "4.0": {"letter": "D", "percentage": "40–50 %"},
    "4.3": {"letter": "E", "percentage": "30–40 %"},
    "4.7": {"letter": "E", "percentage": "20–30 %"},
    "5.0": {"letter": "F", "percentage": "0–10 %"},
}

VALID_NUMERIC_GRADES = list(GRADE_TABLE.keys())  # e.g. ["1.0", "1.3", …, "5.0"]

# ---------------------------------------------------------------------------
# Models available for selection in the UI
# ---------------------------------------------------------------------------

AVAILABLE_MODELS = [
    ("google/gemini-2.0-flash-001",       "Google Gemini 2.0 Flash"),
    ("anthropic/claude-3.5-sonnet",       "Anthropic Claude 3.5 Sonnet"),
    ("openai/gpt-4o",                     "OpenAI GPT-4o"),
    ("openai/gpt-4o-mini",                "OpenAI GPT-4o Mini"),
    ("meta-llama/llama-3.3-70b-instruct", "Meta Llama 3.3 70B Instruct"),
    ("deepseek/deepseek-chat",            "DeepSeek Chat"),
    ("mistralai/mistral-large",           "Mistral Large"),
]

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Maximum number of characters sent to the AI (≈ ~10 000 tokens).
# Very long documents are truncated to keep API costs reasonable.
MAX_DOCUMENT_CHARS = 40_000


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def grade_document(document_text: str, assignment_description: str, model: str) -> dict:
    """
    Send the student's document text together with the assignment description
    to the chosen LLM via OpenRouter and return a structured grading result.

    Returns a dict with:
        numeric_grade  – e.g. "2.3"
        letter_grade   – e.g. "B"
        percentage     – e.g. "70–80 %"
        explanation    – the AI's reasoning (2–4 sentences)
        model_used     – the model ID that was called

    Raises RuntimeError on API errors or when the AI response cannot be parsed.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY ist nicht gesetzt. "
            "Bitte die .env-Datei mit dem API-Schlüssel befüllen."
        )

    # Truncate very long documents to avoid excessive token usage
    if len(document_text) > MAX_DOCUMENT_CHARS:
        document_text = (
            document_text[:MAX_DOCUMENT_CHARS]
            + f"\n\n[… Dokument wurde auf {MAX_DOCUMENT_CHARS} Zeichen gekürzt …]"
        )

    system_prompt = (
        "You are an academic grader assisting university lecturers. "
        "Evaluate the student submission below against the given assignment description. "
        "Use the German university grading scale (1.0 = best, 5.0 = fail).\n\n"
        "You MUST respond with a valid JSON object and NOTHING else. "
        "The JSON must have exactly these two keys:\n"
        '  "numeric_grade": one of 1.0, 1.3, 1.7, 2.0, 2.3, 2.7, 3.0, 3.3, 3.7, 4.0, 4.3, 4.7, 5.0\n'
        '  "explanation": 2–4 sentences explaining the grade\n\n'
        "Base the grade solely on how well the submission fulfils the assignment. "
        "If the document is empty or entirely off-topic, assign 5.0. "
        "Write the explanation in the same language as the submission."
    )

    user_prompt = (
        f"## Assignment description\n{assignment_description}\n\n"
        f"## Student submission\n{document_text}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        # Ask for JSON output where supported
        "response_format": {"type": "json_object"},
        # Low temperature → more deterministic, consistent grading
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter requires an HTTP-Referer header
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Virtual Reviewer",
    }

    try:
        response = requests.post(
            OPENROUTER_API_URL, json=payload, headers=headers, timeout=120
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Netzwerkfehler beim API-Aufruf: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter API antwortete mit Status {response.status_code}: "
            f"{response.text[:500]}"
        )

    # Parse the model's reply
    try:
        raw_content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(raw_content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"API-Antwort konnte nicht verarbeitet werden: {exc}\n"
            f"Rohantwort: {response.text[:500]}"
        ) from exc

    numeric = str(data.get("numeric_grade", "")).strip()
    # Normalise e.g. "2" → "2.0" in case the model omits the decimal
    if "." not in numeric:
        numeric = numeric + ".0"

    if numeric not in GRADE_TABLE:
        raise RuntimeError(
            f"Das KI-Modell hat eine ungueltige Note zurueckgegeben: '{numeric}'. "
            f"Erlaubte Werte: {', '.join(VALID_NUMERIC_GRADES)}"
        )

    return {
        "numeric_grade": numeric,
        "letter_grade":  GRADE_TABLE[numeric]["letter"],
        "percentage":    GRADE_TABLE[numeric]["percentage"],
        "explanation":   str(data.get("explanation", "Keine Begründung angegeben.")),
        "model_used":    model,
    }
