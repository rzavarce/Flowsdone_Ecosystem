import type { Credentials, User } from './types'

/**
 * Authentication port. The UI only knows this interface; there is a mock
 * adapter (demo/development) and an HTTP one (the real backend).
 */
export interface AuthApi {
  /** Restores the existing session when the app opens; `null` if there is none. */
  restore(): Promise<User | null>
  /** Logs in. @throws AuthError with `invalid_credentials` or `unavailable`. */
  login(credentials: Credentials): Promise<User>
  /** Logs out (best effort: should never block the user from leaving). */
  logout(): Promise<void>
  /**
   * Redeems the activation link's token and sets the password: activates the
   * account and leaves the session logged in. @throws AuthError with
   * `invalid_token` (expired/already-used link, or invalid password) or `unavailable`.
   */
  activateAccount(token: string, password: string): Promise<User>
  /**
   * Requests the "forgot my password" email. Never reveals whether the
   * account exists: always resolves, except for `rate_limited`/`unavailable`.
   */
  requestPasswordReset(email: string): Promise<void>
  /**
   * Redeems the recovery link's token and sets the new password: leaves the
   * session logged in. @throws AuthError with `invalid_token` or `unavailable`.
   */
  resetPassword(token: string, password: string): Promise<User>
}

/** Machine-readable auth failure reasons the UI maps to user-facing copy. */
export type AuthErrorCode = 'invalid_credentials' | 'rate_limited' | 'unavailable' | 'invalid_token'

/** Authentication error carrying a message fit to show the user. */
export class AuthError extends Error {
  readonly code: AuthErrorCode

  constructor(code: AuthErrorCode, message: string) {
    super(message)
    this.name = 'AuthError'
    this.code = code
  }
}
