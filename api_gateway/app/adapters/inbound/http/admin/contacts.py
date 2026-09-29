"""Admin endpoints for the contact list: search the people behind the
conversations of the caller's tenants, open one with their latest
conversations, and edit their card.

Cards are started by the gateway with each contact's first message (see
ManageConversationContactsUseCase.record_from_channel); these endpoints
only read and edit them.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.billing_schemas import (
    ContactCardIn,
    ContactDetailOut,
    ContactOut,
    ConversationOut,
)
from app.application.use_cases.conversation_contacts import InvalidContactError
from app.domain.models.conversation_contact import Contact, ContactSummary

router = APIRouter(prefix="/contacts", tags=["admin:contacts"])

# Conversations shown with a contact: the latest ones; the inbox has them all.
RECENT_CONVERSATIONS = 5


def _contact_out(summary: ContactSummary) -> ContactOut:
    """Shape a contact for the list.

    Args:
        summary (ContactSummary): The contact and its activity.

    Returns:
        ContactOut: The response item.
    """
    return ContactOut(
        **summary.contact.model_dump(),
        last_message_at=summary.last_message_at,
        conversation_count=summary.conversation_count,
    )


async def _scoped_contact(request: Request, access: AdminAccess, contact_id: UUID) -> Contact:
    """Load a contact inside the caller's tenants.

    Args:
        request (Request): Used to reach the contacts use case.
        access (AdminAccess): The authenticated caller.
        contact_id (UUID): The contact.

    Returns:
        Contact: The contact.

    Raises:
        HTTPException: 404 if it does not exist or is out of scope.
    """
    contact = await request.app.state.conversation_contacts_use_case.get(contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="contact not found")
    access.tenant(contact.tenant_id, resource="contact")
    return contact


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    request: Request,
    tenant_id: Optional[UUID] = None,
    q: Optional[str] = Query(default=None, max_length=100),
    channel_type: Optional[str] = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    access: AdminAccess = Depends(admin_access("contacts", "read")),
) -> list[ContactOut]:
    """Contacts of the caller's tenants, most recent activity first.

    Args:
        request (Request): Used to reach the contacts use case.
        tenant_id (Optional[UUID]): Only this tenant (404 if out of scope).
        q (Optional[str]): Name, email, phone, @user or identifier contains this.
        channel_type (Optional[str]): Only this channel.
        limit (int): Page size (1-100).
        offset (int): Items to skip ("load more").
        access (AdminAccess): The authenticated caller.

    Returns:
        list[ContactOut]: The page.
    """
    if tenant_id is not None:
        access.tenant(tenant_id)
        tenant_ids = [tenant_id]
    else:
        tenant_ids = None if access.unrestricted else list(access.principal.tenant_ids or [])
    found = await request.app.state.conversation_contacts_use_case.search(
        tenant_ids=tenant_ids, query=q, channel_type=channel_type, limit=limit, offset=offset
    )
    return [_contact_out(s) for s in found]


@router.get("/{contact_id}", response_model=ContactDetailOut)
async def get_contact(
    contact_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("contacts", "read")),
) -> ContactDetailOut:
    """One contact with their latest conversations.

    Args:
        contact_id (UUID): Contact id.
        request (Request): Used to reach the use case and conversations.
        access (AdminAccess): The authenticated caller.

    Returns:
        ContactDetailOut: The contact and up to RECENT_CONVERSATIONS of
        their conversations, newest first.

    Raises:
        HTTPException: 404 if it does not exist or is out of scope.
    """
    contact = await _scoped_contact(request, access, contact_id)
    conversations = await request.app.state.conversation_repo.list(
        tenant_ids=[contact.tenant_id],
        channel_type=contact.channel_type,
        contact_identifier=contact.identifier,
        limit=RECENT_CONVERSATIONS,
    )
    # The totals come from the list query (the conversations above are only the latest).
    matches = await request.app.state.conversation_contacts_use_case.search(
        tenant_ids=[contact.tenant_id], query=contact.identifier, channel_type=contact.channel_type, limit=100
    )
    summary = next((s for s in matches if s.contact.id == contact.id), ContactSummary(contact=contact))
    return ContactDetailOut(
        contact=_contact_out(summary),
        conversations=[ConversationOut(**c.model_dump(), contact_name=contact.name) for c in conversations],
    )


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: UUID,
    body: ContactCardIn,
    request: Request,
    access: AdminAccess = Depends(admin_access("contacts", "write")),
) -> ContactOut:
    """Edit a contact's card; fields left out are not touched, an empty one is cleared.

    Args:
        contact_id (UUID): Contact id.
        body (ContactCardIn): Fields to change.
        request (Request): Used to reach the contacts use case.
        access (AdminAccess): The authenticated caller.

    Returns:
        ContactOut: The contact as stored.

    Raises:
        HTTPException: 404 if it does not exist or is out of scope; 422 on
            an invalid value.
    """
    contact = await _scoped_contact(request, access, contact_id)
    try:
        updated = await request.app.state.conversation_contacts_use_case.update_contact(
            contact, body.model_dump(exclude_unset=True)
        )
    except InvalidContactError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _contact_out(ContactSummary(contact=updated))
