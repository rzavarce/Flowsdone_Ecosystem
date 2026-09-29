"""Admin endpoints for the conversation inbox: list conversations of the
caller's tenants and open one with its transcript and usage, and edit the
card (name, email, phone, notes) of the person behind a conversation.

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
    ContactCardIn,
    ContactCardOut,
    ConversationDetailOut,
    ConversationMessageOut,
    ConversationOut,
    UsageLineOut,
)
from app.application.use_cases.conversation_contacts import InvalidContactError
from app.domain.models.conversation import Conversation
from app.domain.models.conversation_contact import Contact
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
    cards = await request.app.state.conversation_contacts_use_case.for_conversations(conversations)
    return [_conversation_out(c, cards.get(c.id)) for c in conversations]


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
    cards = await request.app.state.conversation_contacts_use_case.for_conversations([detail.conversation])
    card = cards.get(detail.conversation.id)
    return ConversationDetailOut(
        conversation=_conversation_out(detail.conversation, card),
        contact_card=_card_out(card),
        messages=[ConversationMessageOut(**m.model_dump()) for m in detail.messages],
        usage=usage_lines(detail.usage, with_costs=with_costs),
        cost_micros=detail.cost_micros if with_costs else None,
        llm_input_tokens=detail.llm_input_tokens,
        llm_output_tokens=detail.llm_output_tokens,
        llm_cached_input_tokens=detail.llm_cached_input_tokens,
    )


def _conversation_out(conversation: Conversation, card: Optional[Contact]) -> ConversationOut:
    """Shape a conversation, with its contact's name if it has a card.

    Args:
        conversation (Conversation): The conversation.
        card (Optional[Contact]): Its contact's card.

    Returns:
        ConversationOut: The response item.
    """
    return ConversationOut(**conversation.model_dump(), contact_name=card.name if card else None)


def _card_out(card: Optional[Contact]) -> Optional[ContactCardOut]:
    """Shape a contact card.

    Args:
        card (Optional[Contact]): The card.

    Returns:
        Optional[ContactCardOut]: The response, or None without a card.
    """
    if card is None:
        return None
    return ContactCardOut(name=card.name, email=card.email, phone=card.phone, notes=card.notes, updated_at=card.updated_at)


async def _scoped_conversation(request: Request, access: AdminAccess, conversation_id: UUID) -> Conversation:
    """Load a conversation inside the caller's tenants.

    Args:
        request (Request): Used to reach `request.app.state.conversation_repo`.
        access (AdminAccess): The authenticated caller.
        conversation_id (UUID): The conversation.

    Returns:
        Conversation: The conversation.

    Raises:
        HTTPException: 404 if it does not exist or is out of scope.
    """
    conversation = await request.app.state.conversation_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    access.tenant(conversation.tenant_id, resource="conversation")
    return conversation


@router.patch("/{conversation_id}/contact", response_model=ContactCardOut)
async def update_contact(
    conversation_id: UUID,
    body: ContactCardIn,
    request: Request,
    access: AdminAccess = Depends(admin_access("contacts", "write")),
) -> ContactCardOut:
    """Edit the card of the person behind a conversation.

    The card is shared by every conversation with the same person (same
    tenant, channel and identifier). Fields left out are not touched; an
    empty one is cleared.

    Args:
        conversation_id (UUID): Any conversation with that person.
        body (ContactCardIn): Fields to set.
        request (Request): Used to reach `request.app.state.conversation_contacts_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ContactCardOut: The card as stored.

    Raises:
        HTTPException: 404 if the conversation does not exist or is out of
            scope; 422 on an invalid value (e.g. a malformed email).
    """
    conversation = await _scoped_conversation(request, access, conversation_id)
    try:
        card = await request.app.state.conversation_contacts_use_case.update(
            conversation, body.model_dump(exclude_unset=True)
        )
    except InvalidContactError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _card_out(card)  # type: ignore[return-value]


@router.post("/{conversation_id}/contact/capture", response_model=Optional[ContactCardOut])
async def capture_contact(
    conversation_id: UUID,
    body: ContactCardIn,
    request: Request,
    access: AdminAccess = Depends(admin_access("contacts", "write")),
) -> Optional[ContactCardOut]:
    """What an agent learned about the person it is talking to.

    Called from Langflow (the "Guardar contacto" component) with the
    conversation it runs in. Unlike PATCH it only fills fields that are
    still empty, so what staff typed is never replaced, and empty values
    are ignored.

    Args:
        conversation_id (UUID): The conversation the agent is in.
        body (ContactCardIn): What it learned.
        request (Request): Used to reach `request.app.state.conversation_contacts_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        Optional[ContactCardOut]: The card as stored.

    Raises:
        HTTPException: 404 if the conversation does not exist or is out of
            scope; 422 on an invalid value.
    """
    await _scoped_conversation(request, access, conversation_id)
    try:
        card = await request.app.state.conversation_contacts_use_case.capture(
            conversation_id, body.model_dump(exclude_unset=True)
        )
    except InvalidContactError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _card_out(card)
