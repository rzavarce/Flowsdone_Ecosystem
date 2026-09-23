/**
 * Converts a name into a slug (lowercase, no accents, hyphen-separated).
 *
 * @example slugify('Atención al paciente') // 'atencion-al-paciente'
 */
export function slugify(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
