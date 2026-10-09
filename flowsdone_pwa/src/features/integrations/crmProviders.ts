import type { CrmProvider } from '@/core/admin/types'

/** One CRM in the catalog: the generic webhook works today, the rest are coming. */
export interface CrmCatalogItem {
  id: CrmProvider | 'zendesk' | 'salesforce' | 'jira_service_management' | 'zoho'
  /** Brand name (not translated). */
  name: string
  available: boolean
}

/** CRMs a project can hand conversations over to, in display order. */
export const CRM_CATALOG: readonly CrmCatalogItem[] = [
  { id: 'generic_webhook', name: 'Webhook', available: true },
  { id: 'zendesk', name: 'Zendesk', available: false },
  { id: 'salesforce', name: 'Salesforce', available: false },
  { id: 'jira_service_management', name: 'Jira Service Management', available: false },
  { id: 'zoho', name: 'Zoho Desk', available: false },
]
