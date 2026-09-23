"""Tenant billing profile domain model.

`Tenant` in this platform already *is* the client company (its `name` is a
company name, e.g. "Acme Corp") - this is not a separate "Cliente" entity,
just the billing/company data a tenant needs to be invoiced, 1:1 with it.
Pure data capture (legal name, tax id, address, contact, currency, plan/cycle
as free text) - there is no billing engine, payment processor integration or
subscription system behind these fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TenantBillingProfile(BaseModel):
    """Billing/company data for a tenant. Every field but the id/tenant/timestamps
    is optional: a tenant can exist without one yet (nothing to bill until an
    admin fills it in), and any single field can be filled in gradually.

    Attributes:
        id (UUID): Unique identifier.
        tenant_id (UUID): The tenant this profile belongs to (unique - 1:1).
        legal_name (Optional[str]): Registered/legal company name, if it
            differs from the tenant's display name.
        tax_id (Optional[str]): Tax identification number (RFC/NIF/VAT/EIN/...
            - deliberately generic, this platform serves multiple countries).
        billing_email (Optional[str]): Where invoices/receipts are sent.
        billing_contact_name (Optional[str]): Person responsible for billing.
        billing_phone (Optional[str]): Contact phone for billing matters.
        address_line1 (Optional[str]): Street address.
        address_line2 (Optional[str]): Suite/floor/unit, if any.
        city (Optional[str]): City.
        state_province (Optional[str]): State/province/region.
        postal_code (Optional[str]): Postal/ZIP code.
        country (Optional[str]): Country.
        currency (Optional[str]): Billing currency (e.g. "USD", "MXN").
        plan (Optional[str]): Subscription tier, free text (no plans/pricing
            system exists yet - this just records what was agreed).
        billing_cycle (Optional[str]): e.g. "monthly", "annual"; free text.
        notes (Optional[str]): Anything else worth recording about billing.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    tenant_id: UUID
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    billing_email: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    plan: Optional[str] = None
    billing_cycle: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
