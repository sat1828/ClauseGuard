"""
Classifier Unit Tests
Run: pytest tests/test_classifier.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.analysis import ContractTypeResult
from services.classifier import classify_contract
from services.llm_utils import parse_json_response


def make_mock_response(contract_type, confidence, reasoning="Test.", jurisdiction=None):
    return json.dumps({
        "contract_type": contract_type,
        "confidence": confidence,
        "reasoning": reasoning,
        "jurisdiction_hint": jurisdiction,
    })


@pytest.mark.asyncio
async def test_nda_classified_correctly():
    mock_json = make_mock_response("NDA", 0.96,
        "Document title and core confidentiality obligation identify this as NDA.", "US")

    with patch("services.classifier.get_anthropic_client") as mock_fn:
        client = AsyncMock()
        mock_fn.return_value = client
        msg = MagicMock()
        msg.content = [MagicMock(text=mock_json)]
        client.messages.create = AsyncMock(return_value=msg)
        result = await classify_contract("NDA contract text...", "test-nda")

    assert result.contract_type == "NDA"
    assert result.confidence >= 0.85


@pytest.mark.asyncio
async def test_employment_classified_correctly():
    mock_json = make_mock_response("EMPLOYMENT", 0.94,
        "Employment agreement with salary, notice period, non-compete.", "India")

    with patch("services.classifier.get_anthropic_client") as mock_fn:
        client = AsyncMock()
        mock_fn.return_value = client
        msg = MagicMock()
        msg.content = [MagicMock(text=mock_json)]
        client.messages.create = AsyncMock(return_value=msg)
        result = await classify_contract("Employment contract text...", "test-emp")

    assert result.contract_type == "EMPLOYMENT"
    assert result.jurisdiction_hint == "India"


@pytest.mark.asyncio
async def test_low_confidence_returns_unknown():
    mock_json = make_mock_response("SAAS", 0.55, "Mixed signals.")

    with patch("services.classifier.get_anthropic_client") as mock_fn:
        client = AsyncMock()
        mock_fn.return_value = client
        msg = MagicMock()
        msg.content = [MagicMock(text=mock_json)]
        client.messages.create = AsyncMock(return_value=msg)
        result = await classify_contract("Ambiguous text...", "test-unknown")

    assert result.contract_type == "UNKNOWN"
    assert result.confidence < 0.7


def test_parse_json_strips_markdown_fences():
    raw = '```json\n{"contract_type": "NDA", "confidence": 0.9, "reasoning": "It is an NDA.", "jurisdiction_hint": null}\n```'
    parsed = parse_json_response(raw)
    assert parsed["contract_type"] == "NDA"


def test_parse_json_plain():
    raw = '{"contract_type": "SAAS", "confidence": 0.87, "reasoning": "SaaS agreement.", "jurisdiction_hint": "US"}'
    parsed = parse_json_response(raw)
    assert parsed["contract_type"] == "SAAS"


def test_parse_json_raises_on_invalid():
    with pytest.raises(ValueError):
        parse_json_response("This is not JSON and contains nothing extractable xyz")


def test_contract_type_result_validates():
    valid = ContractTypeResult(
        contract_type="NDA",
        confidence=0.95,
        reasoning="Bilateral confidentiality obligation clearly present.",
        jurisdiction_hint="US",
    )
    assert valid.contract_type == "NDA"


def test_contract_type_result_rejects_invalid_type():
    with pytest.raises(Exception):
        ContractTypeResult(
            contract_type="INVALID_TYPE",
            confidence=0.9,
            reasoning="Test",
        )


def test_contract_type_result_rejects_bad_confidence():
    with pytest.raises(Exception):
        ContractTypeResult(
            contract_type="NDA",
            confidence=1.5,
            reasoning="Test",
        )


@pytest.mark.asyncio
async def test_long_document_truncated():
    """Verify long documents are truncated before sending to Claude."""
    long_text = "This is a contract clause. " * 1000  # ~27,000 chars
    captured = []

    async def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        if messages:
            captured.append(messages[0]["content"])
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps({
            "contract_type": "NDA", "confidence": 0.88,
            "reasoning": "NDA.", "jurisdiction_hint": None
        }))]
        return msg

    with patch("services.classifier.get_anthropic_client") as mock_fn:
        client = AsyncMock()
        mock_fn.return_value = client
        client.messages.create = mock_create
        await classify_contract(long_text, "test-long")

    assert len(captured) > 0
    assert len(captured[0]) < 15000, "Long document not properly truncated"
