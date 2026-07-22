import sys, os, asyncio, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

os.environ.setdefault("GROQ_API_KEY", "fake_key_for_smoke_test")

from app.main import app
from app import ai_client

SAMPLE_CONTRACT = """
1. Term and Renewal. This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of cancellation at least ninety (90) days before the end of the current term, which is an unusually long and easy-to-miss notice window for a small business to track manually.

2. Limitation of Liability. IN NO EVENT SHALL PROVIDER'S LIABILITY UNDER THIS AGREEMENT BE LIMITED IN ANY WAY, AND CLIENT SHALL BE FULLY LIABLE FOR ANY AND ALL DAMAGES ARISING FROM ANY BREACH WHATSOEVER, WITH NO CAP OR CEILING OF ANY KIND APPLIED TO SUCH LIABILITY UNDER ANY CIRCUMSTANCES.

3. Intellectual Property Assignment. All work product created by Contractor during the engagement, including pre-existing tools and libraries incorporated into deliverables, shall become the sole and exclusive property of Client immediately upon creation, regardless of payment status.

4. Payment Terms. Client shall pay Contractor within thirty (30) days of receiving a valid invoice for services rendered during the applicable billing period under this Agreement.
"""

FAKE_AI_RESPONSES = [
    {
        "clause_type": "auto_renewal", "risk_score": 8, "risk_label": "high",
        "plain_english_explanation": "This clause auto-renews your contract unless you cancel 90 days early, which is easy to miss and could lock you in for another year.",
        "suggested_safer_language": "Either party may cancel with 30 days notice before renewal.",
        "confidence_score": 0.85, "flags": ["auto_renewal"],
    },
    {
        "clause_type": "uncapped_liability", "risk_score": 10, "risk_label": "critical",
        "plain_english_explanation": "Your liability has no cap at all — a single mistake could bankrupt your business with no ceiling on damages owed.",
        "suggested_safer_language": "Liability shall be capped at fees paid in the preceding 12 months.",
        "confidence_score": 0.9, "flags": ["uncapped_liability"],
    },
    {
        "clause_type": "ip_ownership", "risk_score": 7, "risk_label": "high",
        "plain_english_explanation": "This clause claims ownership of even pre-existing tools you bring into the project, not just new work created for the client.",
        "suggested_safer_language": "Only work product created specifically for this engagement transfers to Client.",
        "confidence_score": 0.75, "flags": ["ip_grab"],
    },
    {
        "clause_type": "payment_terms", "risk_score": 2, "risk_label": "low",
        "plain_english_explanation": "Standard 30-day payment terms tied to invoicing. Nothing unusual here.",
        "suggested_safer_language": None,
        "confidence_score": 0.95, "flags": [],
    },
]


def _fake_call_groq(self, clause_text):
    """Deterministically map each sample clause to its canned response by keyword,
    simulating what a real Groq call would return — without touching the network."""
    if "automatically renew" in clause_text:
        return json.dumps(FAKE_AI_RESPONSES[0])
    if "LIABILITY" in clause_text and "LIMITED IN ANY WAY" in clause_text:
        return json.dumps(FAKE_AI_RESPONSES[1])
    if "Intellectual Property" in clause_text:
        return json.dumps(FAKE_AI_RESPONSES[2])
    return json.dumps(FAKE_AI_RESPONSES[3])


@pytest.mark.asyncio
async def test_full_pipeline_register_upload_analyze_results(tmp_path):
    # Isolate storage for this test run — mutate the shared singleton's root
    # rather than rebinding the name, since every module holds its own
    # `from app.storage import storage` reference to the same object.
    from app.storage import storage as storage_singleton
    from pathlib import Path
    storage_singleton.root = Path(str(tmp_path / "uploads"))
    storage_singleton.root.mkdir(parents=True, exist_ok=True)

    with patch.object(ai_client.GroqClauseAnalyzer, "_call_groq", _fake_call_groq):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register
            r = await client.post("/api/auth/register", json={"email": "sat@example.com", "password": "testpass123"})
            assert r.status_code == 201, r.text
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Duplicate register should 409
            r_dup = await client.post("/api/auth/register", json={"email": "sat@example.com", "password": "testpass123"})
            assert r_dup.status_code == 409

            # Login
            r_login = await client.post("/api/auth/login", json={"email": "sat@example.com", "password": "testpass123"})
            assert r_login.status_code == 200

            # Wrong password should 401
            r_bad = await client.post("/api/auth/login", json={"email": "sat@example.com", "password": "wrong"})
            assert r_bad.status_code == 401

            # me
            r_me = await client.get("/api/auth/me", headers=headers)
            assert r_me.status_code == 200
            assert r_me.json()["analyses_limit"] == 3

            # Upload
            files = {"file": ("contract.pdf", _build_test_pdf(SAMPLE_CONTRACT), "application/pdf")}
            r_upload = await client.post("/api/documents/upload", headers=headers, files=files)
            assert r_upload.status_code == 201, r_upload.text
            doc_id = r_upload.json()["document_id"]
            assert r_upload.json()["status"] == "pending"

            # Poll status until complete (workers run in-process via lifespan,
            # but ASGITransport doesn't run lifespan automatically — drive it manually)
            from app.job_queue import _process_document
            await _process_document(doc_id)

            r_status = await client.get(f"/api/documents/{doc_id}/status", headers=headers)
            assert r_status.status_code == 200
            assert r_status.json()["status"] == "complete", r_status.json()

            # Results
            r_results = await client.get(f"/api/documents/{doc_id}/results", headers=headers)
            assert r_results.status_code == 200
            results = r_results.json()

            assert results["clauses_total"] == 4
            assert results["clauses_failed"] == 0
            assert results["overall_risk_score"] is not None
            assert results["overall_risk_label"] in ("high", "critical")  # dragged up by the uncapped liability clause
            assert results["disclaimer"].startswith("ClauseGuard provides information, not legal advice")

            flag_types = {f["flag_type"] for f in results["flags"]}
            assert "auto_renewal" in flag_types
            assert "uncapped_liability" in flag_types
            assert "ip_grab" in flag_types

            # Clauses sorted by document order in raw endpoint
            clause_types = [c["clause_type"] for c in results["clauses"]]
            assert "auto_renewal" in clause_types
            assert "uncapped_liability" in clause_types

            # Another user cannot see this document
            r_reg2 = await client.post("/api/auth/register", json={"email": "other@example.com", "password": "testpass123"})
            token2 = r_reg2.json()["access_token"]
            r_forbidden = await client.get(f"/api/documents/{doc_id}/results", headers={"Authorization": f"Bearer {token2}"})
            assert r_forbidden.status_code == 404  # not 403 — never confirm existence to a non-owner

            # Quota enforcement: user has used 1/3, use 2 more, then hit the wall
            for _ in range(2):
                files2 = {"file": ("contract2.pdf", _build_test_pdf(SAMPLE_CONTRACT), "application/pdf")}
                r2 = await client.post("/api/documents/upload", headers=headers, files=files2)
                assert r2.status_code == 201
            files3 = {"file": ("contract3.pdf", _build_test_pdf(SAMPLE_CONTRACT), "application/pdf")}
            r3 = await client.post("/api/documents/upload", headers=headers, files=files3)
            assert r3.status_code == 403
            assert "limit" in r3.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_password_protected_and_garbage_uploads_fail_gracefully(tmp_path):
    from app.storage import storage as storage_singleton
    from pathlib import Path
    storage_singleton.root = Path(str(tmp_path / "uploads2"))
    storage_singleton.root.mkdir(parents=True, exist_ok=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={"email": "garbage@example.com", "password": "testpass123"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Not a real PDF at all
        files = {"file": ("fake.pdf", b"this is not a real pdf file at all", "application/pdf")}
        r_upload = await client.post("/api/documents/upload", headers=headers, files=files)
        assert r_upload.status_code == 201
        doc_id = r_upload.json()["document_id"]

        from app.job_queue import _process_document
        await _process_document(doc_id)

        r_status = await client.get(f"/api/documents/{doc_id}/status", headers=headers)
        assert r_status.json()["status"] == "failed"
        assert r_status.json()["error_code"] in ("parse_failed", "text_too_short")


def _build_test_pdf(text: str) -> bytes:
    """insert_text does NOT wrap long lines — it silently clips at the page
    edge, which corrupts clause content. insert_textbox wraps properly,
    matching what a real word processor -> PDF export actually produces."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
    page.insert_textbox(rect, text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


@pytest.mark.asyncio
async def test_clauses_and_flags_endpoints_match_results_payload(tmp_path):
    """The frontend only ever calls /results (it embeds clauses+flags already),
    so these two standalone endpoints — required by the original spec for
    programmatic/API consumers — had zero test coverage until now. Confirming
    they actually work and agree with /results, not just that they exist."""
    from app.storage import storage as storage_singleton
    from pathlib import Path
    storage_singleton.root = Path(str(tmp_path / "uploads_standalone"))
    storage_singleton.root.mkdir(parents=True, exist_ok=True)

    with patch.object(ai_client.GroqClauseAnalyzer, "_call_groq", _fake_call_groq):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/api/auth/register", json={"email": "standalone_endpoints@example.com", "password": "testpass123"})
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            files = {"file": ("contract.pdf", _build_test_pdf(SAMPLE_CONTRACT), "application/pdf")}
            r_upload = await client.post("/api/documents/upload", headers=headers, files=files)
            doc_id = r_upload.json()["document_id"]

            from app.job_queue import _process_document
            await _process_document(doc_id)

            r_results = await client.get(f"/api/documents/{doc_id}/results", headers=headers)
            results = r_results.json()

            r_clauses = await client.get(f"/api/documents/{doc_id}/clauses", headers=headers)
            assert r_clauses.status_code == 200
            clauses = r_clauses.json()
            assert len(clauses) == len(results["clauses"])
            assert {c["id"] for c in clauses} == {c["id"] for c in results["clauses"]}

            r_flags = await client.get(f"/api/documents/{doc_id}/flags", headers=headers)
            assert r_flags.status_code == 200
            flags = r_flags.json()
            assert len(flags) == len(results["flags"])
            assert {f["flag_type"] for f in flags} == {f["flag_type"] for f in results["flags"]}

            # Cross-user access denial applies to these endpoints too, not just /results
            r_reg2 = await client.post("/api/auth/register", json={"email": "standalone_other@example.com", "password": "testpass123"})
            token2 = r_reg2.json()["access_token"]
            r_forbidden = await client.get(f"/api/documents/{doc_id}/clauses", headers={"Authorization": f"Bearer {token2}"})
            assert r_forbidden.status_code == 404
