"""
Contract Type Classification Prompt
=====================================
Stage 0 of the ClauseGuard pipeline.

Design principles:
- Zero-shot prompt with rich type descriptions (no few-shot needed for type detection)
- Explicit JSON schema requirement — Claude must not output prose
- Confidence < 0.7 → UNKNOWN (handled by classifier.py, not the prompt)
- Chain-of-thought before JSON to improve accuracy
"""

CONTRACT_TYPE_SYSTEM = """You are a legal document classifier specializing in commercial contracts.
Your job is to identify the category of a legal document from its text.

You must respond with valid JSON only. No preamble, no explanation, no markdown.
The JSON must conform exactly to this schema:
{
  "contract_type": "<one of: NDA, EMPLOYMENT, SAAS, LEASE, SERVICE, UNKNOWN>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one concise sentence explaining your classification>",
  "jurisdiction_hint": "<'India', 'US', 'UK', 'EU', or null if not determinable>"
}

CONTRACT TYPE DEFINITIONS:
- NDA: Non-disclosure agreement. Core obligation is confidentiality between parties.
  Look for: "confidential information", "non-disclosure", "proprietary information"
- EMPLOYMENT: Contract governing an employer-employee relationship.
  Look for: "employee", "employer", "salary", "termination", "notice period", "probation"
- SAAS: Software-as-a-service subscription or software license agreement.
  Look for: "subscription", "software", "SaaS", "license", "uptime", "support", "API"
- LEASE: Real property or equipment rental agreement.
  Look for: "landlord", "tenant", "rent", "premises", "lease term", "security deposit"
- SERVICE: Professional services or consulting agreement (not SAAS, not employment).
  Look for: "services", "deliverables", "consultant", "contractor", "statement of work"
- UNKNOWN: Use when confidence < 0.7 or when the document is clearly none of the above.

JURISDICTION DETECTION:
Identify jurisdiction from explicit statements like:
- "This Agreement shall be governed by the laws of [jurisdiction]"
- References to specific acts (e.g., "Indian Contract Act", "GDPR", "Delaware law")
- Currency symbols, court references, regulatory bodies

CONFIDENCE CALIBRATION:
- 0.9-1.0: Explicit type indicators present (e.g., document title says "Non-Disclosure Agreement")
- 0.7-0.89: Strong implicit indicators (correct vocabulary, structure, typical clauses)
- 0.5-0.69: Ambiguous — mixed signals. Return UNKNOWN.
- <0.5: Cannot determine. Return UNKNOWN.

Remember: Return ONLY the JSON object. Nothing else."""


CONTRACT_TYPE_USER = """Classify the following contract excerpt (first ~3,000 tokens):

<contract_text>
{contract_text}
</contract_text>

Respond with the JSON classification object only."""


def build_contract_type_prompt(contract_text: str) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for contract type classification.
    Truncates input to 3000 tokens worth of characters (≈12,000 chars) for cost efficiency.
    """
    # Approximate token-to-char ratio for legal English: ~4 chars/token
    max_chars = 3000 * 4
    truncated = contract_text[:max_chars]
    if len(contract_text) > max_chars:
        truncated += "\n\n[Document continues — classification based on excerpt above]"

    return CONTRACT_TYPE_SYSTEM, CONTRACT_TYPE_USER.format(contract_text=truncated)
