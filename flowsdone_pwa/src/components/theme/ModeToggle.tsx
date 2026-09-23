import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useTheme } from '@/core/theme/useTheme'
import type { ColorMode } from '@/core/theme/themes'

const NEXT: Record<ColorMode, ColorMode> = { light: 'dark', dark: 'system', system: 'light' }
const LABEL: Record<ColorMode, string> = { light: 'claro', dark: 'oscuro', system: 'del sistema' }
const ICON = { light: Sun, dark: Moon, system: Monitor }

/** Top bar button that cycles through light -> dark -> system. */
export function ModeToggle() {
  const { mode, setMode } = useTheme()
  const Icon = ICON[mode]
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setMode(NEXT[mode])}
      aria-label={`Modo ${LABEL[mode]}. Cambiar a modo ${LABEL[NEXT[mode]]}`}
      title={`Modo ${LABEL[mode]}`}
    >
      <Icon className="size-5" aria-hidden="true" />
    </Button>
  )
}
