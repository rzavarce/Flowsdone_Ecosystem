import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const h1 = (name: string | RegExp) => screen.findByRole('heading', { level: 1, name })

describe('CompanyPage', () => {
  it('muestra los datos de facturación de la propia empresa (autoservicio, modo mock)', async () => {
    renderApp('/mi-empresa', fakeAuthApi(makeUser('client')))
    await h1('Mi empresa')

    expect(await screen.findByText('Clínica Vital S.A. de C.V.')).toBeInTheDocument()
    expect(screen.getByText('CVI010203AB4')).toBeInTheDocument()
    expect(screen.getByText('facturas@clinicavital.com')).toBeInTheDocument()
    expect(screen.getByText('MXN')).toBeInTheDocument()
  })
})
