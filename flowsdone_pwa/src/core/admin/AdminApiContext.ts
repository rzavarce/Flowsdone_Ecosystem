import { createContext } from 'react'
import type { AdminApi } from './AdminApi'

export const AdminApiContext = createContext<AdminApi | null>(null)
