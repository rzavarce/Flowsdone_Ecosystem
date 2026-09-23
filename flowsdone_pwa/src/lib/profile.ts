import { SOCIAL_NETWORKS, type SocialNetwork } from '@/core/auth/types'

/**
 * Client-side mirror of the gateway's profile rules (`normalize_profile_fields`
 * in manage_profile.py), so the form flags problems before the round trip.
 * The gateway validates again; these only return i18n keys.
 */

const PHONE_RE = /^\+?[0-9 ()./-]{4,40}$/

/** Longest address the gateway accepts. */
export const MAX_ADDRESS = 300

/**
 * Checks an optional phone.
 *
 * @param phone - Raw input (empty is fine: the field is optional).
 * @returns An i18n key describing the problem, or `null` if valid.
 */
export function phoneError(phone: string): 'profile.errors.phone' | null {
  const value = phone.trim()
  return value && !PHONE_RE.test(value) ? 'profile.errors.phone' : null
}

/**
 * Checks an optional profile link.
 *
 * @param url - Raw input (empty is fine).
 * @returns An i18n key if it isn't an http(s) URL, or `null` if valid.
 */
export function urlError(url: string): 'profile.errors.url' | null {
  const value = url.trim()
  if (!value) return null
  try {
    const parsed = new URL(value)
    return (parsed.protocol === 'http:' || parsed.protocol === 'https:') && parsed.hostname && value.length <= 300
      ? null
      : 'profile.errors.url'
  } catch {
    return 'profile.errors.url'
  }
}

/**
 * Drops empty links and trims the rest (what the gateway stores).
 *
 * @param links - Links as typed in the form.
 * @returns Only the networks with a URL.
 */
export function cleanLinks(links: Partial<Record<SocialNetwork, string>>): Partial<Record<SocialNetwork, string>> {
  return Object.fromEntries(
    Object.entries(links)
      .map(([k, v]) => [k, (v ?? '').trim()])
      .filter(([, v]) => v),
  ) as Partial<Record<SocialNetwork, string>>
}

/** The optional profile fields as edited in a form (empty string = not set). */
export interface ProfileFieldsValue {
  phone: string
  address: string
  social_links: Partial<Record<SocialNetwork, string>>
}

/** Which blocks of the profile form (`ProfileFieldsInputs`) to show. */
export type ProfileFieldsPart = 'phone' | 'address' | 'social'

/**
 * Validation errors of the optional fields, as i18n keys (empty object = valid).
 *
 * @param value - Current form value.
 * @returns Errors keyed by `phone`, `address` or the social network.
 */
export function profileFieldsErrors(value: ProfileFieldsValue): Record<string, string> {
  const errors: Record<string, string> = {}
  const phone = phoneError(value.phone)
  if (phone) errors.phone = phone
  if (value.address.trim().length > MAX_ADDRESS) errors.address = 'profile.errors.address'
  for (const network of SOCIAL_NETWORKS) {
    const err = urlError(value.social_links[network] ?? '')
    if (err) errors[network] = err
  }
  return errors
}

