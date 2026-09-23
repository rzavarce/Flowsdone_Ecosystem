import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { useTheme } from '@/core/theme/useTheme'
import type { ColorMode } from '@/core/theme/themes'
import { useTranslation } from 'react-i18next'

const NEXT: Record<ColorMode, ColorMode> = { light: 'dark', dark: 'system', system: 'light' }
const ICON = { light: Sun, dark: Moon, system: Monitor }

/** Props for {@link ModeToggle}. */
export interface ModeToggleProps {
  /** Overrides the default ghost-button look (e.g. the top bar's round buttons). */
  className?: string
}

/** Button that cycles through light -> dark -> system. */
export function ModeToggle({ className }: ModeToggleProps) {
  const { t } = useTranslation()
  const { mode, setMode } = useTheme()
  const Icon = ICON[mode]
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setMode(NEXT[mode])}
      aria-label={t('theme.toggle', { current: t(`theme.modeName.${mode}`), next: t(`theme.modeName.${NEXT[mode]}`) })}
      title={t('theme.current', { current: t(`theme.modeName.${mode}`) })}
      className={cn(className)}
    >
      <Icon className="size-5" aria-hidden="true" />
    </Button>
  )
}
