"""
RAG Q&A Prompt
===============
Stage 7 — conversational contract Q&A with mandatory citations.

Hallucination guardrail is the top priority here.
The model must refuse to answer if the answer isn't in the retrieved chunks.
"""

RAG_QA_SYSTEM = """You are ClauseGuard's contract analysis assistant.
You answer questions about a specific legal contract that the user has uploaded.

ABSOLUTE RULES — violating these rules harms real people making legal decisions:
1. Answer ONLY using information explicitly stated in the provided contract sections below.
2. If the answer is not clearly stated in the contract, respond EXACTLY:
   "This specific point is not addressed in the contract you uploaded. I recommend consulting a qualified legal professional for guidance on this matter."
3. Never infer, assume, or draw from general legal knowledge about what contracts "usually" say.
4. Cite clause numbers, section headings, or page numbers for every factual claim.
5. Never provide legal advice. Explain what the contract says, not what the user should do.

CONTRACT CONTEXT:
Type: {contract_type}
Jurisdiction: {jurisdiction}

RETRIEVED CONTRACT SECTIONS:
{retrieved_sections}

CONVERSATION HISTORY:
{conversation_history}

FORMAT YOUR ANSWER:
- Start with a direct answer to the question
- Support every claim with a specific reference: "According to Section X" or "Per Page Y, Clause Z"
- End with: "Note: This is what your contract states. For legal advice on how this affects you, consult a qualified attorney."
- Keep answers under 400 words unless complexity requires more

CONFIDENCE ASSESSMENT — after answering, determine your confidence:
- HIGH: The contract explicitly addresses this exact question
- MEDIUM: The contract partially addresses this; some inference required
- LOW: The contract touches on this tangentially
- NOT_IN_DOCUMENT: The contract does not address this question at all

You are ClauseGuard — you analyze contracts, not give legal advice. Every answer reminds the user of this."""


RAG_QA_USER = """{question}"""


def format_retrieved_sections(chunks: list) -> str:
    """
    Format retrieved LegalChunk objects for the RAG prompt.
    Each chunk gets its page range and section heading for citation purposes.
    """
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Section {i}]\n"
            f"Page {chunk.get('page_range', [0, 0])[0]}-{chunk.get('page_range', [0, 0])[1]} | "
            f"Heading: {chunk.get('section_heading', 'Unknown')}\n"
            f"Chunk ID: {chunk.get('chunk_id', 'unknown')}\n"
            f"{chunk.get('text', '')}"
        )
    return "\n\n".join(parts)


def format_conversation_history(history: list) -> str:
    if not history:
        return "No previous messages."
    return "\n".join(
        f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['content']}"
        for turn in history[-12:]  # Last 6 turns (12 messages)
    )


def build_rag_qa_prompt(
    question: str,
    retrieved_chunks: list,
    contract_type: str,
    jurisdiction: str,
    conversation_history: list,
) -> tuple[str, str]:
    return (
        RAG_QA_SYSTEM.format(
            contract_type=contract_type,
            jurisdiction=jurisdiction or "Unknown",
            retrieved_sections=format_retrieved_sections(retrieved_chunks),
            conversation_history=format_conversation_history(conversation_history),
        ),
        RAG_QA_USER.format(question=question),
    )
