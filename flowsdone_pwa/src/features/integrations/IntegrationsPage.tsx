import { Cable, Webhook } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Field, Select } from '@/components/ui/Field'
import { Spinner } from '@/components/ui/Spinner'
import {
  useCrmIntegrations,
  useDeleteCrmIntegration,
  useProjects,
  useRotateCrmSecrets,
  useTestCrmIntegration,
  useUpdateCrmIntegration,
} from '@/core/admin/hooks'
import type { CrmIntegration, CrmIntegrationWithSecrets } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { useTenant } from '@/core/tenant/useTenant'
import { CRM_CATALOG } from './crmProviders'
import { CrmSecretsDialog } from './CrmSecretsDialog'
import { CrmWebhookDialog } from './CrmWebhookDialog'
import { useTranslation } from 'react-i18next'

/** The generic webhook card: connect it, or manage the connected integration. */
function WebhookCard({ projectId, integration }: { projectId: string; integration: CrmIntegration | null }) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState<'create' | 'edit' | null>(null)
  const [secrets, setSecrets] = useState<CrmIntegrationWithSecrets | null>(null)
  const [deleting, setDeleting] = useState(false)
  const test = useTestCrmIntegration()
  const rotate = useRotateCrmSecrets()
  const update = useUpdateCrmIntegration()
  const remove = useDeleteCrmIntegration()
  const active = integration?.status === 'active'

  async function rotateSecrets() {
    if (!integration) return
    try {
      setSecrets(await rotate.mutateAsync(integration.id))
    } catch {
      // El error se muestra abajo (rotate.error).
    }
  }

  async function confirmDelete() {
    if (!integration) return
    try {
      await remove.mutateAsync(integration.id)
      setDeleting(false)
    } catch {
      // El error se muestra en el diálogo (remove.error).
    }
  }

  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-primary/10 p-2 text-primary">
            <Webhook className="size-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="font-semibold">{t('integrations.webhook.title')}</h2>
            <p className="text-sm text-muted">{t('integrations.webhook.subtitle')}</p>
          </div>
        </div>
        {integration && (
          <Badge tone={active ? 'success' : 'neutral'}>{active ? t('common.active') : t('common.inactive')}</Badge>
        )}
      </div>

      {integration ? (
        <div className="mt-4 flex flex-1 flex-col gap-4">
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-muted">{t('integrations.webhook.url')}</dt>
              <dd className="truncate font-mono text-xs">{String(integration.config.url ?? '')}</dd>
            </div>
            <div>
              <dt className="text-muted">{t('integrations.replyUrl')}</dt>
              <dd className="truncate font-mono text-xs">{integration.reply_url}</dd>
            </div>
            <div>
              <dt className="text-muted">{t('integrations.closeUrl')}</dt>
              <dd className="truncate font-mono text-xs">{integration.close_url}</dd>
            </div>
          </dl>
          {test.data && (
            <Alert tone={test.data.ok ? 'success' : 'danger'}>
              {test.data.ok ? t('integrations.test.ok') : t('integrations.test.failed', { error: test.data.error ?? '' })}
            </Alert>
          )}
          {(test.error ?? rotate.error ?? update.error) && (
            <Alert tone="danger">{describeError((test.error ?? rotate.error ?? update.error)!)}</Alert>
          )}
          <div className="mt-auto flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => test.mutate(integration.id)} disabled={test.isPending || !active}>
              {test.isPending ? t('integrations.test.sending') : t('integrations.test.send')}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing('edit')}>
              {t('integrations.webhook.changeUrl')}
            </Button>
            <Button size="sm" variant="secondary" onClick={rotateSecrets} disabled={rotate.isPending}>
              {t('integrations.rotate')}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => update.mutate({ id: integration.id, patch: { status: active ? 'inactive' : 'active' } })}
              disabled={update.isPending}
            >
              {active ? t('integrations.deactivate') : t('integrations.activate')}
            </Button>
            <Button size="sm" variant="danger" onClick={() => { remove.reset(); setDeleting(true) }}>
              {t('common.delete')}
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-1 flex-col gap-4">
          <p className="text-sm text-muted">{t('integrations.webhook.description')}</p>
          <Button className="mt-auto self-start" onClick={() => setEditing('create')}>
            {t('integrations.webhook.connect')}
          </Button>
        </div>
      )}

      {editing && (
        <CrmWebhookDialog
          projectId={projectId}
          integration={editing === 'edit' ? integration : null}
          onCreated={(created) => {
            setEditing(null)
            setSecrets(created)
          }}
          onClose={() => setEditing(null)}
        />
      )}
      {secrets && <CrmSecretsDialog integration={secrets} onClose={() => setSecrets(null)} />}
      <ConfirmDialog
        open={deleting}
        title={t('integrations.delete.title')}
        description={t('integrations.delete.description')}
        confirmLabel={t('integrations.delete.confirm')}
        pending={remove.isPending}
        error={remove.error ? describeError(remove.error) : null}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(false)}
      />
    </Card>
  )
}

/**
 * CRM integrations of a project: where its conversations go when the bot hands
 * them over to a person. One integration per project; the generic webhook is
 * available today, the native CRMs are listed as coming soon.
 */
export function IntegrationsPage() {
  const { t } = useTranslation()
  const { current } = useTenant()
  const projects = useProjects(current?.id)
  const [chosen, setChosen] = useState('')
  const list = projects.data ?? []
  const projectId = list.some((p) => p.id === chosen) ? chosen : (list[0]?.id ?? '')
  const integrations = useCrmIntegrations(projectId || undefined, Boolean(projectId))
  const integration = integrations.data?.[0] ?? null

  return (
    <>
      <PageHeader title={t('nav.integrations')} description={t('integrations.description')} />

      {projects.isLoading ? (
        <Spinner label={t('integrations.loading')} className="py-20" />
      ) : projects.error ? (
        <Alert tone="danger">{describeError(projects.error)}</Alert>
      ) : list.length === 0 ? (
        <EmptyState icon={Cable} title={t('integrations.noProjects.title')} description={t('integrations.noProjects.description')} />
      ) : (
        <div className="space-y-6">
          <div className="max-w-sm">
            <Field label={t('integrations.project')}>
              <Select value={projectId} onChange={(e) => setChosen(e.target.value)}>
                {list.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <section aria-labelledby="crm-heading" className="space-y-3">
            <div>
              <h2 id="crm-heading" className="text-lg font-semibold">{t('integrations.crm.title')}</h2>
              <p className="text-sm text-muted">{t('integrations.crm.description')}</p>
            </div>
            {integrations.isLoading ? (
              <Spinner label={t('integrations.loading')} className="py-10" />
            ) : integrations.error ? (
              <Alert tone="danger">{describeError(integrations.error)}</Alert>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                <WebhookCard key={projectId} projectId={projectId} integration={integration} />
                {CRM_CATALOG.filter((c) => !c.available).map((c) => (
                  <Card key={c.id} className="flex items-start justify-between gap-3 p-5 opacity-70">
                    <div>
                      <h2 className="font-semibold">{c.name}</h2>
                      <p className="text-sm text-muted">{t('integrations.native')}</p>
                    </div>
                    <Badge>{t('integrations.comingSoon')}</Badge>
                  </Card>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  )
}
