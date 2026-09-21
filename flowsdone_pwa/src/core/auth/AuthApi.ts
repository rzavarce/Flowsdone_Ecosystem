import type { Credentials, User } from './types'

/**
 * Puerto de autenticación. La UI solo conoce esta interfaz; hay un adaptador
 * mock (maqueta/desarrollo) y uno HTTP (backend real).
 */
export interface AuthApi {
  /** Recupera la sesión existente al abrir la app; `null` si no hay. */
  restore(): Promise<User | null>
  /** Inicia sesión. @throws AuthError con `invalid_credentials` o `unavailable`. */
  login(credentials: Credentials): Promise<User>
  /** Cierra la sesión (mejor esfuerzo: nunca debería impedir salir). */
  logout(): Promise<void>
}

export type AuthErrorCode = 'invalid_credentials' | 'rate_limited' | 'unavailable'

/** Error de autenticación con un mensaje apto para mostrar a la persona usuaria. */
export class AuthError extends Error {
  readonly code: AuthErrorCode

  constructor(code: AuthErrorCode, message: string) {
    super(message)
    this.name = 'AuthError'
    this.code = code
  }
}
