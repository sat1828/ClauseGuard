"""
Overall document score. Weighted average — critical clauses (score >= 9)
count double. Failed clauses are EXCLUDED, not scored as 0 — an analysis
failure is not evidence of safety.
"""


def compute_overall_score(clause_records: list[dict]) -> float | None:
    """
    clause_records: list of {"risk_score": int|None, "analysis_failed": bool}
    Returns None if there is nothing to score.
    """
    scored = [c for c in clause_records if not c.get("analysis_failed") and c.get("risk_score") is not None]
    if not scored:
        return None

    total_weight = 0.0
    total_weighted = 0.0
    for c in scored:
        score = c["risk_score"]
        weight = 2.0 if score >= 9 else 1.0
        total_weight += weight
        total_weighted += score * weight

    return round(total_weighted / total_weight, 2)


def score_to_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 3.5:
        return "low"
    if score < 6.0:
        return "medium"
    if score < 8.0:
        return "high"
    return "critical"


def risk_score_to_label(score: int) -> str:
    """Per-clause label from its 1-10 risk_score. Reuses the same thresholds
    as the overall document score so a clause labelled 'high' and a document
    labelled 'high' mean the same thing."""
    return score_to_label(float(score))
