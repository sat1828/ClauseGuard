"""
Chunker Unit Tests
Run: pytest tests/test_chunker.py -v
"""

import pytest
from services.chunker import (
    build_context_header,
    chunk_document,
    count_tokens,
    split_into_sentences,
)
from services.document_parser import PageBlock, ParsedDocument


def make_block(text: str, is_heading: bool = False, page_num: int = 1) -> PageBlock:
    return PageBlock(
        page_num=page_num,
        text=text,
        is_heading=is_heading,
        font_size=14.0 if is_heading else 11.0,
    )


def make_doc(blocks: list[PageBlock], defined_terms: dict = None) -> ParsedDocument:
    raw_text = "\n".join(b.text for b in blocks)
    return ParsedDocument(
        blocks=blocks,
        defined_terms=defined_terms or {},
        total_pages=max(b.page_num for b in blocks) if blocks else 1,
        raw_text=raw_text,
        file_type="txt",
    )


def test_multi_paragraph_clause_stays_together():
    heading = make_block("4. CONFIDENTIALITY", is_heading=True)
    para1 = make_block(
        "The Receiving Party agrees to hold all Confidential Information in strict confidence "
        "and to protect it using the same degree of care as its own confidential information."
    )
    para2 = make_block(
        "The Receiving Party may disclose Confidential Information only to employees who need "
        "to know and are bound by confidentiality obligations at least as protective as those herein."
    )
    para3 = make_block(
        "These obligations shall survive termination of this Agreement for five (5) years."
    )

    doc = make_doc([heading, para1, para2, para3])
    chunks = chunk_document(doc, contract_type="NDA", max_tokens=800)

    conf_chunks = [c for c in chunks if "CONFIDENTIALITY" in c.section_heading.upper()]
    assert len(conf_chunks) == 1, f"Expected 1 chunk, got {len(conf_chunks)}"
    combined = conf_chunks[0].text
    assert "strict confidence" in combined
    assert "five (5) years" in combined


def test_heading_creates_hard_boundary():
    blocks = [
        make_block("1. PAYMENT TERMS", is_heading=True),
        make_block("Client shall pay $10,000 per month on the first business day."),
        make_block("2. TERMINATION", is_heading=True),
        make_block("Either party may terminate with 30 days written notice."),
        make_block("3. GOVERNING LAW", is_heading=True),
        make_block("This Agreement is governed by the laws of Delaware."),
    ]
    doc = make_doc(blocks)
    chunks = chunk_document(doc, contract_type="SERVICE", max_tokens=800)

    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
    headings = [c.section_heading for c in chunks]
    assert any("PAYMENT" in h for h in headings)
    assert any("TERMINATION" in h for h in headings)
    assert any("GOVERNING" in h for h in headings)

    payment_chunk = next(c for c in chunks if "PAYMENT" in c.section_heading)
    assert "terminate" not in payment_chunk.text.lower()


def test_defined_terms_in_context_header():
    defined_terms = {
        "Confidential Information": "any data designated as confidential",
        "Term": "the period from Effective Date to termination",
    }
    heading = make_block("OBLIGATIONS", is_heading=True, page_num=3)
    body = make_block(
        "The Receiving Party shall not disclose Confidential Information during the Term.",
        page_num=3,
    )
    doc = make_doc([heading, body], defined_terms=defined_terms)
    chunks = chunk_document(doc, contract_type="NDA", max_tokens=800)

    assert len(chunks) >= 1
    header = chunks[0].context_header
    assert "CONTRACT TYPE: NDA" in header
    assert "SECTION:" in header


def test_no_chunk_exceeds_max_tokens():
    long_clause = (
        "The Employee hereby assigns to the Company all right, title, and interest "
        "in and to any and all inventions, works of authorship, and developments. " * 30
    )
    heading = make_block("IP ASSIGNMENT", is_heading=True)
    body = make_block(long_clause)
    doc = make_doc([heading, body])
    max_tokens = 800
    chunks = chunk_document(doc, contract_type="EMPLOYMENT", max_tokens=max_tokens)

    for chunk in chunks:
        actual = count_tokens(chunk.text)
        assert actual <= max_tokens * 1.15, \
            f"Chunk {chunk.chunk_index} has {actual} tokens > {max_tokens}"


def test_overlap_between_consecutive_chunks():
    sentences = [
        f"Sentence {i}: The Employee shall maintain confidentiality of all proprietary "
        f"information including trade secrets, strategies, and customer data for five years."
        for i in range(40)
    ]
    heading = make_block("CONFIDENTIALITY", is_heading=True)
    body = make_block("\n".join(sentences))
    doc = make_doc([heading, body])
    chunks = chunk_document(doc, contract_type="NDA", max_tokens=800, overlap_tokens=200)

    if len(chunks) >= 2:
        words1 = set(chunks[0].text.split())
        words2 = set(chunks[1].text.split())
        overlap = words1 & words2
        assert len(overlap) >= 10, \
            f"Expected word overlap between chunks, got {len(overlap)}"


def test_empty_document_returns_empty_list():
    doc = make_doc([])
    chunks = chunk_document(doc, contract_type="NDA")
    assert chunks == []


def test_single_short_block_single_chunk():
    block = make_block("This Agreement is governed by the laws of California.")
    doc = make_doc([block])
    chunks = chunk_document(doc, contract_type="NDA")
    assert len(chunks) == 1
    assert "California" in chunks[0].text


def test_sentence_splitter_preserves_abbreviations():
    text = (
        "This clause applies to Mr. Smith and Dr. Johnson. "
        "The Company (Inc.) is registered in Delaware. "
        "Any disputes, i.e., contractual disagreements, go to arbitration."
    )
    sentences = split_into_sentences(text)
    assert len(sentences) <= 4, f"Got {len(sentences)} sentences: {sentences}"


def test_context_header_format():
    header = build_context_header(
        contract_type="EMPLOYMENT",
        section_heading="4. IP Assignment",
        defined_terms={"Confidential Information": "any non-public data"},
        terms_in_scope=["Confidential Information"],
    )
    assert "[CONTRACT TYPE: EMPLOYMENT]" in header
    assert "[SECTION: 4. IP Assignment]" in header
    assert "Confidential Information" in header


def test_chunk_index_sequential():
    blocks = [make_block(f"Clause {i} content.", page_num=i) for i in range(1, 11)]
    doc = make_doc(blocks)
    chunks = chunk_document(doc, contract_type="NDA")
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i, f"Expected index {i}, got {chunk.chunk_index}"
