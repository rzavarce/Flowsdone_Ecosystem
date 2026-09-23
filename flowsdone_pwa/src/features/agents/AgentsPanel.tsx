import { Bot, Pause, Pencil, Play, Plus, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Spinner } from '@/components/ui/Spinner'
import { useAgents, useDeleteAgent, useProjectFlows, useProjects, useUpdateAgent } from '@/core/admin/hooks'
import type { Agent, Project } from '@/core/admin/types'
import { ApiError } from '@/core/http/apiFetch'
import { describeError } from '@/core/http/describeError'
import { AgentDialog } from './AgentDialog'
import { useTranslation } from 'react-i18next'

/** Pending confirmation: delete or suspend an agent. */
type Pending = { kind: 'delete' | 'suspend'; agent: Agent } | null

/** One project's agents, with the name of the flow each one runs. */
function ProjectAgents({
  project,
  agents,
  onRegister,
  onEdit,
  onAsk,
  onMakeDefault,
  onReactivate,
}: {
  project: Project
  agents: Agent[]
  onRegister: () => void
  onEdit: (agent: Agent) => void
  onAsk: (pending: NonNullable<Pending>) => void
  onMakeDefault: (agent: Agent) => void
  onReactivate: (agent: Agent) => void
}) {
  const { t } = useTranslation()
  const flows = useProjectFlows(agents.length ? project.id : undefined)
  const flowName = (id: string) => flows.data?.find((f) => f.id === id)?.name

  return (
    <Card>
      <CardHeader
        title={project.name}
        action={
          <Button size="sm" variant="secondary" onClick={onRegister}>
            <Plus className="size-4" aria-hidden="true" />
            {t('agents.list.register')}
          </Button>
        }
      />
      <div className="p-5 pt-3 sm:px-6">
        {agents.length === 0 ? (
          <p className="text-sm text-muted">{t('agents.list.empty')}</p>
        ) : (
          <ul className="divide-y divide-border" aria-label={project.name}>
            {agents.map((agent) => {
              const suspended = agent.status !== 'active'
              const name = flowName(agent.langflow_flow_id)
              return (
                <li key={agent.id} className="flex flex-wrap items-center gap-3 py-3">
                  <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-primary-ink">
                    <Bot className="size-4.5" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-medium">{agent.name}</span>
                      {agent.is_default && <Badge tone="primary">{t('agents.list.default')}</Badge>}
                      {suspended && <Badge tone="warning">{t('common.suspended')}</Badge>}
                    </span>
                    <span className="block truncate text-xs text-muted">
                      {name
                        ? t('agents.list.flow', { name })
                        : flows.isSuccess
                          ? t('agents.list.flowMissing')
                          : agent.langflow_flow_id}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1">
                    {!agent.is_default && (
                      <Button variant="ghost" size="icon" onClick={() => onMakeDefault(agent)} aria-label={t('agents.list.makeDefaultItem', { name: agent.name })} title={t('agents.list.makeDefault')}>
                        <Star className="size-4" aria-hidden="true" />
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" onClick={() => onEdit(agent)} aria-label={t('common.editItem', { name: agent.name })}>
                      <Pencil className="size-4" aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => (suspended ? onReactivate(agent) : onAsk({ kind: 'suspend', agent }))}
                      aria-label={t(suspended ? 'common.reactivateItem' : 'common.suspendItem', { name: agent.name })}
                    >
                      {suspended ? <Play className="size-4" aria-hidden="true" /> : <Pause className="size-4" aria-hidden="true" />}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => onAsk({ kind: 'delete', agent })} aria-label={t('common.deleteItem', { name: agent.name })}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </Button>
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Card>
  )
}

/**
 * The tenant's agents, grouped by project: register a flow of the project's
 * Langflow folder as an agent, rename it or point it at another flow, make
 * it the project's default, suspend/reactivate it (its channels stop
 * answering) and delete it (not while channels are connected).
 */
export function AgentsPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation()
  const projects = useProjects(tenantId)
  const agents = useAgents()
  const update = useUpdateAgent()
  const remove = useDeleteAgent()
  const [dialog, setDialog] = useState<{ agent: Agent | null; projectId?: string } | null>(null)
  const [pending, setPending] = useState<Pending>(null)

  if (projects.isPending || agents.isPending) return <Spinner label={t('agents.list.loading')} className="py-16" />
  if (projects.isError || agents.isError) {
    return <Alert tone="danger">{t('agents.list.loadError', { error: describeError(projects.error ?? agents.error) })}</Alert>
  }
  if (projects.data.length === 0) return <Alert tone="info">{t('agents.list.noProjects')}</Alert>

  const mutationError = pending?.kind === 'delete' ? remove.error : update.error
  const confirmError =
    mutationError instanceof ApiError && mutationError.status === 409 ? t('agents.delete.inUse') : mutationError ? describeError(mutationError) : null

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">{t('agents.list.description')}</p>
      <Alert tone="info">{t('agents.list.howTo')}</Alert>
      {update.error && !pending && <Alert tone="danger">{describeError(update.error)}</Alert>}
      {projects.data.map((project) => (
        <ProjectAgents
          key={project.id}
          project={project}
          agents={agents.data.filter((a) => a.project_id === project.id)}
          onRegister={() => setDialog({ agent: null, projectId: project.id })}
          onEdit={(agent) => setDialog({ agent })}
          onAsk={(next) => {
            remove.reset()
            update.reset()
            setPending(next)
          }}
          onMakeDefault={(agent) => void update.mutateAsync({ id: agent.id, patch: { is_default: true } }).catch(() => {})}
          onReactivate={(agent) => void update.mutateAsync({ id: agent.id, patch: { status: 'active' } }).catch(() => {})}
        />
      ))}

      {dialog && <AgentDialog projects={projects.data} agent={dialog.agent} projectId={dialog.projectId} onClose={() => setDialog(null)} />}
      <ConfirmDialog
        open={pending !== null}
        title={pending ? t(pending.kind === 'delete' ? 'common.deleteItem' : 'common.suspendItem', { name: pending.agent.name }) : ''}
        description={pending?.kind === 'delete' ? t('agents.delete.description') : t('agents.suspend.description')}
        confirmLabel={pending?.kind === 'delete' ? t('agents.delete.confirm') : t('agents.suspend.confirm')}
        pending={remove.isPending || update.isPending}
        error={confirmError}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (!pending) return
          const action =
            pending.kind === 'delete'
              ? remove.mutateAsync(pending.agent.id)
              : update.mutateAsync({ id: pending.agent.id, patch: { status: 'suspended' } })
          void action.then(() => setPending(null)).catch(() => {})
        }}
      />
    </div>
  )
}
