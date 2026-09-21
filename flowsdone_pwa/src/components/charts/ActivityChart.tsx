import { Card, CardHeader } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import type { ActivityPoint } from '@/mocks/data'
import { H, W, linePath, toPoints } from './chartGeometry'

/** Gráfico de área simple (SVG, sin librería) con los colores del template. */
export function ActivityChart({ data, className }: { data: readonly ActivityPoint[]; className?: string }) {
  const points = toPoints(data.map((d) => d.value))
  const line = linePath(points)
  const area = `${line} L${points.at(-1)![0]} ${H} L${points[0]![0]} ${H} Z`
  const peak = data.reduce((a, b) => (b.value > a.value ? b : a))

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader title="Actividad semanal" description="Conversaciones por día" />
      <div className="flex flex-1 flex-col p-5">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Conversaciones por día; el máximo fue ${peak.value} el ${peak.label}.`}
          className="min-h-48 w-full flex-1"
        >
          <defs>
            <linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--primary)" stopOpacity="0.3" />
              <stop offset="1" stopColor="var(--primary)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill="url(#activity-fill)" />
          <path
            d={line}
            fill="none"
            stroke="var(--primary)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div className="mt-2 flex justify-between text-xs text-muted" aria-hidden="true">
          {data.map((d) => (
            <span key={d.label}>{d.label}</span>
          ))}
        </div>
      </div>
    </Card>
  )
}
