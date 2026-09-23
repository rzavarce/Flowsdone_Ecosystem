"""Admin endpoints for the conversation inbox: list conversations of the
caller's tenants and open one with its transcript and usage.

Costs are Flowsdone's own figures: only unrestricted callers (admin, API
key) see them; everyone else gets quantities only.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.billing_schemas import (
    ConversationDetailOut,
    ConversationMessageOut,
    ConversationOut,
    UsageLineOut,
)
from app.domain.models.usage import RatedUsage

router = APIRouter(prefix="/conversations", tags=["admin:conversations"])


def usage_lines(rated: List[RatedUsage], *, with_costs: bool) -> List[UsageLineOut]:
    """Sum rated daily usage per meter for display.

    Args:
        rated (List[RatedUsage]): Rated daily aggregates.
        with_costs (bool): Include costs (admin) or null them.

    Returns:
        List[UsageLineOut]: One line per meter.
    """
    lines: dict = {}
    for item in rated:
        u = item.usage
        key = (u.kind, u.provider, u.sku, u.unit, u.channel_type)
        line = lines.setdefault(
            key,
            UsageLineOut(
                kind=u.kind, provider=u.provider, sku=u.sku, unit=u.unit, channel_type=u.channel_type,
                quantity=0, cost_micros=0 if with_costs else None, rated=True,
            ),
        )
        line.quantity += u.quantity
        line.rated = line.rated and not item.missing_rate
        if with_costs:
            line.cost_micros += item.cost_micros
    return [lines[k] for k in sorted(lines)]


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    request: Request,
    tenant_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    channel_type: Optional[str] = None,
    status: Optional[str] = Query(default=None, pattern="^(open|closed)$"),
    contact: Optional[str] = Query(default=None, max_length=100),
    before: Optional[datetime] = None,
    limit: int = Query(default=50, ge=1, le=200),
    access: AdminAccess = Depends(admin_access("conversations", "read")),
) -> list[ConversationOut]:
    """Conversations of the caller's tenants, most recent activity first.

    Args:
        request (Request): Used to reach `request.app.state.conversation_repo`.
        tenant_id (Optional[UUID]): Only this tenant (404 if out of scope).
        project_id (Optional[UUID]): Only this project (404 if out of scope).
        channel_type (Optional[str]): Only this channel.
        status (Optional[str]): "open" or "closed".
        contact (Optional[str]): Contact contains this text.
        before (Optional[datetime]): Pagination cursor (last_message_at of
            the last item of the previous page).
        limit (int): Page size (1-200).
        access (AdminAccess): The authenticated caller.

    Returns:
        list[ConversationOut]: The page.
    """
    if tenant_id is not None:
        access.tenant(tenant_id)
        tenant_ids = [tenant_id]
    else:
        tenant_ids = None if access.unrestricted else list(access.principal.tenant_ids or [])
    if project_id is not None:
        await access.project(project_id)
    conversations = await request.app.state.conversation_repo.list(
        tenant_ids=tenant_ids,
        project_id=project_id,
        channel_type=channel_type,
        status=status,
        contact=contact,
        before=before,
        limit=limit,
    )
    return [ConversationOut(**c.model_dump()) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("conversations", "read")),
) -> ConversationDetailOut:
    """One conversation with its transcript and usage.

    Args:
        conversation_id (UUID): Conversation id.
        request (Request): Used to reach the detail use case.
        access (AdminAccess): The authenticated caller.

    Returns:
        ConversationDetailOut: The detail (costs only for admins).

    Raises:
        HTTPException: 404 if it does not exist or is out of scope.
    """
    detail = await request.app.state.get_conversation_detail_use_case.execute(conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    access.tenant(detail.conversation.tenant_id, resource="conversation")
    with_costs = access.unrestricted
    return ConversationDetailOut(
        conversation=ConversationOut(**detail.conversation.model_dump()),
        messages=[ConversationMessageOut(**m.model_dump()) for m in detail.messages],
        usage=usage_lines(detail.usage, with_costs=with_costs),
        cost_micros=detail.cost_micros if with_costs else None,
        llm_input_tokens=detail.llm_input_tokens,
        llm_output_tokens=detail.llm_output_tokens,
        llm_cached_input_tokens=detail.llm_cached_input_tokens,
    )
