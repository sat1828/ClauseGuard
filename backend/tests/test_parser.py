"""
Document Parser Unit Tests
Run: pytest tests/test_parser.py -v
"""

import os
import tempfile
import pytest

from services.document_parser import (
    extract_defined_terms, parse_txt, parse_document, PageBlock, ParsedDocument,
)


def test_txt_produces_blocks():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("NON-DISCLOSURE AGREEMENT\n\n"
                "1. CONFIDENTIALITY\nThe parties agree to strict confidence.\n\n"
                "2. GOVERNING LAW\nThis is governed by the laws of India.\n")
        tmp = f.name
    try:
        result = parse_txt(tmp)
        assert len(result.blocks) > 0
        assert result.file_type == "txt"
        assert len(result.raw_text) > 50
    finally:
        os.unlink(tmp)


def test_heading_detection():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("CONFIDENTIALITY OBLIGATIONS\n\nThe receiving party shall maintain strict confidence.\n\n"
                "PAYMENT TERMS\n\nClient pays within 30 days.\n\n"
                "This is regular body text that should not be a heading.\n")
        tmp = f.name
    try:
        result = parse_txt(tmp)
        headings = [b for b in result.blocks if b.is_heading]
        assert len(headings) >= 2
    finally:
        os.unlink(tmp)


def test_defined_term_means_pattern():
    text = '"Confidential Information" means any data disclosed by the Disclosing Party that is designated as confidential.'
    terms = extract_defined_terms(text)
    assert "Confidential Information" in terms


def test_defined_term_shall_mean():
    text = '"Intellectual Property" shall mean all inventions, patents, and copyrights.'
    terms = extract_defined_terms(text)
    assert "Intellectual Property" in terms


def test_empty_document():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("   \n\n   \n")
        tmp = f.name
    try:
        result = parse_txt(tmp)
        non_empty = [b for b in result.blocks if b.text.strip()]
        assert len(non_empty) == 0
    finally:
        os.unlink(tmp)


def test_page_count_estimates_correctly():
    text = "This is a sentence with five words. " * 120  # ~720 words
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text)
        tmp = f.name
    try:
        result = parse_txt(tmp)
        assert result.total_pages >= 2
    finally:
        os.unlink(tmp)


def test_parse_document_routes_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("EMPLOYMENT AGREEMENT\nEmployee shall receive a salary.")
        tmp = f.name
    try:
        result = parse_document(tmp)
        assert result.file_type == "txt"
        assert len(result.blocks) > 0
    finally:
        os.unlink(tmp)


def test_parse_document_rejects_unsupported():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rtf", delete=False) as f:
        f.write("RTF content")
        tmp = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            parse_document(tmp)
    finally:
        os.unlink(tmp)


def test_raw_text_contains_all_blocks():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("SECTION ONE\nFirst paragraph content here.\n\nSECTION TWO\nSecond paragraph.\n")
        tmp = f.name
    try:
        result = parse_txt(tmp)
        assert "First paragraph" in result.raw_text
        assert "Second paragraph" in result.raw_text
    finally:
        os.unlink(tmp)


def test_sample_nda_parses():
    p = os.path.join(os.path.dirname(__file__),
                     "..", "evaluation", "test_contracts", "sample_nda.txt")
    if not os.path.exists(p):
        pytest.skip("sample_nda.txt not found")
    result = parse_document(p)
    assert len(result.blocks) > 5
    assert "Confidential Information" in result.raw_text
    assert len(result.defined_terms) >= 1
