"""
Chat Router
============
POST /api/v1/chat/{contract_id}

Streams Claude's grounded answer as Server-Sent Events.
Each token is sent immediately as it's generated.
Final event contains the complete ChatResponse with citations.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models.contract import ChatMessage, Contract
from routers.deps import get_current_user_id
from schemas.chat import ChatRequest
from services.rag_chain import get_suggested_questions, stream_chat_response

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/{contract_id}")
async def chat_with_contract(
    contract_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """
    POST /api/v1/chat/{contract_id}

    Body: { message: str, conversation_history: [{role, content}] }
    Response: Server-Sent Events stream

    SSE events:
    - {"type": "token", "content": "..."} — streaming tokens
    - {"type": "done", "response": {ChatResponse}} — final answer + citations
    - {"type": "error", "message": "..."} — error occurred
    """
    # Validate contract exists and belongs to user
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == user_id,
        )
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    if contract.status != "COMPLETE":
        raise HTTPException(
            status_code=409,
            detail=f"Contract analysis is not yet complete (status: {contract.status}). Please wait.",
        )

    if not contract.pinecone_namespace:
        raise HTTPException(
            status_code=500,
            detail="Contract embeddings not found. The analysis may need to be re-run.",
        )

    # Persist user message to DB for history
    user_msg = ChatMessage(
        contract_id=contract_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    # Session commits at end of request via dependency

    jurisdiction = "Unknown"
    if contract.full_analysis and "contract_type" in contract.full_analysis:
        jurisdiction = (
            contract.full_analysis["contract_type"].get("jurisdiction_hint") or "Unknown"
        )

    history_dicts = [
        {"role": turn.role, "content": turn.content}
        for turn in body.conversation_history
    ]

    async def generate():
        """Async generator that yields SSE events."""
        async for event in stream_chat_response(
            question=body.message,
            contract_id=contract_id,
            pinecone_namespace=contract.pinecone_namespace,
            contract_type=contract.contract_type or "UNKNOWN",
            jurisdiction=jurisdiction,
            conversation_history=history_dicts,
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering for SSE
            "Connection": "keep-alive",
        },
    )


@router.get("/{contract_id}/suggested-questions")
async def get_suggested_questions_endpoint(
    contract_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    GET /api/v1/chat/{contract_id}/suggested-questions

    Returns pre-populated questions based on found clause types.
    Used to populate the chat UI suggestion chips.
    """
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == user_id,
        )
    )
    contract = result.scalar_one_or_none()

    if not contract or not contract.full_analysis:
        return {"questions": []}

    clause_types = [
        c["clause_type"]
        for c in contract.full_analysis.get("extracted_clauses", [])
    ]
    questions = get_suggested_questions(clause_types)
    return {"questions": questions}


@router.get("/{contract_id}/history")
async def get_chat_history(
    contract_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    GET /api/v1/chat/{contract_id}/history

    Returns persisted chat history for this contract.
    Used to restore conversation on page refresh.
    """
    # Verify ownership
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    msgs_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.contract_id == contract_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(100)
    )
    messages = msgs_result.scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    }
