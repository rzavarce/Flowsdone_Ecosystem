import { createContext } from 'react'
import type { AdminApi } from './AdminApi'

/** React context carrying the active {@link AdminApi} adapter; `null` outside `<AdminApiProvider>`. */
export const AdminApiContext = createContext<AdminApi | null>(null)
