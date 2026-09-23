/** Lowercase and strip accents, so "José" matches "jose". */
export function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().trim()
}

/**
 * Whether any of `fields` contains `query`, ignoring case and accents.
 * An empty query matches everything.
 */
export function matchesQuery(query: string, ...fields: (string | null | undefined)[]): boolean {
  const q = normalize(query)
  return !q || fields.some((field) => field && normalize(field).includes(q))
}
