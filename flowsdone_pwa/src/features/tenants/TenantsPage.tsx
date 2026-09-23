import { Building2, Pause, Pencil, Play, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useDeleteProject, useDeleteTenant, useUpdateProject, useUpdateTenant } from '@/core/admin/hooks'
import type { Project, TenantRecord } from '@/core/admin/types'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { useTenant } from '@/core/tenant/useTenant'
import { BillingProfileCard } from './BillingProfileCard'
import { SubscriptionCard } from './SubscriptionCard'
import { UsageCard } from './UsageCard'
import { ProjectDialog } from './ProjectDialog'
import { ProjectsCard } from './ProjectsCard'
import { TenantDialog } from './TenantDialog'
import { TenantList } from './TenantList'
import { summarize, useTenantsView } from './useTenantsView'
import { Trans, useTranslation } from 'react-i18next'

/** Open dialog: new/edited tenant, new/edited project, or none. */
type Dialogs =
  | { kind: 'tenant'; tenant: TenantRecord | null }
  | { kind: 'project'; project: Project | null }
  | null

/** Confirmation pending for a destructive or disruptive action. */
type Pending =
  | { kind: 'delete-tenant'; tenant: TenantRecord }
  | { kind: 'suspend-tenant'; tenant: TenantRecord }
  | { kind: 'delete-project'; project: Project }
  | { kind: 'suspend-project'; project: Project }
  | null

/**
 * Tenants and their projects, in a single screen: the list on the left and
 * the detail (status, actions and projects) on the right.
 *
 * - Admin: creates, edits, suspends and deletes tenants, and manages their projects.
 * - Manager: only sees their own tenants and manages their projects.
 * - Suspending cuts off channel routing without deleting anything; deleting
 *   cascades (projects, agents and channels) and requires typing the slug.
 */
export function TenantsPage() {
  const { t } = useTranslation()
  const view = useTenantsView()
  const { user } = useAuth()
  const { current } = useTenant()
  const canManageTenants = can(user, 'tenants:manage')
  // admin + tenant_manager (POLICY["tenant_billing"] en el gateway); botmaster
  // gestiona agentes/canales, no facturación.
  const canManageBilling = can(user, 'projects:manage')
  const updateTenant = useUpdateTenant()
  const deleteTenant = useDeleteTenant()
  const updateProject = useUpdateProject()
  const deleteProject = useDeleteProject()
  const [dialog, setDialog] = useState<Dialogs>(null)
  const [pending, setPending] = useState<Pending>(null)
  const [choice, setChoice] = useState<string | null>(null)

  // Selección derivada: la elegida si sigue existiendo; si no, el tenant activo del
  // selector superior; si no, el primero.
  const selected =
    view.entries.find((e) => e.tenant.id === choice) ?? view.entries.find((e) => e.tenant.id === current?.id) ?? view.entries[0]

  async function run(action: () => Promise<unknown>, done?: () => void) {
    try {
      await action()
      setPending(null)
      done?.()
    } catch {
      // El error queda en la mutación correspondiente y se muestra en el diálogo.
    }
  }

  /** Opens a deletion confirmation with freshly fetched counts (never the cached ones). */
  async function confirmDeletion(next: NonNullable<Pending>) {
    await view.refreshContents().catch(() => {})
    setPending(next)
  }

  const toggleTenant = (tenant: TenantRecord) => {
    if (tenant.status === 'active') {
      updateTenant.reset()
      setPending({ kind: 'suspend-tenant', tenant })
    } else {
      void updateTenant.mutateAsync({ id: tenant.id, patch: { status: 'active' } }).catch(() => {})
    }
  }
  const toggleProject = (project: Project) => {
    if (project.status === 'active') {
      updateProject.reset()
      setPending({ kind: 'suspend-project', project })
    } else {
      void updateProject.mutateAsync({ id: project.id, patch: { status: 'active' } }).catch(() => {})
    }
  }

  const header = (
    <PageHeader
      title={t('nav.tenants')}
      description={canManageTenants ? t('tenants.descriptionAll') : t('tenants.descriptionOwn')}
      actions={
        canManageTenants && (
          <Button onClick={() => setDialog({ kind: 'tenant', tenant: null })} disabled={view.isLoading}>
            <Plus className="size-4" aria-hidden="true" />
            {t('tenants.new')}
          </Button>
        )
      }
    />
  )

  if (view.isLoading) {
    return (
      <>
        {header}
        <Spinner label={t('tenants.loading')} className="py-20" />
      </>
    )
  }
  if (view.error) {
    return (
      <>
        {header}
        <Alert tone="danger">
          <p>{t('tenants.loadError', { error: describeError(view.error) })}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={view.refetch}>
            {t('common.retry')}
          </Button>
        </Alert>
      </>
    )
  }
  if (!selected) {
    return (
      <>
        {header}
        <EmptyState
          icon={Building2}
          title={t('tenants.empty.title')}
          description={canManageTenants ? t('tenants.empty.descriptionAdmin') : t('tenants.empty.descriptionOther')}
        />
        {dialog?.kind === 'tenant' && <TenantDialog tenant={dialog.tenant} onClose={() => setDialog(null)} onSaved={(t) => setChoice(t.id)} />}
      </>
    )
  }

  const { tenant } = selected
  const suspended = tenant.status !== 'active'

  return (
    <>
      {header}
      <div className="grid gap-6 lg:grid-cols-[minmax(18rem,22rem)_1fr]">
        <TenantList entries={view.entries} selectedId={tenant.id} onSelect={setChoice} />

        <div className="min-w-0 space-y-6">
          <Card className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="flex items-center gap-2 text-xl font-semibold">
                  <span className="truncate">{tenant.name}</span>
                  <Badge tone={suspended ? 'warning' : 'success'}>{suspended ? t('common.suspended') : t('common.active')}</Badge>
                </h2>
                <p className="mt-0.5 font-mono text-xs text-muted">{tenant.slug}</p>
                <p className="mt-2 text-sm text-muted">
                  {summarize({ projects: selected.projects.length, agents: selected.agents, channels: selected.channels })} ·{' '}
                  {t('tenants.createdOn', { date: new Date(tenant.created_at).toLocaleDateString(currentLocale()) })}
                </p>
              </div>
              {canManageTenants && (
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: 'tenant', tenant })} aria-label={t('common.editItem', { name: tenant.name })}>
                    <Pencil className="size-4" aria-hidden="true" />
                    {t('common.edit')}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => toggleTenant(tenant)} aria-label={t(suspended ? 'common.reactivateItem' : 'common.suspendItem', { name: tenant.name })}>
                    {suspended ? <Play className="size-4" aria-hidden="true" /> : <Pause className="size-4" aria-hidden="true" />}
                    {suspended ? t('common.reactivate') : t('common.suspend')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      deleteTenant.reset()
                      void confirmDeletion({ kind: 'delete-tenant', tenant })
                    }}
                    aria-label={t('common.deleteItem', { name: tenant.name })}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    {t('common.delete')}
                  </Button>
                </div>
              )}
            </div>
            {suspended && (
              <Alert tone="info" className="mt-4">
                <Trans i18nKey="tenants.suspendedNotice" components={{ strong: <strong /> }} />
              </Alert>
            )}
            {(updateTenant.error || updateProject.error) && !pending && (
              <Alert tone="danger" className="mt-4">
                {describeError(updateTenant.error ?? updateProject.error)}
              </Alert>
            )}
          </Card>

          <ProjectsCard
            projects={selected.projects}
            counts={view.projectCounts}
            onCreate={() => setDialog({ kind: 'project', project: null })}
            onEdit={(project) => setDialog({ kind: 'project', project })}
            onToggleStatus={toggleProject}
            onDelete={(project) => {
              deleteProject.reset()
              void confirmDeletion({ kind: 'delete-project', project })
            }}
          />

          {canManageBilling && (
            <>
              {/* Asignar/cambiar el plan: solo admin (POLICY["billing"] write en el gateway). */}
              <SubscriptionCard tenantId={tenant.id} tenantName={tenant.name} canEdit={can(user, 'platform:manage')} />
              <UsageCard tenantId={tenant.id} />
              <BillingProfileCard tenantId={tenant.id} tenantName={tenant.name} />
            </>
          )}
        </div>
      </div>

      {dialog?.kind === 'tenant' && <TenantDialog tenant={dialog.tenant} onClose={() => setDialog(null)} onSaved={(t) => setChoice(t.id)} />}
      {dialog?.kind === 'project' && <ProjectDialog tenant={tenant} project={dialog.project} onClose={() => setDialog(null)} />}

      <ConfirmDialog
        open={pending?.kind === 'delete-tenant'}
        title={pending?.kind === 'delete-tenant' ? t('common.deleteItem', { name: pending.tenant.name }) : ''}
        description={t('tenants.delete.description')}
        confirmLabel={t('tenants.delete.confirm')}
        requireText={pending?.kind === 'delete-tenant' ? pending.tenant.slug : undefined}
        pending={deleteTenant.isPending}
        error={deleteTenant.error ? describeError(deleteTenant.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'delete-tenant' && void run(() => deleteTenant.mutateAsync(pending.tenant.id), () => setChoice(null))}
      >
        <Alert tone="danger">
          <Trans
            i18nKey="tenants.delete.cascade"
            values={{ summary: summarize({ projects: selected.projects.length, agents: selected.agents, channels: selected.channels }) }}
            components={{ strong: <strong /> }}
          />
        </Alert>
      </ConfirmDialog>

      <ConfirmDialog
        open={pending?.kind === 'suspend-tenant'}
        title={pending?.kind === 'suspend-tenant' ? t('common.suspendItem', { name: pending.tenant.name }) : ''}
        description={t('tenants.suspend.description')}
        confirmLabel={t('tenants.suspend.confirm')}
        pending={updateTenant.isPending}
        error={updateTenant.error ? describeError(updateTenant.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'suspend-tenant' && void run(() => updateTenant.mutateAsync({ id: pending.tenant.id, patch: { status: 'suspended' } }))}
      />

      <ConfirmDialog
        open={pending?.kind === 'delete-project'}
        title={pending?.kind === 'delete-project' ? t('common.deleteItem', { name: pending.project.name }) : ''}
        description={t('tenants.projects.delete.description')}
        confirmLabel={t('tenants.projects.delete.confirm')}
        requireText={
          pending?.kind === 'delete-project' && (view.projectCounts.get(pending.project.id)?.agents || view.projectCounts.get(pending.project.id)?.channels)
            ? pending.project.slug
            : undefined
        }
        pending={deleteProject.isPending}
        error={deleteProject.error ? describeError(deleteProject.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'delete-project' && void run(() => deleteProject.mutateAsync(pending.project.id))}
      >
        {pending?.kind === 'delete-project' && (() => {
          const c = view.projectCounts.get(pending.project.id) ?? { agents: 0, channels: 0 }
          return c.agents || c.channels ? (
            <Alert tone="danger">
              <Trans i18nKey="tenants.projects.delete.cascade" values={{ summary: summarize(c) }} components={{ strong: <strong /> }} />
            </Alert>
          ) : null
        })()}
      </ConfirmDialog>

      <ConfirmDialog
        open={pending?.kind === 'suspend-project'}
        title={pending?.kind === 'suspend-project' ? t('common.suspendItem', { name: pending.project.name }) : ''}
        description={t('tenants.projects.suspend.description')}
        confirmLabel={t('tenants.projects.suspend.confirm')}
        pending={updateProject.isPending}
        error={updateProject.error ? describeError(updateProject.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'suspend-project' && void run(() => updateProject.mutateAsync({ id: pending.project.id, patch: { status: 'suspended' } }))}
      />
    </>
  )
}
