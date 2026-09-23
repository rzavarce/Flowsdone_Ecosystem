/**
 * Returns up to two initials from a name.
 *
 * @example initials('Ana María Pérez') // 'AM'
 */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return parts
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join('')
}
