"""
Turns the `flags` list each clause's AI analysis returns into document-level
DocumentFlag records with human-readable summaries and severity.
"""

FLAG_META = {
    "auto_renewal": {
        "severity": "critical",
        "title": "Auto-Renewal Trap Detected",
        "summary": "This contract renews automatically unless you cancel within a specific window — missing it can lock you in for another full term.",
    },
    "ip_grab": {
        "severity": "critical",
        "title": "IP Ownership Risk Detected",
        "summary": "A clause transfers or claims ownership of intellectual property in a way that may not favor you — review who actually owns the work.",
    },
    "uncapped_liability": {
        "severity": "critical",
        "title": "Uncapped Liability Detected",
        "summary": "At least one clause exposes a party to liability with no dollar cap — a single incident could create unlimited financial exposure.",
    },
    "price_escalation": {
        "severity": "warning",
        "title": "Automatic Price Increase Detected",
        "summary": "Pricing can increase automatically on renewal or over time — check the mechanism and whether there's a cap.",
    },
}


def build_document_flags(clause_records: list[dict]) -> list[dict]:
    """
    clause_records: list of dicts with keys: id (clause_id), flags (list[str])
    Returns: list of dicts ready to become DocumentFlag rows.
    De-duplicates by flag_type — first occurrence wins for affected_clause_id,
    but the summary always reflects the flag type, not the specific clause.
    """
    seen_types = set()
    results = []
    for clause in clause_records:
        for flag_type in clause.get("flags") or []:
            if flag_type in seen_types or flag_type not in FLAG_META:
                continue
            seen_types.add(flag_type)
            meta = FLAG_META[flag_type]
            results.append({
                "flag_type": flag_type,
                "severity": meta["severity"],
                "summary": f"{meta['title']}: {meta['summary']}",
                "affected_clause_id": clause["id"],
            })
    return results
