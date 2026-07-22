"""
Groq-backed clause analyzer.

Audit-driven design decisions baked in here:
- Raw LLM output NEVER reaches the caller unvalidated. It's parsed against a
  strict pydantic schema; anything that fails validation is treated as a
  failed analysis, not silently coerced into something plausible-looking.
- Self-reported confidence is blended with a cheap heuristic (clause length,
  hedging language) rather than trusted alone — see the audit note in the
  README about why raw self-reported LLM confidence is close to theater.
- No case law / statute citation permitted, enforced in the system prompt.
"""
import json
import logging
import re

from pydantic import BaseModel, ValidationError, field_validator
from groq import Groq, APIError, APIConnectionError, RateLimitError

from app.config import settings
from app.taxonomy import VALID_TYPES, VALID_FLAGS, taxonomy_prompt_block

logger = logging.getLogger("clauseguard.ai")

SYSTEM_PROMPT = f"""You are a contract risk analysis engine for ClauseGuard, a legal-tech tool for small businesses. Your job is to analyze a single contract clause and return a structured risk assessment.

CRITICAL RULES:
- You analyze only the provided clause text. Do not invent facts not present in the text.
- Do not cite case law, statutes, or regulations, by name or number.
- Do not give legal advice. Provide practical risk assessment only.
- Explanations must be in plain English, understandable by a non-lawyer business owner.
- You must report your confidence in the analysis honestly. If the clause text is ambiguous, truncated, or hard to interpret, report LOW confidence.
- Return ONLY a JSON object. No prose. No markdown fences. No preamble, no epilogue.

OUTPUT SCHEMA (return exactly these keys):
{{
  "clause_type": "<one taxonomy key from the list below>",
  "risk_score": <integer 1-10>,
  "risk_label": "<low|medium|high|critical>",
  "plain_english_explanation": "<2-4 sentences explaining what this clause means for the user and why it matters>",
  "suggested_safer_language": "<rewritten version of the clause that is more balanced, or null if the clause is already low risk>",
  "confidence_score": <float 0.0-1.0>,
  "flags": [<zero or more of: auto_renewal, ip_grab, uncapped_liability, price_escalation>]
}}

TAXONOMY (classify clause_type as exactly one of these keys):
{taxonomy_prompt_block()}

RISK SCORING GUIDE:
1-2: Standard, balanced clause. No unusual risk.
3-4: Slightly one-sided. Worth noting but not alarming.
5-6: Meaningfully unfavorable. Business owner should be aware.
7-8: High risk. Potentially costly or restrictive. Review before signing.
9-10: Critical. Could cause significant financial loss, loss of IP, or unlimited liability.
"""

_HEDGE_WORDS = re.compile(r"\b(may|might|unclear|ambiguous|possibly|arguably|could be interpreted)\b", re.IGNORECASE)


class ClauseAnalysisSchema(BaseModel):
    clause_type: str
    risk_score: int
    risk_label: str
    plain_english_explanation: str
    suggested_safer_language: str | None = None
    confidence_score: float
    flags: list[str] = []

    @field_validator("clause_type")
    @classmethod
    def valid_type(cls, v):
        if v not in VALID_TYPES:
            raise ValueError(f"clause_type '{v}' not in taxonomy")
        return v

    @field_validator("risk_score")
    @classmethod
    def valid_score(cls, v):
        if not (1 <= v <= 10):
            raise ValueError(f"risk_score {v} out of range 1-10")
        return v

    @field_validator("risk_label")
    @classmethod
    def valid_label(cls, v):
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError(f"invalid risk_label '{v}'")
        return v

    @field_validator("confidence_score")
    @classmethod
    def valid_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence_score {v} out of range 0-1")
        return v

    @field_validator("flags")
    @classmethod
    def valid_flags(cls, v):
        bad = [f for f in v if f not in VALID_FLAGS]
        if bad:
            raise ValueError(f"invalid flags: {bad}")
        return [f for f in v if f != "none"]


class AnalysisResult:
    def __init__(self, success: bool, data: dict | None = None, failure_reason: str | None = None):
        self.success = success
        self.data = data
        self.failure_reason = failure_reason


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _blend_confidence(model_confidence: float, clause_text: str, explanation: str) -> float:
    """
    Self-reported confidence alone is poorly calibrated (see README audit
    notes). Nudge it down when the clause text is very short/fragment-like
    or when the model's own explanation uses hedging language — both
    correlate with genuinely uncertain analysis.
    """
    penalty = 0.0
    word_count = len(clause_text.split())
    if word_count < 25:
        penalty += 0.15
    if _HEDGE_WORDS.search(explanation or ""):
        penalty += 0.10
    return max(0.0, round(model_confidence - penalty, 2))


class GroqClauseAnalyzer:
    def __init__(self):
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
                "and put it in your .env file."
            )
        if self._client is None:
            self._client = Groq(api_key=settings.GROQ_API_KEY, timeout=settings.GROQ_TIMEOUT_SECONDS)
        return self._client

    async def analyze_clause(self, clause_text: str) -> AnalysisResult:
        import asyncio

        last_error = None
        for attempt in range(1, settings.GROQ_MAX_RETRIES + 1):
            try:
                # Groq's SDK is sync; run it off the event loop thread so one
                # slow clause doesn't block the whole worker.
                raw_text = await asyncio.to_thread(self._call_groq, clause_text)
            except RateLimitError as e:
                last_error = f"rate_limited: {e}"
                await asyncio.sleep(min(2 ** attempt, 20))
                continue
            except (APIConnectionError, APIError) as e:
                last_error = f"api_error: {e}"
                await asyncio.sleep(min(2 ** attempt, 10))
                continue
            except Exception as e:
                last_error = f"unexpected_error: {e}"
                break

            cleaned = _strip_json_fences(raw_text)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                last_error = f"invalid_json: {e}. Raw (truncated): {raw_text[:300]!r}"
                logger.warning(f"Groq returned non-JSON on attempt {attempt}: {last_error}")
                continue

            try:
                validated = ClauseAnalysisSchema(**parsed)
            except ValidationError as e:
                last_error = f"schema_validation_failed: {e}"
                logger.warning(f"Groq JSON failed schema validation on attempt {attempt}: {last_error}")
                continue

            data = validated.model_dump()
            data["confidence_score"] = _blend_confidence(
                validated.confidence_score, clause_text, validated.plain_english_explanation
            )
            return AnalysisResult(success=True, data=data)

        logger.error(f"Clause analysis failed after {settings.GROQ_MAX_RETRIES} attempts: {last_error}")
        return AnalysisResult(success=False, failure_reason=last_error or "unknown_error")

    def _call_groq(self, clause_text: str) -> str:
        response = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=1000,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this contract clause:\n\n---\n{clause_text}\n---"},
            ],
        )
        return response.choices[0].message.content


analyzer = GroqClauseAnalyzer()
