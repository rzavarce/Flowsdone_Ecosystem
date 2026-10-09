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
import { originsOf, parseOrigins } from './webchat'
import type { ChannelsView } from './useChannelsView'
import { Trans, useTranslation } from 'react-i18next'

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
  const { t } = useTranslation()
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
  const [origins, setOrigins] = useState(() => originsOf(connection).join('\n'))
  const [sandbox, setSandbox] = useState(() => connection?.config?.sandbox === true)
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
  // 360dialog identifies the connection by the business number: digits only.
  const cleanExternalId = type === 'whatsapp_360dialog' ? externalId.replace(/\D/g, '') : externalId.trim()
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error

  const errors = {
    project: !editing && !effectiveProjectId ? t('channels.form.errors.project') : '',
    agent: !effectiveAgentId ? t('channels.form.errors.agent') : '',
    externalId: !editing && !config.autoKey && !cleanExternalId ? t('common.fieldRequired', { field: config.externalIdLabel }) : '',
    credentials: Object.fromEntries(
      config.credentials.filter((f) => f.required && !editing && !credentials[f.key]?.trim()).map((f) => [f.key, t('common.fieldRequired', { field: f.label })]),
    ) as Record<string, string>,
  }
  const hasErrors = Boolean(errors.project || errors.agent || errors.externalId || Object.keys(errors.credentials).length)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (hasErrors) return
    const filled = Object.fromEntries(Object.entries(credentials).filter(([, v]) => v.trim()))
    const typeConfig =
      type === 'webchat'
        ? { config: { allowed_origins: parseOrigins(origins) } }
        : type === 'whatsapp_360dialog'
          ? { config: { sandbox } }
          : {}
    try {
      if (editing) {
        await update.mutateAsync({
          id: connection.id,
          patch: {
            agent_id: effectiveAgentId,
            display_name: displayName.trim(),
            status,
            ...(Object.keys(filled).length ? { credentials: filled } : {}),
            ...typeConfig,
          },
        })
      } else {
        await create.mutateAsync({
          project_id: effectiveProjectId,
          agent_id: effectiveAgentId,
          channel_type: channelType,
          ...(config.autoKey ? {} : { external_id: cleanExternalId }),
          display_name: displayName.trim() || null,
          ...(Object.keys(filled).length ? { credentials: filled } : {}),
          ...typeConfig,
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
      title={editing ? t('channels.form.editTitle') : t('channels.form.createTitle')}
      description={
        editing
          ? `${config.label} · ${maskExternalId(type, connection.external_id)}`
          : t('channels.form.createDescription')
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          {!noProjects && (
            <Button type="submit" form={FORM_ID} disabled={pending}>
              {pending ? t('common.saving') : editing ? t('common.saveChanges') : t('channels.form.submit')}
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
              <Field label={t('common.project')} error={submitted ? errors.project : undefined}>
                <Select value={effectiveProjectId} onChange={(e) => setProjectId(e.target.value)}>
                  {view.projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t('channels.form.channel')}>
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

          <Field label={t('common.agent')} error={submitted ? errors.agent : undefined}>
            <Select value={effectiveAgentId} onChange={(e) => setAgentId(e.target.value)} disabled={agentOptions.length === 0}>
              {agentOptions.length === 0 && <option value="">{t('channels.form.noAgents')}</option>}
              {agentOptions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.is_default ? ` ${t('channels.form.defaultAgent')}` : ''}
                </option>
              ))}
            </Select>
          </Field>
          {agentOptions.length === 0 && (
            <Alert tone="info">
              <Trans
                i18nKey="channels.form.noAgentsHelp"
                components={{ agentsLink: <Link to="/agents" className="font-medium underline" /> }}
              />
            </Alert>
          )}

          {!editing && !config.autoKey && (
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

          <Field label={t('channels.form.displayName')} hint={t('channels.form.displayNameHint')}>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={config.label} />
          </Field>

          {type === 'webchat' && (
            <Field label={t('channels.form.allowedOrigins')} hint={t('channels.form.allowedOriginsHint')}>
              <textarea
                value={origins}
                rows={3}
                onChange={(e) => setOrigins(e.target.value)}
                placeholder="https://miempresa.com"
                spellCheck={false}
                className="w-full rounded-lg border border-input bg-transparent px-4 py-3 font-mono text-sm shadow-theme-xs placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
              />
            </Field>
          )}

          {type === 'whatsapp_360dialog' && (
            <label className="flex cursor-pointer items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={sandbox}
                onChange={(e) => setSandbox(e.target.checked)}
                className="mt-0.5 size-4 accent-primary"
              />
              <span>
                {t('channels.form.sandbox')}
                <span className="block text-xs text-muted">{t('channels.form.sandboxHint')}</span>
              </span>
            </label>
          )}

          {editing && (
            <Field label={t('common.status')}>
              <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="active">{t('common.active')}</option>
                <option value="inactive">{t('common.inactive')}</option>
              </Select>
            </Field>
          )}

          {config.credentials.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              hint={editing ? t('channels.form.keepCredential') : field.hint}
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
