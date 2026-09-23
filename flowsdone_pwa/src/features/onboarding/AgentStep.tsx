import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useAgents, useCreateBaseAgent } from '@/core/admin/hooks'
import type { AgentTone } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { cn } from '@/lib/cn'
import { StepFrame } from './StepFrame'
import { useTranslation } from 'react-i18next'

const TONES: AgentTone[] = ['cercano', 'profesional', 'formal']

/**
 * Step 4: the base agent - a chat assistant with conversation memory whose
 * instructions are built from these answers, created in the project's
 * Langflow folder and registered as its default agent. If the project
 * already has an agent, the step just shows it.
 */
export function AgentStep({
  projectId,
  companyName,
  onDone,
  onBack,
}: {
  projectId: string
  companyName: string
  onDone: () => void
  onBack: () => void
}) {
  const { t } = useTranslation()
  const agents = useAgents()
  const create = useCreateBaseAgent()
  const [assistantName, setAssistantName] = useState<string>(t('onboarding.agent.defaultName', { company: companyName }))
  const [tone, setTone] = useState<AgentTone>('cercano')
  const [instructions, setInstructions] = useState('')
  const [error, setError] = useState<string | null>(null)
  if (agents.isPending) return <Spinner label={t('onboarding.loading')} className="py-16" />
  const existing = agents.data?.find((a) => a.project_id === projectId)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (existing) return onDone()
    if (!assistantName.trim()) return setError(t('common.nameRequired'))
    setError(null)
    try {
      await create.mutateAsync({ project_id: projectId, assistant_name: assistantName.trim(), tone, instructions: instructions.trim() })
      onDone()
    } catch {
      // El error queda en create.error.
    }
  }

  return (
    <StepFrame
      title={t('onboarding.steps.agent')}
      description={t('onboarding.agent.description')}
      onSubmit={submit}
      onBack={onBack}
      pending={create.isPending}
      pendingLabel={t('onboarding.agent.creating')}
      error={error ?? (create.error ? describeError(create.error) : null)}
    >
      {existing ? (
        <Alert tone="success">{t('onboarding.agent.existing', { name: existing.name })}</Alert>
      ) : (
        <div className="space-y-5">
          <Field label={t('onboarding.agent.assistantName')} hint={t('onboarding.agent.assistantNameHint')}>
            <Input value={assistantName} maxLength={60} onChange={(e) => setAssistantName(e.target.value)} />
          </Field>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-foreground/80">{t('onboarding.agent.tone')}</legend>
            <div role="radiogroup" aria-label={t('onboarding.agent.tone')} className="grid gap-3 sm:grid-cols-3">
              {TONES.map((id) => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={tone === id}
                  onClick={() => setTone(id)}
                  className={cn(
                    'cursor-pointer rounded-xl border p-3 text-left text-sm transition',
                    tone === id ? 'border-primary bg-primary/5 ring-2 ring-primary/30' : 'border-border hover:bg-surface-muted',
                  )}
                >
                  <span className="block font-medium">{t(`onboarding.agent.tones.${id}.label`)}</span>
                  <span className="block text-xs text-muted">{t(`onboarding.agent.tones.${id}.description`)}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <Field label={t('onboarding.agent.instructions')} hint={t('onboarding.agent.instructionsHint')}>
            <textarea
              value={instructions}
              maxLength={4000}
              rows={6}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder={t('onboarding.agent.instructionsPlaceholder')}
              className="w-full rounded-lg border border-input bg-transparent px-4 py-3 text-sm shadow-theme-xs placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
            />
          </Field>
        </div>
      )}
    </StepFrame>
  )
}
