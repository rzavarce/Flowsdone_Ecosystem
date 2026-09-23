import { Check, Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES, currentLanguage, setLanguage } from '@/core/i18n/i18n'
import { cn } from '@/lib/cn'

/** Props for {@link LanguageSelect}. */
export interface LanguageSelectProps {
  className?: string
}

/**
 * Compact native language selector (for screens without the user menu, like
 * login). Native `<select>`: accessible and mobile-friendly out of the box.
 */
export function LanguageSelect({ className }: LanguageSelectProps) {
  const { t, i18n } = useTranslation()
  return (
    <label className={cn('relative inline-flex items-center', className)}>
      <span className="sr-only">{t('layout.language')}</span>
      <Languages className="pointer-events-none absolute left-3 size-4 text-muted" aria-hidden="true" />
      <select
        value={i18n.language}
        onChange={(e) => setLanguage(e.target.value as (typeof LANGUAGES)[number]['id'])}
        className="h-10 cursor-pointer appearance-none rounded-full border border-border bg-surface py-2 pr-4 pl-9 text-sm font-medium text-foreground/85 shadow-theme-xs [&>option]:bg-surface"
      >
        {LANGUAGES.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Props for {@link LanguageOptions}. */
export interface LanguageOptionsProps {
  /** Called after switching (e.g. to close the menu). */
  onPicked?: () => void
}

/** Radio-like list of the languages, used inside the user dropdown. */
export function LanguageOptions({ onPicked }: LanguageOptionsProps) {
  const { t } = useTranslation()
  const active = currentLanguage()
  return (
    <ul role="radiogroup" aria-label={t('layout.language')} className="mt-1 space-y-0.5 pl-8">
      {LANGUAGES.map((l) => (
        <li key={l.id}>
          <button
            type="button"
            role="radio"
            aria-checked={active === l.id}
            onClick={() => {
              setLanguage(l.id)
              onPicked?.()
            }}
            className={cn(
              'flex w-full cursor-pointer items-center justify-between rounded-lg px-3 py-1.5 text-sm transition hover:bg-surface-muted',
              active === l.id ? 'font-medium text-primary-ink' : 'text-foreground/80',
            )}
          >
            {l.name}
            {active === l.id && <Check className="size-4" aria-hidden="true" />}
          </button>
        </li>
      ))}
    </ul>
  )
}
