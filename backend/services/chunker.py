"""
Legal-Aware Clause Chunker — Stage 2
======================================
The hardest engineering problem in ClauseGuard.

Standard text splitters destroy legal clause boundaries. A Limitation of Liability
clause that spans 4 paragraphs and references a defined term from page 1 becomes
two incoherent chunks when split on character count — neither retrieves correctly.

This chunker uses document structure signals (headings, numbered lists, defined terms)
to create semantically coherent chunks that match legal clause boundaries.

Chunking rules (in priority order):
1. HARD boundary: any block with is_heading=True
2. SOFT boundary: numbered/lettered list items (clause subclauses)
3. OVERFLOW split: at sentence boundary if chunk exceeds max_tokens
4. OVERLAP: 200-token overlap between consecutive chunks
5. CONTEXT HEADER: each chunk prepended with contract type, section, defined terms
"""

import re
import uuid
from dataclasses import dataclass

import structlog
import tiktoken

from schemas.analysis import LegalChunk
from services.document_parser import PageBlock, ParsedDocument

logger = structlog.get_logger(__name__)

# tiktoken encoder for token counting
# cl100k_base is used by GPT-4 and Claude approximates similarly.
# For exact Claude token counts we'd use the Anthropic tokenizer,
# but cl100k_base is accurate within ±5% and avoids an API call.
_ENCODER = tiktoken.get_encoding("cl100k_base")

# Subclause pattern: "1.", "1.1", "a.", "(a)", "i.", "(i)", "iv."
_SUBCLAUSE_PATTERN = re.compile(
    r"^\s*(?:\(?\d+\.\d*\)?|\(?[a-z]\)\.?|\(?(?:i{1,3}|iv|v|vi{0,3}|ix|x)\)\.?)\s+",
    re.IGNORECASE,
)


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoder."""
    return len(_ENCODER.encode(text))


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences for overflow splitting.
    Simple rule-based splitter tuned for legal English:
    - Splits on ". " followed by capital letter
    - Preserves abbreviations (Mr., Inc., Ltd., etc.)
    - Does not split on e.g., i.e., etc.
    """
    # Protect common legal abbreviations
    abbreviations = [
        "Mr.", "Ms.", "Mrs.", "Dr.", "Prof.", "Inc.", "Corp.", "Ltd.", "Co.",
        "vs.", "v.", "i.e.", "e.g.", "et al.", "No.", "Art.", "Sec.", "para.",
    ]
    protected = text
    for abbr in abbreviations:
        protected = protected.replace(abbr, abbr.replace(".", "<!DOT!>"))

    # Split on sentence-ending patterns
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"])', protected)

    # Restore protected dots
    return [s.replace("<!DOT!>", ".") for s in sentences if s.strip()]


def build_context_header(
    contract_type: str,
    section_heading: str,
    defined_terms: dict[str, str],
    terms_in_scope: list[str],
) -> str:
    """
    Build the context header prepended to each chunk at query time.
    NOT stored in the vector — injected when the chunk is retrieved.

    This is critical for correct interpretation: if "Confidential Information"
    is defined on page 1 and the clause referencing it is on page 8, Claude
    needs the definition in context to assess the clause correctly.
    """
    header_parts = [
        f"[CONTRACT TYPE: {contract_type}]",
        f"[SECTION: {section_heading}]",
    ]

    if terms_in_scope:
        # Include definitions for all terms seen earlier in the document
        term_defs = []
        for term in terms_in_scope[:10]:  # Cap at 10 to control context size
            if term in defined_terms:
                defn = defined_terms[term][:100]  # Truncate long definitions
                term_defs.append(f'"{term}": {defn}')
        if term_defs:
            header_parts.append(f"[DEFINED TERMS IN SCOPE: {'; '.join(term_defs)}]")

    return " ".join(header_parts)


def chunk_document(
    parsed_doc: ParsedDocument,
    contract_type: str,
    max_tokens: int = 800,
    overlap_tokens: int = 200,
) -> list[LegalChunk]:
    """
    Chunk a parsed document into legal-boundary-aware chunks.

    Args:
        parsed_doc: Output of document_parser.parse_document()
        contract_type: From Stage 0 classification
        max_tokens: Maximum tokens per chunk (default 800)
        overlap_tokens: Token overlap between consecutive chunks (default 200)

    Returns:
        List[LegalChunk] in document order
    """
    blocks = [b for b in parsed_doc.blocks if not b.is_empty()]
    defined_terms = parsed_doc.defined_terms

    chunks: list[LegalChunk] = []
    current_group: list[PageBlock] = []
    current_tokens = 0
    current_heading = "Preamble"
    current_page_start = 1
    terms_seen_so_far: list[str] = []  # Track which terms have been defined so far

    def flush_group(group: list[PageBlock], heading: str, page_start: int) -> None:
        """Convert a group of blocks into one or more LegalChunk objects."""
        nonlocal terms_seen_so_far

        if not group:
            return

        combined_text = "\n".join(b.text for b in group)
        page_end = group[-1].page_num if group else page_start

        # Update defined terms seen so far (terms defined in this group become available for next group)
        for term in defined_terms:
            if term in combined_text and term not in terms_seen_so_far:
                terms_seen_so_far.append(term)

        token_count = count_tokens(combined_text)

        if token_count <= max_tokens:
            # Single chunk — fits within limit
            context_header = build_context_header(
                contract_type, heading, defined_terms, terms_seen_so_far
            )
            chunks.append(LegalChunk(
                chunk_id=str(uuid.uuid4()),
                text=combined_text,
                context_header=context_header,
                page_range=(page_start, page_end),
                section_heading=heading,
                chunk_index=len(chunks),
                token_count=token_count,
            ))
        else:
            # Overflow: split at sentence boundaries, apply overlap
            sentences = split_into_sentences(combined_text)
            sub_chunk_sentences: list[str] = []
            sub_chunk_tokens = 0
            overlap_sentences: list[str] = []

            for sentence in sentences:
                sent_tokens = count_tokens(sentence)

                if sub_chunk_tokens + sent_tokens > max_tokens and sub_chunk_sentences:
                    # Emit current sub-chunk
                    sub_text = " ".join(sub_chunk_sentences)
                    context_header = build_context_header(
                        contract_type, heading, defined_terms, terms_seen_so_far
                    )
                    chunks.append(LegalChunk(
                        chunk_id=str(uuid.uuid4()),
                        text=sub_text,
                        context_header=context_header,
                        page_range=(page_start, page_end),
                        section_heading=heading,
                        chunk_index=len(chunks),
                        token_count=count_tokens(sub_text),
                    ))

                    # Start next chunk with overlap sentences
                    overlap_sentences = sub_chunk_sentences[-3:]  # Last 3 sentences = overlap
                    overlap_token_count = sum(count_tokens(s) for s in overlap_sentences)
                    # Trim overlap if it's too long
                    while overlap_token_count > overlap_tokens and len(overlap_sentences) > 1:
                        overlap_sentences.pop(0)
                        overlap_token_count = sum(count_tokens(s) for s in overlap_sentences)

                    sub_chunk_sentences = overlap_sentences + [sentence]
                    sub_chunk_tokens = sum(count_tokens(s) for s in sub_chunk_sentences)
                else:
                    sub_chunk_sentences.append(sentence)
                    sub_chunk_tokens += sent_tokens

            # Emit final sub-chunk
            if sub_chunk_sentences:
                sub_text = " ".join(sub_chunk_sentences)
                context_header = build_context_header(
                    contract_type, heading, defined_terms, terms_seen_so_far
                )
                chunks.append(LegalChunk(
                    chunk_id=str(uuid.uuid4()),
                    text=sub_text,
                    context_header=context_header,
                    page_range=(page_start, page_end),
                    section_heading=heading,
                    chunk_index=len(chunks),
                    token_count=count_tokens(sub_text),
                ))

    for block in blocks:
        if block.is_heading:
            # RULE 1: Hard boundary — flush current group, start new one
            flush_group(current_group, current_heading, current_page_start)
            current_group = []
            current_tokens = 0
            current_heading = block.text_stripped
            current_page_start = block.page_num
            # Don't add the heading block itself to the new group — it becomes the heading label
            continue

        block_tokens = count_tokens(block.text)
        is_subclause = bool(_SUBCLAUSE_PATTERN.match(block.text))

        if current_tokens + block_tokens > max_tokens:
            if is_subclause and current_group:
                # RULE 2: Soft boundary — prefer to keep subclauses together
                # but flush if we must
                flush_group(current_group, current_heading, current_page_start)
                current_group = [block]
                current_tokens = block_tokens
                current_page_start = block.page_num
            else:
                # RULE 4: Normal overflow — flush and continue
                flush_group(current_group, current_heading, current_page_start)
                current_group = [block]
                current_tokens = block_tokens
                current_page_start = block.page_num
        else:
            current_group.append(block)
            current_tokens += block_tokens

    # Flush final group
    flush_group(current_group, current_heading, current_page_start)

    # Re-index chunks sequentially
    for i, chunk in enumerate(chunks):
        object.__setattr__(chunk, "chunk_index", i)

    logger.info(
        "document_chunked",
        total_chunks=len(chunks),
        avg_tokens=sum(c.token_count for c in chunks) // max(len(chunks), 1),
        max_token_chunk=max((c.token_count for c in chunks), default=0),
        contract_type=contract_type,
    )

    return chunks
