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
import { useTenant } from '@/core/tenant/useTenant'
import { ProjectDialog } from './ProjectDialog'
import { ProjectsCard } from './ProjectsCard'
import { TenantDialog } from './TenantDialog'
import { TenantList } from './TenantList'
import { summarize, useTenantsView } from './useTenantsView'

/** Diálogo abierto: tenant nuevo/editado, proyecto nuevo/editado, o ninguno. */
type Dialogs =
  | { kind: 'tenant'; tenant: TenantRecord | null }
  | { kind: 'project'; project: Project | null }
  | null

/** Confirmación pendiente de una acción destructiva o disruptiva. */
type Pending =
  | { kind: 'delete-tenant'; tenant: TenantRecord }
  | { kind: 'suspend-tenant'; tenant: TenantRecord }
  | { kind: 'delete-project'; project: Project }
  | { kind: 'suspend-project'; project: Project }
  | null

/**
 * Tenants y sus proyectos, en una sola pantalla: la lista a la izquierda y el
 * detalle (estado, acciones y proyectos) a la derecha.
 *
 * - Admin: crea, edita, suspende y borra tenants, y gestiona sus proyectos.
 * - Gestor: solo ve sus tenants y gestiona sus proyectos.
 * - Suspender corta el enrutado de los canales sin borrar nada; borrar es en
 *   cascada (proyectos, agentes y canales) y pide escribir el slug.
 */
export function TenantsPage() {
  const view = useTenantsView()
  const { user } = useAuth()
  const { current } = useTenant()
  const canManageTenants = can(user, 'tenants:manage')
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

  /** Abre una confirmación de borrado con los recuentos recién pedidos (nunca los de la caché). */
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
      title="Tenants"
      description={canManageTenants ? 'Organizaciones clientes y sus proyectos.' : 'Tus organizaciones y sus proyectos.'}
      actions={
        canManageTenants && (
          <Button onClick={() => setDialog({ kind: 'tenant', tenant: null })} disabled={view.isLoading}>
            <Plus className="size-4" aria-hidden="true" />
            Nuevo tenant
          </Button>
        )
      }
    />
  )

  if (view.isLoading) {
    return (
      <>
        {header}
        <Spinner label="Cargando tenants" className="py-20" />
      </>
    )
  }
  if (view.error) {
    return (
      <>
        {header}
        <Alert tone="danger">
          <p>No se pudieron cargar los tenants: {describeError(view.error)}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={view.refetch}>
            Reintentar
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
          title="Aún no hay tenants"
          description={canManageTenants ? 'Crea el primero para empezar a dar de alta proyectos y canales.' : 'Todavía no tienes tenants asignados. Pídeselo a un administrador.'}
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
                  <Badge tone={suspended ? 'warning' : 'success'}>{suspended ? 'Suspendido' : 'Activo'}</Badge>
                </h2>
                <p className="mt-0.5 font-mono text-xs text-muted">{tenant.slug}</p>
                <p className="mt-2 text-sm text-muted">
                  {summarize({ projects: selected.projects.length, agents: selected.agents, channels: selected.channels })} · creado el{' '}
                  {new Date(tenant.created_at).toLocaleDateString('es')}
                </p>
              </div>
              {canManageTenants && (
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setDialog({ kind: 'tenant', tenant })} aria-label={`Editar ${tenant.name}`}>
                    <Pencil className="size-4" aria-hidden="true" />
                    Editar
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => toggleTenant(tenant)} aria-label={`${suspended ? 'Reactivar' : 'Suspender'} ${tenant.name}`}>
                    {suspended ? <Play className="size-4" aria-hidden="true" /> : <Pause className="size-4" aria-hidden="true" />}
                    {suspended ? 'Reactivar' : 'Suspender'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      deleteTenant.reset()
                      void confirmDeletion({ kind: 'delete-tenant', tenant })
                    }}
                    aria-label={`Eliminar ${tenant.name}`}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    Eliminar
                  </Button>
                </div>
              )}
            </div>
            {suspended && (
              <Alert tone="info" className="mt-4">
                Este tenant está suspendido: <strong>sus canales no responden mensajes</strong>. Los datos se conservan y puedes
                reactivarlo cuando quieras.
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
        </div>
      </div>

      {dialog?.kind === 'tenant' && <TenantDialog tenant={dialog.tenant} onClose={() => setDialog(null)} onSaved={(t) => setChoice(t.id)} />}
      {dialog?.kind === 'project' && <ProjectDialog tenant={tenant} project={dialog.project} onClose={() => setDialog(null)} />}

      <ConfirmDialog
        open={pending?.kind === 'delete-tenant'}
        title={pending?.kind === 'delete-tenant' ? `Eliminar ${pending.tenant.name}` : ''}
        description="Se elimina el tenant y TODO lo que contiene."
        confirmLabel="Eliminar tenant"
        requireText={pending?.kind === 'delete-tenant' ? pending.tenant.slug : undefined}
        pending={deleteTenant.isPending}
        error={deleteTenant.error ? describeError(deleteTenant.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'delete-tenant' && void run(() => deleteTenant.mutateAsync(pending.tenant.id), () => setChoice(null))}
      >
        <Alert tone="danger">
          Se borrarán en cascada <strong>{summarize({ projects: selected.projects.length, agents: selected.agents, channels: selected.channels })}</strong>.
          Los canales dejarán de responder de inmediato. Si solo quieres pausarlo, usa <strong>Suspender</strong>.
        </Alert>
      </ConfirmDialog>

      <ConfirmDialog
        open={pending?.kind === 'suspend-tenant'}
        title={pending?.kind === 'suspend-tenant' ? `Suspender ${pending.tenant.name}` : ''}
        description="Los canales de este tenant dejarán de responder mensajes. No se borra nada y puedes reactivarlo."
        confirmLabel="Suspender tenant"
        pending={updateTenant.isPending}
        error={updateTenant.error ? describeError(updateTenant.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'suspend-tenant' && void run(() => updateTenant.mutateAsync({ id: pending.tenant.id, patch: { status: 'suspended' } }))}
      />

      <ConfirmDialog
        open={pending?.kind === 'delete-project'}
        title={pending?.kind === 'delete-project' ? `Eliminar ${pending.project.name}` : ''}
        description="Se elimina el proyecto y lo que contiene."
        confirmLabel="Eliminar proyecto"
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
              Se borrarán en cascada <strong>{summarize(c)}</strong>. Los canales dejarán de responder.
            </Alert>
          ) : null
        })()}
      </ConfirmDialog>

      <ConfirmDialog
        open={pending?.kind === 'suspend-project'}
        title={pending?.kind === 'suspend-project' ? `Suspender ${pending.project.name}` : ''}
        description="Los canales de este proyecto dejarán de responder mensajes. No se borra nada y puedes reactivarlo."
        confirmLabel="Suspender proyecto"
        pending={updateProject.isPending}
        error={updateProject.error ? describeError(updateProject.error) : null}
        onCancel={() => setPending(null)}
        onConfirm={() => pending?.kind === 'suspend-project' && void run(() => updateProject.mutateAsync({ id: pending.project.id, patch: { status: 'suspended' } }))}
      />
    </>
  )
}
