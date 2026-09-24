import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import { SEED } from '@/test/adminFixtures'
import { fakeAuthApi, makeUser, renderApp } from '@/test/renderApp'

const api = () => createMockAdminApi({ latencyMs: 0, seed: SEED })
const next = () => userEvent.click(screen.getByRole('button', { name: 'Guardar y continuar' }))
const heading = (name: string) => screen.findByRole('heading', { level: 2, name })

describe('Alta de cliente (wizard)', { timeout: 30_000 }, () => {
  it('da de alta un cliente de principio a fin', async () => {
    const admin = api()
    const spies = {
      tenant: vi.spyOn(admin, 'createTenant'),
      billing: vi.spyOn(admin, 'updateTenantBilling'),
      plan: vi.spyOn(admin, 'putSubscription'),
      project: vi.spyOn(admin, 'createProject'),
      agent: vi.spyOn(admin, 'createBaseAgent'),
    }
    renderApp('/onboarding', fakeAuthApi(makeUser('admin')), admin)

    await heading('Empresa')
    expect(screen.getByText('Paso 1 de 5')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Nombre'), 'Farmasi Iberia')
    expect(screen.getByLabelText(/Identificador/)).toHaveValue('farmasi-iberia')
    await userEvent.type(screen.getByLabelText('Nombre de la persona de contacto'), 'Laura')
    await userEvent.type(screen.getByLabelText('Email de acceso a la consola'), 'laura@farmasi.es')
    await userEvent.type(screen.getByLabelText('Razón social'), 'Farmasi Iberia SL')
    await userEvent.type(screen.getByLabelText('Email de facturación'), 'facturas@farmasi.es')
    await next()

    await heading('Plan')
    expect(spies.tenant).toHaveBeenCalledWith(expect.objectContaining({ name: 'Farmasi Iberia', slug: 'farmasi-iberia', client_email: 'laura@farmasi.es' }))
    const tenantId = (await spies.tenant.mock.results[0]!.value).id
    expect(spies.billing).toHaveBeenCalledWith(tenantId, expect.objectContaining({ legal_name: 'Farmasi Iberia SL', billing_email: 'facturas@farmasi.es', currency: 'EUR' }))
    await userEvent.click(screen.getByRole('radio', { name: /Pro/ }))
    await next()

    await heading('Proyecto')
    expect(spies.plan).toHaveBeenCalledWith(tenantId, { plan_id: 'plan-pro', overage_mode: null, spending_cap_micros: null })
    expect(screen.getByLabelText('Nombre')).toHaveValue('Atención al cliente')
    await next()

    await heading('Agente')
    expect(spies.project).toHaveBeenCalledWith({ tenant_id: tenantId, name: 'Atención al cliente', slug: 'atencion-al-cliente' })
    expect(screen.getByLabelText('Nombre del asistente')).toHaveValue('Asistente de Farmasi Iberia')
    await userEvent.click(screen.getByRole('radio', { name: /Formal/ }))
    // Viene con un texto de partida con el nombre de la empresa, que se puede cambiar.
    const about = screen.getByLabelText<HTMLTextAreaElement>('Sobre el negocio')
    expect(about.value).toContain('Formas parte del equipo de atención de Farmasi Iberia.')
    await userEvent.clear(about)
    await userEvent.type(about, 'Cosmética y bienestar.')
    await next()

    await heading('Resumen')
    expect(spies.agent).toHaveBeenCalledWith(expect.objectContaining({
      assistant_name: 'Asistente de Farmasi Iberia', tone: 'formal', instructions: 'Cosmética y bienestar.',
    }))
    expect(await screen.findByText('Agente predeterminado')).toBeInTheDocument()
    expect(screen.getByText('Cuenta del cliente').parentElement).toHaveTextContent('Revisar')
    expect(screen.getByText(/conéctalo a mano en Canales/)).toBeInTheDocument()
  })

  it('exige los datos obligatorios de la empresa', async () => {
    const admin = api()
    const create = vi.spyOn(admin, 'createTenant')
    renderApp('/onboarding', fakeAuthApi(makeUser('admin')), admin)
    await heading('Empresa')
    await next()
    expect(screen.getByText('El nombre es obligatorio.')).toBeInTheDocument()
    expect(screen.getAllByText('Escribe un email válido.')).toHaveLength(2)
    expect(create).not.toHaveBeenCalled()
  })

  it('retoma un cliente en el primer paso pendiente', async () => {
    const admin = api()
    await admin.updateTenantBilling('t1', { billing_email: 'f@clinica.com' })
    // t1 ya tiene plan (mock), proyecto y agente: todo hecho -> resumen.
    renderApp('/onboarding?tenant=t1', fakeAuthApi(makeUser('admin')), admin)
    await heading('Resumen')
    expect(screen.getByText('Paso 5 de 5')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Atrás' }))
    await heading('Agente')
    expect(await screen.findByText(/ya tiene el agente Recepción/)).toBeInTheDocument()
  })

  it('el agente se puede crear tal cual: nombre y texto de partida con el nombre de la empresa', async () => {
    const admin = api()
    await admin.updateTenantBilling('t3', { billing_email: 'f@aurora.com' })
    await admin.putSubscription('t3', { plan_id: 'plan-pro', overage_mode: null, spending_cap_micros: null })
    await admin.createProject({ tenant_id: 't3', name: 'Tienda', slug: 'tienda' })
    const agent = vi.spyOn(admin, 'createBaseAgent')
    renderApp('/onboarding?tenant=t3', fakeAuthApi(makeUser('admin')), admin)

    await heading('Agente')
    expect(await screen.findByDisplayValue('Asistente de Tienda Aurora')).toBeInTheDocument()
    await next()

    await heading('Resumen')
    const [input] = agent.mock.calls[0]!
    expect(input.assistant_name).toBe('Asistente de Tienda Aurora')
    expect(input.instructions).toContain('Formas parte del equipo de atención de Tienda Aurora.')
    expect(input.instructions).toContain('ofrece que una persona del equipo le contacte')
  })

  it('un tenant sin facturación retoma en Empresa con solo los datos de facturación', async () => {
    renderApp('/onboarding?tenant=t2', fakeAuthApi(makeUser('admin')), api())
    await heading('Empresa')
    expect(screen.getByText(/La empresa ya está creada/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Email de acceso a la consola')).not.toBeInTheDocument()
  })

  it('en Tenants: el admin tiene el acceso al wizard y la checklist; el gestor solo la checklist', async () => {
    const { unmount } = renderApp('/tenants', fakeAuthApi(makeUser('admin')), api())
    expect(await screen.findByRole('link', { name: 'Alta de cliente' })).toHaveAttribute('href', '/onboarding')
    expect(await screen.findByText('Puesta en marcha')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Continuar alta' })).toHaveAttribute('href', expect.stringContaining('/onboarding?tenant='))
    expect(screen.getByText('Falta el email de facturación.')).toBeInTheDocument()
    unmount()

    renderApp('/tenants', fakeAuthApi(makeUser('tenant_manager')), api())
    expect(await screen.findByText('Puesta en marcha')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Alta de cliente' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Continuar alta' })).not.toBeInTheDocument()
  })
})
