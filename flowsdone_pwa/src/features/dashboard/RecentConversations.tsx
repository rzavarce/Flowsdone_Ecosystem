import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Card, CardHeader } from '@/components/ui/Card'
import type { ConversationSummary } from '@/mocks/data'
import { useTranslation } from 'react-i18next'

/** List of the latest conversations with their channel and status. */
export function RecentConversations({
  items,
  className,
}: {
  items: readonly ConversationSummary[]
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <Card className={className}>
      <CardHeader title={t('dashboard.recent.title')} description={t('dashboard.recent.description')} />
      <ul className="p-2">
        {items.map((c) => (
          <li key={c.id} className="flex items-center gap-3 rounded-xl p-3 transition hover:bg-surface-muted">
            <Avatar name={c.contact} />
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2">
                <span className="truncate text-sm font-medium">{c.contact}</span>
                <span className="text-xs text-muted">· {c.channel}</span>
              </p>
              <p className="truncate text-sm text-muted">{c.preview}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Badge tone={c.status.tone}>{c.status.label}</Badge>
              <span className="text-xs text-muted">{c.time}</span>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
