import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateConnection, useUpdateConnection } from '@/core/admin/hooks'
import type { ChannelConnection, ChannelType } from '@/core/admin/types'
import { useTenant } from '@/core/tenant/useTenant'
import { CHANNEL_TYPE_LIST, CHANNEL_TYPES, maskExternalId } from './channelTypes'
import { describeError } from '@/core/http/describeError'
import { NewProjectForm } from './NewProjectForm'
import type { ChannelsView } from './useChannelsView'

/** Props for {@link ConnectionDialog}. */
export interface ConnectionDialogProps {
  /** `null` = create a new channel; a connection = edit it. */
  connection: ChannelConnection | null
  view: ChannelsView
  onClose: () => void
}

const FORM_ID = 'connection-form'

/**
 * Form to connect a new channel or edit an existing one.
 *
 * When **creating**, the user picks project, type, agent (from that same
 * project) and identifier, plus whatever credentials the type requires. When
 * **editing**, only agent, name, status and (optionally) credentials can
 * change: the gateway doesn't allow moving a channel to another project or
 * changing its identifier. It's only mounted while open, so each opening
 * starts from a clean state.
 */
export function ConnectionDialog({ connection, view, onClose }: ConnectionDialogProps) {
  const editing = connection !== null
  const { current, tenants } = useTenant()
  const create = useCreateConnection()
  const update = useUpdateConnection()

  const [projectId, setProjectId] = useState('')
  const [channelType, setChannelType] = useState<ChannelType>('whatsapp_evolution')
  const [agentId, setAgentId] = useState(connection?.agent_id ?? '')
  const [externalId, setExternalId] = useState('')
  const [displayName, setDisplayName] = useState(connection?.display_name ?? '')
  const [status, setStatus] = useState(connection?.status ?? 'active')
  const [credentials, setCredentials] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  // Valores efectivos derivados (sin efectos): si la elección ya no es válida
  // (p. ej. cambió el proyecto), se cae al valor por defecto razonable.
  const effectiveProjectId = editing
    ? connection.project_id
    : view.projects.some((p) => p.id === projectId)
      ? projectId
      : (view.projects[0]?.id ?? '')
  const agentOptions = view.agents.filter((a) => a.project_id === effectiveProjectId)
  const effectiveAgentId = agentOptions.some((a) => a.id === agentId)
    ? agentId
    : (agentOptions.find((a) => a.is_default) ?? agentOptions[0])?.id ?? ''

  const type = editing ? connection.channel_type : channelType
  const config = CHANNEL_TYPES[type]
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error

  const errors = {
    project: !editing && !effectiveProjectId ? 'Elige un proyecto.' : '',
    agent: !effectiveAgentId ? 'Elige un agente.' : '',
    externalId: !editing && !externalId.trim() ? `${config.externalIdLabel} es obligatorio.` : '',
    credentials: Object.fromEntries(
      config.credentials.filter((f) => f.required && !editing && !credentials[f.key]?.trim()).map((f) => [f.key, `${f.label} es obligatorio.`]),
    ) as Record<string, string>,
  }
  const hasErrors = Boolean(errors.project || errors.agent || errors.externalId || Object.keys(errors.credentials).length)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (hasErrors) return
    const filled = Object.fromEntries(Object.entries(credentials).filter(([, v]) => v.trim()))
    try {
      if (editing) {
        await update.mutateAsync({
          id: connection.id,
          patch: {
            agent_id: effectiveAgentId,
            display_name: displayName.trim(),
            status,
            ...(Object.keys(filled).length ? { credentials: filled } : {}),
          },
        })
      } else {
        await create.mutateAsync({
          project_id: effectiveProjectId,
          agent_id: effectiveAgentId,
          channel_type: channelType,
          external_id: externalId.trim(),
          display_name: displayName.trim() || null,
          ...(Object.keys(filled).length ? { credentials: filled } : {}),
        })
      }
      onClose()
    } catch {
      // El error queda en create.error / update.error y se muestra abajo.
    }
  }

  const noProjects = !editing && view.projects.length === 0

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={editing ? 'Editar canal' : 'Conectar un canal'}
      description={
        editing
          ? `${config.label} · ${maskExternalId(type, connection.external_id)}`
          : 'Elige el proyecto, el canal y el agente que responderá por él.'
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          {!noProjects && (
            <Button type="submit" form={FORM_ID} disabled={pending}>
              {pending ? 'Guardando…' : editing ? 'Guardar cambios' : 'Conectar canal'}
            </Button>
          )}
        </>
      }
    >
      {noProjects ? (
        <NewProjectForm tenants={current ? [current] : tenants} defaultTenantId={current?.id} onCreated={(p) => setProjectId(p.id)} />
      ) : (
        <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
          {!editing && (
            <>
              <Field label="Proyecto" error={submitted ? errors.project : undefined}>
                <Select value={effectiveProjectId} onChange={(e) => setProjectId(e.target.value)}>
                  {view.projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Canal">
                <Select value={channelType} onChange={(e) => setChannelType(e.target.value as ChannelType)}>
                  {CHANNEL_TYPE_LIST.map((c) => (
                    <option key={c.type} value={c.type}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}

          <Field label="Agente" error={submitted ? errors.agent : undefined}>
            <Select value={effectiveAgentId} onChange={(e) => setAgentId(e.target.value)} disabled={agentOptions.length === 0}>
              {agentOptions.length === 0 && <option value="">Sin agentes</option>}
              {agentOptions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.is_default ? ' (por defecto)' : ''}
                </option>
              ))}
            </Select>
          </Field>
          {agentOptions.length === 0 && (
            <Alert tone="info">
              Este proyecto todavía no tiene agentes. Crea uno en{' '}
              <Link to="/agents" className="font-medium underline">
                Agentes
              </Link>{' '}
              para poder conectar un canal.
            </Alert>
          )}

          {!editing && (
            <Field label={config.externalIdLabel} hint={config.externalIdHint} error={submitted ? errors.externalId : undefined}>
              <Input
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                placeholder={config.externalIdPlaceholder}
                autoComplete="off"
                spellCheck={false}
              />
            </Field>
          )}

          <Field label="Nombre para mostrar" hint="Opcional. Ayuda a distinguirlo en la lista.">
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={config.label} />
          </Field>

          {editing && (
            <Field label="Estado">
              <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="active">Activo</option>
                <option value="inactive">Inactivo</option>
              </Select>
            </Field>
          )}

          {config.credentials.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              hint={editing ? 'Déjalo vacío para conservar el actual. Si escribes uno, reemplaza al anterior.' : field.hint}
              error={submitted ? errors.credentials[field.key] : undefined}
            >
              <Input
                type="password"
                value={credentials[field.key] ?? ''}
                onChange={(e) => setCredentials((c) => ({ ...c, [field.key]: e.target.value }))}
                autoComplete="off"
              />
            </Field>
          ))}

          {!editing && config.note && <Alert tone="info">{config.note}</Alert>}
          {error && <Alert tone="danger">{describeError(error)}</Alert>}
        </form>
      )}
    </Dialog>
  )
}
