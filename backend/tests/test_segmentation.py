import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.segmentation import segment_clauses, MIN_CLAUSE_WORDS, MAX_CLAUSE_TOKENS, _approx_tokens

NUMBERED_CONTRACT = """
1. Term. This Agreement shall commence on the Effective Date and continue for a period of twelve (12) months, and shall automatically renew for successive twelve (12) month periods unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.

2. Fees. Client shall pay Provider a monthly fee of $5,000, due on the first day of each month. Late payments shall accrue interest at 1.5% per month.

3. Limitation of Liability. IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF THIS AGREEMENT, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES, EXCEPT THAT PROVIDER'S TOTAL LIABILITY SHALL BE UNCAPPED FOR CLAIMS ARISING FROM GROSS NEGLIGENCE OR WILLFUL MISCONDUCT.

3.1 Notwithstanding the foregoing, Provider's aggregate liability arising out of or related to this Agreement shall not exceed the total fees paid by Client in the twelve (12) months preceding the claim.

4. Intellectual Property. All work product, inventions, and deliverables created by Provider in the course of performing services under this Agreement shall be the sole and exclusive property of Client upon full payment, and Provider hereby assigns all right, title, and interest in such work product to Client.

5. Termination. Either party may terminate this Agreement for convenience upon thirty (30) days written notice to the other party.
"""

CAPS_HEADING_CONTRACT = """
DEFINITIONS

The following terms shall have the meanings set forth below wherever used in this Agreement, unless the context clearly requires otherwise, and such definitions shall apply consistently throughout every section of this document.

GOVERNING LAW

This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of laws principles, and the parties consent to exclusive jurisdiction in Delaware courts.

CONFIDENTIALITY

Each party agrees to maintain the confidentiality of all proprietary information disclosed by the other party during the term of this Agreement and for a period of five years thereafter, using at least the same degree of care it uses to protect its own confidential information.

DISPUTE RESOLUTION

Any dispute arising out of or relating to this Agreement shall be resolved through binding arbitration administered by the American Arbitration Association in accordance with its Commercial Arbitration Rules.
"""

PURE_PROSE_CONTRACT = """
This is a simple freelance agreement between the Client and the Contractor for the design of a company logo and associated brand assets to be delivered within four weeks of signing this agreement by both parties involved.

The Contractor retains no ownership over the final delivered files once full payment has been received, and all rights transfer immediately and irrevocably to the Client upon receipt of the final invoice payment in full.

Payment shall be made in two installments: fifty percent upfront before work begins, and the remaining fifty percent due upon final delivery and Client's written approval of the completed brand assets and associated source files.
""" * 2  # duplicate paragraphs to exceed word thresholds reliably


def test_numbered_sections_detected():
    clauses = segment_clauses(NUMBERED_CONTRACT)
    assert len(clauses) >= 5, f"expected >=5 clauses, got {len(clauses)}: {clauses}"
    assert any("automatically renew" in c for c in clauses)
    assert any("Intellectual Property" in c for c in clauses)


def test_caps_heading_sections_detected():
    clauses = segment_clauses(CAPS_HEADING_CONTRACT)
    assert len(clauses) >= 3, f"expected >=3 clauses, got {len(clauses)}: {clauses}"
    assert any("arbitration" in c.lower() for c in clauses)


def test_pure_prose_falls_back_to_paragraphs():
    clauses = segment_clauses(PURE_PROSE_CONTRACT)
    assert len(clauses) >= 1
    for c in clauses:
        assert len(c.split()) >= MIN_CLAUSE_WORDS, f"clause too short: {c!r}"


def test_never_returns_empty_for_nonempty_input():
    weird_text = "word " * 500  # no structure at all
    clauses = segment_clauses(weird_text)
    assert len(clauses) > 0


def test_empty_input_returns_empty():
    assert segment_clauses("") == []
    assert segment_clauses("   \n\n  ") == []


def test_oversized_clause_gets_split():
    long_sentence_block = ". ".join([f"This is filler sentence number {i} about contract terms" for i in range(200)]) + "."
    text = "1. Big Section\n" + long_sentence_block
    clauses = segment_clauses(text)
    for c in clauses:
        assert _approx_tokens(c) <= MAX_CLAUSE_TOKENS + 50, f"clause exceeds token budget: {_approx_tokens(c)} tokens"


def test_short_fragments_get_merged():
    text = "1. A.\n\n2. This next section actually has real substantive content that goes well beyond the minimum word threshold required for a standalone clause to survive merging logic."
    clauses = segment_clauses(text)
    for c in clauses:
        assert len(c.split()) >= MIN_CLAUSE_WORDS


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
