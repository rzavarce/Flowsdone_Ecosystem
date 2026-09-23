import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateAgent, useProjectFlows, useUpdateAgent } from '@/core/admin/hooks'
import type { Agent, Project } from '@/core/admin/types'
import { ApiError } from '@/core/http/apiFetch'
import { describeError } from '@/core/http/describeError'
import { useTranslation } from 'react-i18next'

/** Props for {@link AgentDialog}. */
export interface AgentDialogProps {
  /** Projects of the tenant (the agent's project can't change once registered). */
  projects: Project[]
  /** Agent to edit, or `null` to register one. */
  agent: Agent | null
  /** Project preselected when registering. */
  projectId?: string
  onClose: () => void
}

const FORM_ID = 'agent-form'

/**
 * Register a flow of a project's Langflow folder as an agent, or edit one
 * (name, flow, default). The flow is picked from the folder - never typed -
 * so an agent can only point at a flow that exists in its own tenant.
 */
export function AgentDialog({ projects, agent, projectId, onClose }: AgentDialogProps) {
  const { t } = useTranslation()
  const create = useCreateAgent()
  const update = useUpdateAgent()
  const [project, setProject] = useState(agent?.project_id ?? projectId ?? projects[0]?.id ?? '')
  const [flowId, setFlowId] = useState(agent?.langflow_flow_id ?? '')
  const [name, setName] = useState(agent?.name ?? '')
  const [nameTouched, setNameTouched] = useState(Boolean(agent))
  const [isDefault, setIsDefault] = useState(agent?.is_default ?? false)
  const [errors, setErrors] = useState<{ flow?: string; name?: string }>({})
  const flows = useProjectFlows(project)
  const mutation = agent ? update : create
  const pending = mutation.isPending

  function pickFlow(id: string) {
    setFlowId(id)
    // Hasta que la persona lo toque, el nombre sigue al del flujo elegido.
    if (!nameTouched) setName(flows.data?.find((f) => f.id === id)?.name ?? '')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const problems = {
      flow: flowId ? undefined : t('agents.dialog.flowRequired'),
      name: name.trim() ? undefined : t('common.nameRequired'),
    }
    setErrors(problems)
    if (problems.flow || problems.name) return
    try {
      if (agent) {
        await update.mutateAsync({ id: agent.id, patch: { name: name.trim(), langflow_flow_id: flowId, ...(isDefault && !agent.is_default ? { is_default: true } : {}) } })
      } else {
        await create.mutateAsync({ project_id: project, name: name.trim(), langflow_flow_id: flowId, is_default: isDefault })
      }
      onClose()
    } catch {
      // El error queda en la mutación y se muestra abajo.
    }
  }

  const error = mutation.error
  const errorText =
    error instanceof ApiError && error.status === 400 ? t('agents.dialog.flowNotInFolder') : error ? describeError(error) : null

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={agent ? t('agents.dialog.editTitle', { name: agent.name }) : t('agents.dialog.registerTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label={t('agents.dialog.project')}>
          <Select
            value={project}
            disabled={Boolean(agent)}
            onChange={(e) => {
              setProject(e.target.value)
              setFlowId('')
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>

        {flows.isPending ? (
          <Spinner label={t('agents.dialog.loadingFlows')} />
        ) : flows.isError ? (
          <Alert tone="danger">{describeError(flows.error)}</Alert>
        ) : flows.data.length === 0 ? (
          <Alert tone="info">{t('agents.dialog.noFlows')}</Alert>
        ) : (
          <Field label={t('agents.dialog.flow')} hint={t('agents.dialog.flowHint')} error={errors.flow}>
            <Select value={flowId} onChange={(e) => pickFlow(e.target.value)}>
              <option value="">{t('agents.dialog.choose')}</option>
              {flows.data.map((f) => {
                const taken = f.agent_id !== null && f.agent_id !== agent?.id
                return (
                  <option key={f.id} value={f.id} disabled={taken}>
                    {taken ? t('agents.dialog.registered', { name: f.name }) : f.name}
                  </option>
                )
              })}
            </Select>
          </Field>
        )}

        <Field label={t('agents.dialog.name')} error={errors.name}>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value)
              setNameTouched(true)
            }}
          />
        </Field>
        <label className="flex cursor-pointer items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={isDefault}
            disabled={agent?.is_default}
            onChange={(e) => setIsDefault(e.target.checked)}
            className="mt-0.5 size-4 accent-primary"
          />
          <span>
            {t('agents.dialog.makeDefault')}
            <span className="block text-xs text-muted">{t('agents.dialog.makeDefaultHint')}</span>
          </span>
        </label>
        {errorText && <Alert tone="danger">{errorText}</Alert>}
      </form>
    </Dialog>
  )
}
