"""
Clause taxonomy. This is the ONLY place clause types are defined.
The AI prompt, the validator, and the frontend labels all derive from this
so they can never drift out of sync with each other.
"""

TAXONOMY: dict[str, dict] = {
    "auto_renewal": {"label": "Auto-Renewal", "default_risk": "high"},
    "liability_cap": {"label": "Liability Cap", "default_risk": "medium"},
    "uncapped_liability": {"label": "Uncapped Liability", "default_risk": "critical"},
    "indemnification": {"label": "Indemnification", "default_risk": "high"},
    "ip_ownership": {"label": "IP Ownership", "default_risk": "high"},
    "ip_license": {"label": "IP License", "default_risk": "medium"},
    "termination_for_convenience": {"label": "Termination for Convenience", "default_risk": "medium"},
    "termination_for_cause": {"label": "Termination for Cause", "default_risk": "medium"},
    "governing_law": {"label": "Governing Law", "default_risk": "low"},
    "dispute_resolution": {"label": "Dispute Resolution", "default_risk": "medium"},
    "confidentiality": {"label": "Confidentiality", "default_risk": "low"},
    "non_compete": {"label": "Non-Compete", "default_risk": "high"},
    "non_solicitation": {"label": "Non-Solicitation", "default_risk": "medium"},
    "payment_terms": {"label": "Payment Terms", "default_risk": "low"},
    "price_escalation": {"label": "Price Escalation", "default_risk": "high"},
    "data_privacy": {"label": "Data Privacy", "default_risk": "medium"},
    "force_majeure": {"label": "Force Majeure", "default_risk": "low"},
    "warranty": {"label": "Warranty", "default_risk": "medium"},
    "warranty_disclaimer": {"label": "Warranty Disclaimer", "default_risk": "medium"},
    "assignment": {"label": "Assignment", "default_risk": "medium"},
    "entire_agreement": {"label": "Entire Agreement", "default_risk": "low"},
    "amendment": {"label": "Amendment", "default_risk": "low"},
    "notice": {"label": "Notice", "default_risk": "low"},
    "other": {"label": "Other", "default_risk": "low"},
}

VALID_TYPES = set(TAXONOMY.keys())
VALID_FLAGS = {"auto_renewal", "ip_grab", "uncapped_liability", "price_escalation", "none"}


def taxonomy_prompt_block() -> str:
    lines = [f"- {key}: {v['label']}" for key, v in TAXONOMY.items()]
    return "\n".join(lines)


def human_label(clause_type: str | None) -> str:
    if not clause_type or clause_type not in TAXONOMY:
        return "Uncategorized"
    return TAXONOMY[clause_type]["label"]
