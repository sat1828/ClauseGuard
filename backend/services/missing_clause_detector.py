"""
Missing Clause Detector — Stage 6
====================================
Compares identified clauses against required templates per contract type.
Flags structurally absent clauses with severity and guidance.
"""

import structlog

from schemas.analysis import ClauseExtractionResult, MissingClause

logger = structlog.get_logger(__name__)

# Required clause templates per contract type
# Severity: CRITICAL > IMPORTANT > RECOMMENDED
REQUIRED_CLAUSES: dict[str, list[dict]] = {
    "NDA": [
        {
            "clause_type": "CONFIDENTIALITY",
            "severity": "CRITICAL",
            "why_it_matters": "Without an explicit confidentiality obligation, the entire purpose of an NDA is unenforceable. There is no legal basis to sue if the other party discloses your information.",
            "example_language": 'Each Party agrees to hold the other Party\'s Confidential Information in strict confidence and not to disclose it to any third party without prior written consent.',
        },
        {
            "clause_type": "DEFINITIONS",
            "severity": "CRITICAL",
            "why_it_matters": "Without defining what counts as 'Confidential Information,' disputes will arise over whether disclosed information was actually protected. Courts cannot enforce protection over undefined information.",
            "example_language": '"Confidential Information" means any data or information disclosed by one Party to the other that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information.',
        },
        {
            "clause_type": "GOVERNING_LAW",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a governing law clause, a dispute about which jurisdiction's laws apply can delay resolution for months and dramatically increase legal costs.",
            "example_language": "This Agreement shall be governed by and construed in accordance with the laws of [Jurisdiction], without regard to its conflict of laws principles.",
        },
        {
            "clause_type": "DISPUTE_RESOLUTION",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a dispute resolution clause, any disagreement defaults to expensive litigation in a court that may be inconvenient for both parties.",
            "example_language": "Any dispute arising from this Agreement shall first be addressed through good-faith negotiation. If unresolved within 30 days, the parties may proceed to binding arbitration.",
        },
        {
            "clause_type": "FORCE_MAJEURE",
            "severity": "RECOMMENDED",
            "why_it_matters": "Without force majeure, a party could be held liable for breach even when performance was impossible due to events outside their control (natural disasters, pandemics, government action).",
            "example_language": "Neither party shall be liable for delays or failures in performance resulting from causes beyond their reasonable control, including acts of God, natural disasters, or government actions.",
        },
    ],
    "EMPLOYMENT": [
        {
            "clause_type": "PAYMENT_TERMS",
            "severity": "CRITICAL",
            "why_it_matters": "Without explicit payment terms, compensation disputes are extremely difficult to resolve and the employee may have difficulty proving what was agreed.",
            "example_language": "The Employee shall receive a gross annual salary of [Amount], payable in equal monthly installments on the last business day of each month.",
        },
        {
            "clause_type": "IP_ASSIGNMENT",
            "severity": "IMPORTANT",
            "why_it_matters": "Without an IP clause, ownership of work product created during employment is legally ambiguous and can cause disputes years after employment ends.",
            "example_language": "Work product created by Employee in the course of their employment using Company resources shall be the exclusive property of the Company.",
        },
        {
            "clause_type": "TERMINATION_FOR_CAUSE",
            "severity": "IMPORTANT",
            "why_it_matters": "Without defined termination conditions, the employer may claim almost anything as grounds for dismissal without compensation, leaving the employee with no recourse.",
            "example_language": 'The Company may terminate this Agreement for cause upon written notice if the Employee commits gross misconduct, material breach, or is convicted of a criminal offense.',
        },
        {
            "clause_type": "NOTICE",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a notice period, either party can terminate the employment relationship without warning, leaving the employee without income or the employer without transition time.",
            "example_language": "Either party may terminate this Agreement by providing [30/60/90] days written notice to the other party.",
        },
        {
            "clause_type": "DATA_PROTECTION",
            "severity": "IMPORTANT",
            "why_it_matters": "In India (DPDPA 2023) and EU (GDPR), employers have legal obligations regarding employee personal data. Absence of this clause may indicate non-compliant data practices.",
            "example_language": "The Company shall process Employee personal data only for lawful employment purposes and in accordance with applicable data protection laws.",
        },
        {
            "clause_type": "GOVERNING_LAW",
            "severity": "RECOMMENDED",
            "why_it_matters": "Employment law varies significantly between jurisdictions. Without specifying which laws apply, the employee may not know which legal protections they have.",
            "example_language": "This Agreement shall be governed by the laws of [State/Country] and the Employee's rights shall be subject to applicable local employment legislation.",
        },
    ],
    "SAAS": [
        {
            "clause_type": "PAYMENT_TERMS",
            "severity": "CRITICAL",
            "why_it_matters": "Without clear payment terms, the vendor can change pricing at any time without notice, creating unpredictable costs for the customer.",
            "example_language": "Subscription fees are [Amount] per [month/year], due in advance. Pricing is fixed for the current subscription term and may be adjusted with 60 days written notice.",
        },
        {
            "clause_type": "AUTO_RENEWAL",
            "severity": "CRITICAL",
            "why_it_matters": "SaaS contracts are notorious for hidden auto-renewal clauses that trap customers in unwanted subscriptions. Without clarity here, you may be billed for a year you didn't intend to continue.",
            "example_language": "This Agreement will automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least 45 days before the renewal date.",
        },
        {
            "clause_type": "DATA_PROTECTION",
            "severity": "CRITICAL",
            "why_it_matters": "Any SaaS product processes customer data. Without explicit data protection terms, the vendor has no binding obligations on how they handle, store, or share your data.",
            "example_language": "Vendor shall process Customer data only on documented instructions, implement appropriate security measures, and delete Customer data within 30 days of contract termination.",
        },
        {
            "clause_type": "LIMITATION_OF_LIABILITY",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a liability cap, a SaaS vendor could face unlimited damages from a single incident. This often drives up pricing and creates unpredictable risk for both parties.",
            "example_language": "Each party's aggregate liability shall not exceed the fees paid by Customer in the 12 months preceding the incident giving rise to the claim.",
        },
        {
            "clause_type": "WARRANTY_DISCLAIMER",
            "severity": "RECOMMENDED",
            "why_it_matters": "Without warranty terms, implied warranties under law may apply that expose the vendor to claims of fitness for purpose that the software cannot realistically meet.",
            "example_language": 'The Service is provided "as is." Vendor disclaims all implied warranties of merchantability, fitness for a particular purpose, and non-infringement.',
        },
        {
            "clause_type": "TERMINATION_FOR_CONVENIENCE",
            "severity": "RECOMMENDED",
            "why_it_matters": "Without a termination right, the customer may be locked into a service even if it becomes unusable, too expensive, or is replaced by a better alternative.",
            "example_language": "Either party may terminate this Agreement with 30 days written notice. Customer will receive a pro-rated refund of pre-paid fees for the unused subscription period.",
        },
    ],
    "LEASE": [
        {
            "clause_type": "PAYMENT_TERMS",
            "severity": "CRITICAL",
            "why_it_matters": "Without explicit rent amount, payment schedule, and accepted payment methods, rental disputes are extremely difficult to resolve.",
            "example_language": "Tenant shall pay monthly rent of [Amount] on or before the [date] of each month via [payment method] to [Landlord details].",
        },
        {
            "clause_type": "TERMINATION_FOR_CAUSE",
            "severity": "CRITICAL",
            "why_it_matters": "Without defined eviction conditions, the landlord may claim any reason to evict, or the tenant may not know what constitutes a lease violation.",
            "example_language": "Landlord may terminate this lease for cause upon [X] days written notice for non-payment of rent, material breach, or illegal use of the premises.",
        },
        {
            "clause_type": "NOTICE",
            "severity": "IMPORTANT",
            "why_it_matters": "Without formal notice requirements, disputes about whether a notice was properly given can void otherwise valid terminations or renewals.",
            "example_language": "All notices under this Agreement shall be in writing, delivered by registered post or hand delivery to the addresses specified above.",
        },
        {
            "clause_type": "AUTO_RENEWAL",
            "severity": "IMPORTANT",
            "why_it_matters": "Without clarity on renewal terms, both parties face uncertainty about the lease term after the initial period ends, potentially creating holdover liability.",
            "example_language": "This lease shall not automatically renew. The parties must execute a new lease or written extension before the expiry date to continue occupancy.",
        },
        {
            "clause_type": "GOVERNING_LAW",
            "severity": "IMPORTANT",
            "why_it_matters": "Local tenancy laws often override contract terms. Without specifying jurisdiction, tenant protection laws may not be clearly applicable.",
            "example_language": "This Agreement shall be governed by the laws of [State/Province], including applicable residential tenancy legislation.",
        },
        {
            "clause_type": "ASSIGNMENT",
            "severity": "RECOMMENDED",
            "why_it_matters": "Without an assignment clause, subletting or transferring the lease is legally ambiguous, which can cause problems if the tenant needs to leave early.",
            "example_language": "Tenant may not assign this lease or sublet the premises without Landlord's prior written consent, which shall not be unreasonably withheld.",
        },
    ],
    "SERVICE": [
        {
            "clause_type": "PAYMENT_TERMS",
            "severity": "CRITICAL",
            "why_it_matters": "Without payment terms in a service agreement, the contractor has no clear legal basis to demand payment or enforce payment timelines.",
            "example_language": "Client shall pay all invoices within 30 days of receipt. Invoices will be issued [monthly/upon milestone completion/as specified in the SOW].",
        },
        {
            "clause_type": "WORK_PRODUCT",
            "severity": "IMPORTANT",
            "why_it_matters": "Without clear ownership of deliverables, both parties may claim rights to the work product, creating costly IP disputes after project completion.",
            "example_language": "Upon receipt of full payment, Contractor assigns to Client all right, title, and interest in the deliverables specified in the Statement of Work.",
        },
        {
            "clause_type": "TERMINATION_FOR_CONVENIENCE",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a termination right, both parties may be trapped in an unsatisfactory engagement with no clean exit mechanism.",
            "example_language": "Either party may terminate this Agreement with 30 days written notice. Client shall pay for all work completed and expenses incurred through the notice period.",
        },
        {
            "clause_type": "LIMITATION_OF_LIABILITY",
            "severity": "IMPORTANT",
            "why_it_matters": "Without a liability cap, a service provider could face catastrophic damages from a single error, making the engagement economically irrational to perform.",
            "example_language": "Contractor's aggregate liability shall not exceed the total fees paid in the 3 months preceding the incident giving rise to the claim.",
        },
        {
            "clause_type": "GOVERNING_LAW",
            "severity": "RECOMMENDED",
            "why_it_matters": "Professional services contracts often cross jurisdictional lines. Without a governing law clause, disputes about which rules apply can precede any substantive resolution.",
            "example_language": "This Agreement shall be governed by the laws of [Jurisdiction], and any disputes shall be resolved in the courts of [Location].",
        },
    ],
    "UNKNOWN": [],  # Cannot check missing clauses for unknown contract type
}


def detect_missing_clauses(
    identified_clauses: list[ClauseExtractionResult],
    contract_type: str,
    contract_id: str,
) -> list[MissingClause]:
    """
    Stage 6: Detect structurally absent clauses.

    Compares the set of identified clause types against the required template
    for this contract type. Returns MissingClause objects for each gap.
    """
    template = REQUIRED_CLAUSES.get(contract_type, [])

    if not template:
        logger.info(
            "no_template_available",
            contract_id=contract_id,
            contract_type=contract_type,
        )
        return []

    # Build set of identified clause types (case-insensitive)
    identified_types = {c.clause_type.upper() for c in identified_clauses}

    missing: list[MissingClause] = []
    for required in template:
        if required["clause_type"].upper() not in identified_types:
            missing.append(
                MissingClause(
                    clause_type=required["clause_type"],
                    severity=required["severity"],
                    why_it_matters=required["why_it_matters"],
                    example_language=required["example_language"],
                )
            )
            logger.debug(
                "missing_clause_detected",
                contract_id=contract_id,
                clause_type=required["clause_type"],
                severity=required["severity"],
            )

    logger.info(
        "missing_clause_detection_complete",
        contract_id=contract_id,
        contract_type=contract_type,
        missing_count=len(missing),
        checked_count=len(template),
    )

    return missing
