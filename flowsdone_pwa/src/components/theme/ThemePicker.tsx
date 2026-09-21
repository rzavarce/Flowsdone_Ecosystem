import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useTheme } from '@/core/theme/useTheme'
import { THEMES, type ColorMode } from '@/core/theme/themes'

const MODES: { id: ColorMode; label: string; icon: typeof Sun }[] = [
  { id: 'light', label: 'Claro', icon: Sun },
  { id: 'dark', label: 'Oscuro', icon: Moon },
  { id: 'system', label: 'Sistema', icon: Monitor },
]

/**
 * Selector de template: grilla de presets con vista previa en vivo y control
 * segmentado de modo. Cada tarjeta lleva su propio `data-theme`, así muestra
 * los colores de ese preset sin importar cuál esté activo.
 */
export function ThemePicker() {
  const { theme, mode, setTheme, setMode } = useTheme()

  return (
    <div className="space-y-8">
      <section aria-labelledby="mode-title">
        <h3 id="mode-title" className="text-sm font-semibold">
          Modo
        </h3>
        <div role="radiogroup" aria-labelledby="mode-title" className="mt-3 inline-flex rounded-xl bg-surface-muted p-1">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={mode === id}
              onClick={() => setMode(id)}
              className={cn(
                'inline-flex cursor-pointer items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition',
                mode === id ? 'bg-surface text-foreground shadow-sm' : 'text-muted hover:text-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="template-title">
        <h3 id="template-title" className="text-sm font-semibold">
          Template
        </h3>
        <div role="radiogroup" aria-labelledby="template-title" className="mt-3 grid gap-4 sm:grid-cols-2">
          {THEMES.map((preset) => {
            const active = theme === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                role="radio"
                aria-checked={active}
                data-theme={preset.id}
                onClick={() => setTheme(preset.id)}
                className={cn(
                  'cursor-pointer rounded-card border bg-surface p-3 text-left transition',
                  active ? 'border-primary ring-2 ring-primary/30' : 'border-border hover:border-primary/50',
                )}
              >
                <span
                  className="relative block h-20 overflow-hidden rounded-xl"
                  style={{ backgroundImage: 'var(--gradient-brand)' }}
                  aria-hidden="true"
                >
                  <span className="absolute inset-x-3 bottom-3 flex gap-1.5">
                    <span className="h-2 flex-1 rounded-full bg-white/70" />
                    <span className="h-2 w-8 rounded-full bg-white/40" />
                  </span>
                </span>
                <span className="mt-3 flex items-center justify-between gap-2">
                  <span className="font-semibold">{preset.name}</span>
                  {active && (
                    <span className="inline-flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="size-3.5" aria-hidden="true" />
                      <span className="sr-only">Activo</span>
                    </span>
                  )}
                </span>
                <span className="mt-0.5 block text-sm text-muted">{preset.description}</span>
              </button>
            )
          })}
        </div>
      </section>
    </div>
  )
}
