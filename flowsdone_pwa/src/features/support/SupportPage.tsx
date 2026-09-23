import { ChevronDown, CircleHelp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card } from '@/components/ui/Card'
import { FAQ_IDS } from './faq'

/**
 * Support: frequently asked questions about using the console, for every
 * role. Native `<details>` so it's keyboard- and screen-reader-friendly
 * without extra code.
 */
export function SupportPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('support.title')} description={t('support.description')} />
      <Card className="p-5 lg:p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <CircleHelp className="size-5 text-primary-ink" aria-hidden="true" />
          {t('support.faqTitle')}
        </h2>
        <div className="divide-y divide-border rounded-2xl border border-border">
          {FAQ_IDS.map((id) => (
            <details key={id} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-medium transition hover:bg-surface-muted [&::-webkit-details-marker]:hidden">
                {t(`support.faq.${id}.q`)}
                <ChevronDown className="size-5 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="px-5 pb-5 text-sm leading-relaxed text-muted">{t(`support.faq.${id}.a`)}</p>
            </details>
          ))}
        </div>
        <p className="mt-6 text-sm text-muted">{t('support.contact')}</p>
      </Card>
    </>
  )
}
