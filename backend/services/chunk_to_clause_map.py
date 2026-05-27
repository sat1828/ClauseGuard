"""Utility to build a clause_type → original_text map for alternative generation."""
from schemas.analysis import ClauseExtractionResult


def build_clause_text_map(
    extracted_clauses: list[ClauseExtractionResult],
) -> dict[str, str]:
    """
    Build a mapping from clause_type to the highest-confidence relevant_text.
    Used by alternative_generator to access the original clause text.
    When multiple extractions exist for the same type, keep highest confidence.
    """
    clause_map: dict[str, ClauseExtractionResult] = {}
    for clause in extracted_clauses:
        existing = clause_map.get(clause.clause_type)
        if existing is None or clause.confidence > existing.confidence:
            clause_map[clause.clause_type] = clause
    return {ct: c.relevant_text for ct, c in clause_map.items()}
