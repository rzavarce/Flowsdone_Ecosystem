import { useId } from 'react'
import { useTheme } from '@/core/theme/useTheme'

/**
 * Flowsdone logo, vector-based. The geometry mirrors `public/brand/flowsdone-logo.svg`
 * (the design's source of truth); it's painted here with a palette chosen by
 * background so the text doesn't disappear on light surfaces.
 *
 * - `icon`: square isotype (collapsed sidebar, mobile bar).
 * - `wordmark`: isotype + "Flowsdone".
 * - `full`: wordmark + "INTELLIGENCE IN MOTION" tagline.
 */
export type LogoVariant = 'icon' | 'wordmark' | 'full'

interface Palette {
  text: string
  done: string
  slogan: string
  /** Stroke gradient stops: 0%, 55%, 85%, 100%. */
  line: [string, string, string, string]
  nodeStart: string
  nodeEnd: string
  glow: boolean
}

/** On dark backgrounds: original brand colors, with a neon glow. */
const ON_DARK: Palette = {
  text: '#F2FBF7',
  done: '#3EFF8B',
  slogan: '#19B4E6',
  line: ['#19B4E6', '#19B4E6', '#24E5A3', '#3EFF8B'],
  nodeStart: '#19B4E6',
  nodeEnd: '#3EFF8B',
  glow: true,
}

/** On light backgrounds: darker variants (contrast-calculated) and no glow. */
const ON_LIGHT: Palette = {
  text: '#04141F',
  done: '#0A8F48',
  slogan: '#0A6F94',
  line: ['#0A9CC8', '#0A9CC8', '#10A27A', '#0A8F48'],
  nodeStart: '#0A9CC8',
  nodeEnd: '#0A8F48',
  glow: false,
}

const WAVE = 'M 8 32 C 16 16, 32 16, 44 28 C 54 38, 64 36, 72 26 L 84 38 L 108 4'
const FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

/** Crops (viewBox) for each variant over the original 490x110 canvas. */
const VIEWBOX: Record<Exclude<LogoVariant, 'icon'>, string> = {
  wordmark: '26 24 350 50',
  full: '26 24 350 60',
}

/** Props for {@link Logo}. */
export interface LogoProps {
  variant?: LogoVariant
  /**
   * `auto` follows the app's color mode; `onDark` forces the palette for
   * fixed dark backgrounds (e.g. the login page's brand panel).
   */
  tone?: 'auto' | 'onDark'
  /** Set the height, e.g. `h-8 w-auto` (or `size-9` for `icon`). */
  className?: string
}

/** Flowsdone logo with an accessible name (`role="img"`). */
export function Logo({ variant = 'wordmark', tone = 'auto', className }: LogoProps) {
  const { resolvedMode } = useTheme()
  const uid = useId().replace(/:/g, '')
  const gradId = `${uid}-line`
  const glowId = `${uid}-glow`
  const p = tone === 'onDark' || resolvedMode === 'dark' ? ON_DARK : ON_LIGHT
  const glow = p.glow ? `url(#${glowId})` : undefined

  const defs = (
    <defs>
      <linearGradient id={gradId} x1="0%" y1="50%" x2="100%" y2="50%">
        <stop offset="0%" stopColor={p.line[0]} />
        <stop offset="55%" stopColor={p.line[1]} />
        <stop offset="85%" stopColor={p.line[2]} />
        <stop offset="100%" stopColor={p.line[3]} />
      </linearGradient>
      <filter id={glowId} x="-20%" y="-60%" width="140%" height="220%">
        <feGaussianBlur stdDeviation="2.5" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
    </defs>
  )

  if (variant === 'icon') {
    // Tile oscuro fijo (como el favicon): se ve bien sobre cualquier fondo.
    return (
      <svg viewBox="0 0 64 64" role="img" aria-label="Flowsdone" className={className}>
        {defs}
        <rect width="64" height="64" rx="14" fill="#04141F" />
        <g transform="translate(3 21.5) scale(0.5)" filter={`url(#${glowId})`}>
          <path d={WAVE} fill="none" stroke={`url(#${gradId})`} strokeWidth="8.8" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="8" cy="32" r="6.2" fill={ON_DARK.nodeStart} />
          <circle cx="108" cy="4" r="6.2" fill={ON_DARK.nodeEnd} />
        </g>
      </svg>
    )
  }

  return (
    <svg
      viewBox={VIEWBOX[variant]}
      role="img"
      aria-label={variant === 'full' ? 'Flowsdone — Intelligence in motion' : 'Flowsdone'}
      className={className}
    >
      {defs}
      <g transform="translate(30, 32)">
        <path d={WAVE} fill="none" stroke={`url(#${gradId})`} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" filter={glow} />
        <circle cx="8" cy="32" r="4.5" fill={p.nodeStart} filter={glow} />
        <circle cx="108" cy="4" r="4.5" fill={p.nodeEnd} filter={glow} />
      </g>
      <g transform="translate(150, 60)" fontFamily={FONT}>
        {/* Capa de resplandor: solo "done" (Flows va sin relleno). Es un <text> aparte
            porque el filtro no aplica a <tspan>. */}
        {glow && (
          <text fontSize="40" fontWeight="700" fill="none" letterSpacing="-0.5" filter={glow} aria-hidden="true">
            Flows
            <tspan fontWeight="300" fill={p.done}>
              done
            </tspan>
          </text>
        )}
        {/* "done" fluye tras "Flows" (tspan): no depende del ancho de la tipografía del sistema. */}
        <text fontSize="40" fontWeight="700" fill={p.text} letterSpacing="-0.5">
          Flows
          <tspan fontWeight="300" fill={p.done}>
            done
          </tspan>
        </text>
        {variant === 'full' && (
          <text x="1" y="16" fontSize="10.2" fontWeight="700" fill={p.slogan} letterSpacing="3.1" opacity="0.95">
            INTELLIGENCE IN MOTION
          </text>
        )}
      </g>
    </svg>
  )
}
