"""
RAG Chain — Stage 7
=====================
Ask-the-contract Q&A with mandatory citation grounding.

The @traceable decorator cannot be applied to async generators.
Instead, we wrap the core LLM call in a separate traced function,
and the generator streams the already-computed tokens.
"""

import json
import re
import time
from typing import AsyncGenerator, Optional

import structlog
from langsmith import traceable

from config import get_settings
from prompts.rag_qa import build_rag_qa_prompt
from schemas.analysis import ChatResponse, Citation
from services.embedder import query_chunks
from services.llm_utils import get_anthropic_client

logger = structlog.get_logger(__name__)
settings = get_settings()


@traceable(
    name="rag_retrieve_and_prepare",
    tags=["rag-qa"],
    metadata={"pipeline_stage": "7_rag_qa"},
)
async def _retrieve_and_build_prompt(
    question: str,
    contract_id: str,
    pinecone_namespace: str,
    contract_type: str,
    jurisdiction: str,
    conversation_history: list[dict],
) -> tuple[str, str, list[dict]]:
    """
    Retrieve relevant chunks and build the RAG prompt.
    This function IS traced in LangSmith.
    Returns: (system_prompt, user_prompt, retrieved_chunks)
    """
    retrieved_chunks = await query_chunks(
        question=question,
        contract_id=contract_id,
        top_k=settings.RAG_TOP_K,
        contract_namespace=pinecone_namespace,
    )

    system_prompt, user_prompt = build_rag_qa_prompt(
        question=question,
        retrieved_chunks=retrieved_chunks,
        contract_type=contract_type,
        jurisdiction=jurisdiction,
        conversation_history=conversation_history,
    )

    return system_prompt, user_prompt, retrieved_chunks


async def stream_chat_response(
    question: str,
    contract_id: str,
    pinecone_namespace: str,
    contract_type: str,
    jurisdiction: str,
    conversation_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Stream a grounded answer to a contract question.
    Yields SSE-formatted strings for FastAPI StreamingResponse.
    """
    client = get_anthropic_client()
    start_time = time.time()

    try:
        # Retrieve and build prompt (traced in LangSmith)
        system_prompt, user_prompt, retrieved_chunks = await _retrieve_and_build_prompt(
            question=question,
            contract_id=contract_id,
            pinecone_namespace=pinecone_namespace,
            contract_type=contract_type,
            jurisdiction=jurisdiction,
            conversation_history=conversation_history,
        )

        if not retrieved_chunks:
            no_doc_answer = (
                "This specific point is not addressed in the contract you uploaded. "
                "I recommend consulting a qualified legal professional for guidance on this matter."
            )
            yield _sse_event("token", no_doc_answer)
            yield _sse_done(
                answer=no_doc_answer,
                citations=[],
                confidence="NOT_IN_DOCUMENT",
            )
            return

        # Stream Claude's response
        full_answer = ""
        input_tokens = 0
        output_tokens = 0

        async with client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                full_answer += text
                yield _sse_event("token", text)

            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

        citations = _extract_citations(full_answer, retrieved_chunks)
        confidence = _assess_confidence(full_answer, retrieved_chunks)

        logger.info(
            "rag_response_complete",
            contract_id=contract_id,
            duration_seconds=round(time.time() - start_time, 2),
            citations=len(citations),
            confidence=confidence,
            tokens=input_tokens + output_tokens,
        )

        yield _sse_done(
            answer=full_answer,
            citations=[c.model_dump() for c in citations],
            confidence=confidence,
            tokens_used=input_tokens + output_tokens,
        )

    except Exception as e:
        logger.error("rag_chain_error", contract_id=contract_id, error=str(e))
        yield json.dumps({"type": "error", "message": str(e)})


def _sse_event(event_type: str, content: str) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


def _sse_done(
    answer: str,
    citations: list,
    confidence: str,
    tokens_used: Optional[int] = None,
) -> str:
    return f"data: {json.dumps({'type': 'done', 'response': {'answer': answer, 'citations': citations, 'confidence': confidence, 'tokens_used': tokens_used}})}\n\n"


def _extract_citations(answer: str, retrieved_chunks: list[dict]) -> list[Citation]:
    citations: list[Citation] = []
    cited_chunks: set[str] = set()

    referenced_pages: set[int] = set()
    for pattern in [r"[Ss]ection\s+(\d+)", r"[Cc]lause\s+(\d+)", r"[Pp]age\s+(\d+)", r"[Aa]rticle\s+(\d+)"]:
        for match in re.findall(pattern, answer):
            try:
                referenced_pages.add(int(match.split(".")[0]))
            except ValueError:
                pass

    for chunk in retrieved_chunks:
        chunk_id = chunk["chunk_id"]
        if chunk_id in cited_chunks:
            continue
        page_start = chunk["page_range"][0]
        page_end = chunk["page_range"][1]
        chunk_pages = set(range(page_start, page_end + 1))
        if referenced_pages & chunk_pages:
            excerpt = chunk["text"][:200].strip()
            citations.append(Citation(
                chunk_id=chunk_id,
                page_range=(page_start, page_end),
                relevant_excerpt=excerpt + ("..." if len(chunk["text"]) > 200 else ""),
                section_heading=chunk.get("section_heading"),
            ))
            cited_chunks.add(chunk_id)

    if not citations and retrieved_chunks:
        for chunk in retrieved_chunks[:2]:
            chunk_id = chunk["chunk_id"]
            excerpt = chunk["text"][:200].strip()
            citations.append(Citation(
                chunk_id=chunk_id,
                page_range=(chunk["page_range"][0], chunk["page_range"][1]),
                relevant_excerpt=excerpt + ("..." if len(chunk["text"]) > 200 else ""),
                section_heading=chunk.get("section_heading"),
            ))

    return citations[:5]


def _assess_confidence(answer: str, retrieved_chunks: list[dict]) -> str:
    answer_lower = answer.lower()
    not_found_phrases = [
        "not addressed in the contract",
        "not clearly stated",
        "consult a legal professional",
        "not found in",
    ]
    if any(phrase in answer_lower for phrase in not_found_phrases):
        return "NOT_IN_DOCUMENT"

    has_section_ref = bool(re.search(r"[Ss]ection|[Cc]lause|[Pp]age|[Aa]rticle", answer))
    high_score_chunks = [c for c in retrieved_chunks if c.get("score", 0) > 0.8]

    if has_section_ref and len(high_score_chunks) >= 2:
        return "HIGH"
    elif has_section_ref or len(high_score_chunks) >= 1:
        return "MEDIUM"
    return "LOW"


CLAUSE_QUESTIONS: dict[str, str] = {
    "NON_COMPETE": "Can I work for competitors after leaving this role?",
    "IP_ASSIGNMENT": "Do I lose rights to personal projects I build outside work hours?",
    "AUTO_RENEWAL": "When do I need to cancel to avoid auto-renewal charges?",
    "TERMINATION_FOR_CAUSE": "Under what conditions can they terminate me immediately?",
    "TERMINATION_FOR_CONVENIENCE": "How much notice must they give before terminating?",
    "CONFIDENTIALITY": "What specific information am I required to keep confidential?",
    "NON_SOLICITATION": "Can I work with clients I brought to the company after I leave?",
    "LIMITATION_OF_LIABILITY": "What is the maximum amount they can sue me for?",
    "INDEMNIFICATION": "When am I personally responsible for their legal costs?",
    "DATA_PROTECTION": "How will my personal data be used and stored?",
    "GOVERNING_LAW": "Which country's laws govern this contract?",
    "PAYMENT_TERMS": "When and how will I be paid?",
}


def get_suggested_questions(identified_clause_types: list[str]) -> list[str]:
    suggestions = [
        CLAUSE_QUESTIONS[ct]
        for ct in identified_clause_types
        if ct in CLAUSE_QUESTIONS
    ]
    suggestions.append("What are the most important things I should know before signing?")
    return suggestions[:5]
