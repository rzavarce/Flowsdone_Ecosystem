import { ApiError } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import type {
  ChannelConnection,
  Conversation,
  ConversationMessage,
  CostRate,
  Plan,
  Project,
  Statement,
  StatementChannel,
  Subscription,
  TenantRecord,
} from './types'

/** The conversations/billing slice of {@link AdminApi}, implemented by the mock. */
export type BillingApi = Pick<
  AdminApi,
  | 'listConversations'
  | 'getConversation'
  | 'listPlans'
  | 'createPlan'
  | 'updatePlan'
  | 'deletePlan'
  | 'getPlanPricingInsight'
  | 'listCostRates'
  | 'createCostRate'
  | 'deleteCostRate'
  | 'listUnratedMeters'
  | 'getSubscription'
  | 'putSubscription'
  | 'deleteSubscription'
  | 'getStatement'
  | 'listStatements'
>

/** Live data the billing mock reads from (shared with the rest of the mock adapter). */
export interface MockBillingSources {
  latencyMs: number
  tenants: TenantRecord[]
  projects: Project[]
  connections: ChannelConnection[]
}

const DAY = 24 * 3600 * 1000
const BASE = Date.parse('2026-09-20T10:00:00Z')
const iso = (ms: number) => new Date(ms).toISOString()
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T
const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/** Demo exchanges, cycled over the generated conversations. */
const SCRIPTS: [string, string][][] = [
  [
    ['Hola, ¿tienen hora para mañana?', 'Hola 👋 Sí, mañana hay hueco a las 10:00 y a las 16:30. ¿Cuál prefieres?'],
    ['A las 10, por favor', 'Perfecto, te reservo mañana a las 10:00. ¿Me confirmas tu nombre completo?'],
  ],
  [
    ['¿Cuál es el precio del piso de la calle Mayor?', 'El piso de la calle Mayor está en 245.000 €. ¿Quieres agendar una visita?'],
  ],
  [
    ['Mi pedido no ha llegado', 'Siento la espera. ¿Me indicas el número de pedido para revisarlo?'],
    ['Es el 48213', 'Gracias. El pedido 48213 salió ayer y llegará mañana antes de las 14:00.'],
    ['Genial, gracias', '¡A ti! Si necesitas algo más, aquí estoy.'],
  ],
]

/**
 * Creates the conversations/billing half of the mock adapter: a few
 * conversations per channel connection (with transcripts), two plans, one
 * subscription on the first tenant and a small cost catalog. Statements are
 * computed from the conversations, like the gateway does from usage.
 */
export function createMockBilling({ latencyMs, tenants, projects, connections }: MockBillingSources): BillingApi {
  let seq = 500
  const conversations: Conversation[] = []
  const transcripts = new Map<string, ConversationMessage[]>()

  connections.forEach((connection, ci) => {
    const project = projects.find((p) => p.id === connection.project_id)
    if (!project) return
    for (let k = 0; k < 3; k++) {
      const script = SCRIPTS[(ci + k) % SCRIPTS.length]!
      const start = BASE - (ci * 3 + k) * 5 * 3600 * 1000
      const messages: ConversationMessage[] = []
      script.forEach(([question, answer], turn) => {
        const at = start + turn * 90_000
        messages.push({ message_id: `m-${++seq}`, timestamp: iso(at), direction: 'inbound', sender_type: 'contact', app: 'langflow', text: question, billable: true })
        messages.push({ message_id: `m-${++seq}`, timestamp: iso(at + 4000), direction: 'outbound', sender_type: 'bot', app: 'langflow', text: answer, billable: true })
      })
      const last = Date.parse(messages[messages.length - 1]!.timestamp)
      const closed = k === 2
      const id = `conv-${connection.id}-${k}`
      conversations.push({
        id,
        tenant_id: project.tenant_id,
        project_id: project.id,
        agent_id: connection.agent_id,
        channel_type: connection.channel_type,
        channel_connection_id: connection.id,
        contact: connection.channel_type === 'telegram' ? `@usuario${ci}${k}` : `+34 6${ci}${k} 123 45${k}`,
        status: closed ? 'closed' : 'open',
        started_at: iso(start),
        last_inbound_at: messages.filter((m) => m.direction === 'inbound').at(-1)!.timestamp,
        last_message_at: iso(last),
        inbound_count: script.length,
        outbound_count: script.length,
        closed_at: closed ? iso(last + DAY) : null,
        close_reason: closed ? 'inactivity' : null,
      })
      transcripts.set(id, messages)
    }
  })

  const plans: Plan[] = [
    {
      id: 'plan-starter', code: 'starter', name: 'Starter', description: 'Para empezar con un canal.',
      monthly_fee_micros: 29_000_000, currency: 'EUR', included_messages: { '*': 500 }, overage_price_micros: { '*': 30_000 },
      margin_pct: '40.00', allowed_models: ['gpt-4.1-mini*'], monthly_token_allowance: 2_000_000,
      default_overage_mode: 'hard_stop', active: true, subscriptions: 0, created_at: iso(BASE), updated_at: iso(BASE),
    },
    {
      id: 'plan-pro', code: 'pro', name: 'Pro', description: 'Varios canales con excedente.',
      monthly_fee_micros: 99_000_000, currency: 'EUR', included_messages: { whatsapp_evolution: 3000, '*': 1000 },
      overage_price_micros: { whatsapp_evolution: 20_000, '*': 25_000 }, margin_pct: '35.00', allowed_models: [],
      monthly_token_allowance: null, default_overage_mode: 'overage', active: true, subscriptions: 0,
      created_at: iso(BASE), updated_at: iso(BASE),
    },
  ]
  const subscriptions = new Map<string, Subscription>()
  if (tenants[0]) {
    subscriptions.set(tenants[0].id, {
      tenant_id: tenants[0].id, plan_id: 'plan-pro', plan_code: 'pro', plan_name: 'Pro', overage_mode: null,
      effective_overage_mode: 'overage', spending_cap_micros: 50_000_000, started_at: iso(BASE - 60 * DAY), updated_at: null,
    })
  }
  const rates: CostRate[] = [
    { id: 'rate-1', kind: 'llm', provider: 'openai', sku: 'gpt-4.1-mini*', unit: 'input_token', price_micros: 370_000, per_quantity: 1_000_000, currency: 'EUR', valid_from: '2026-01-01T00:00:00Z', note: 'Precio de lista', created_at: iso(BASE) },
    { id: 'rate-2', kind: 'llm', provider: 'openai', sku: 'gpt-4.1-mini*', unit: 'output_token', price_micros: 1_480_000, per_quantity: 1_000_000, currency: 'EUR', valid_from: '2026-01-01T00:00:00Z', note: 'Precio de lista', created_at: iso(BASE) },
    { id: 'rate-3', kind: 'channel', provider: 'whatsapp_evolution', sku: '*', unit: 'message', price_micros: 0, per_quantity: 1, currency: 'EUR', valid_from: '2026-01-01T00:00:00Z', note: 'Evolution: sin coste por mensaje', created_at: iso(BASE) },
  ]

  const need = <T,>(item: T | undefined, what: string): T => {
    if (!item) throw new ApiError(404, `${what} not found`)
    return item
  }
  const withCount = (plan: Plan): Plan => ({
    ...plan,
    subscriptions: [...subscriptions.values()].filter((s) => s.plan_id === plan.id).length,
  })
  const planFor = (id: string) => plans.find((p) => p.id === id)
  const included = (plan: Plan, channel: string) => plan.included_messages[channel] ?? plan.included_messages['*'] ?? 0
  const overagePrice = (plan: Plan, channel: string) => plan.overage_price_micros[channel] ?? plan.overage_price_micros['*'] ?? null

  function statement(tenantId: string, period: string): Statement {
    const sub = subscriptions.get(tenantId)
    const plan = sub ? planFor(sub.plan_id) : undefined
    const messages = new Map<string, number>()
    for (const c of conversations) {
      if (c.tenant_id === tenantId && c.started_at.startsWith(period)) {
        // Escala la demo a un volumen de mes realista.
        messages.set(c.channel_type, (messages.get(c.channel_type) ?? 0) + c.inbound_count * 420)
      }
    }
    const channels: StatementChannel[] = [...messages].map(([channel, used]) => {
      const inc = plan ? included(plan, channel) : 0
      const over = plan ? Math.max(0, used - inc) : 0
      const price = plan ? overagePrice(plan, channel) : null
      return {
        channel_type: channel, messages: used, included: inc, overage_messages: over,
        overage_price_micros: price, overage_amount_micros: over * (price ?? 0), cost_micros: used * 1_150,
      }
    })
    const fee = plan?.monthly_fee_micros ?? 0
    const overage = channels.reduce((sum, c) => sum + c.overage_amount_micros, 0)
    const cost = channels.reduce((sum, c) => sum + (c.cost_micros ?? 0), 0)
    const revenue = fee + overage
    return {
      tenant_id: tenantId, period, status: 'preview', currency: 'EUR', plan_id: plan?.id ?? null,
      plan_code: plan?.code ?? null, plan_name: plan?.name ?? null, overage_mode: sub?.effective_overage_mode ?? null,
      monthly_fee_micros: fee, channels, costs: null, overage_amount_micros: overage, revenue_micros: revenue,
      cost_micros: cost, margin_micros: revenue - cost, margin_pct: revenue ? ((100 * (revenue - cost)) / revenue).toFixed(1) : null,
      llm_input_tokens: channels.reduce((s, c) => s + c.messages * 560, 0),
      llm_output_tokens: channels.reduce((s, c) => s + c.messages * 60, 0), llm_cached_input_tokens: 0,
      token_allowance: plan?.monthly_token_allowance ?? null, over_token_allowance: false, disallowed_models: [],
      unrated_meters: 0, generated_at: new Date().toISOString(),
    }
  }

  return {
    async listConversations(filters = {}) {
      await wait(latencyMs)
      const contact = filters.contact?.toLowerCase()
      return clone(
        conversations
          .filter((c) => !filters.tenant_id || c.tenant_id === filters.tenant_id)
          .filter((c) => !filters.project_id || c.project_id === filters.project_id)
          .filter((c) => !filters.channel_type || c.channel_type === filters.channel_type)
          .filter((c) => !filters.status || c.status === filters.status)
          .filter((c) => !contact || c.contact.toLowerCase().includes(contact))
          .filter((c) => !filters.before || c.last_message_at < filters.before)
          .sort((a, b) => b.last_message_at.localeCompare(a.last_message_at))
          .slice(0, filters.limit ?? 50),
      )
    },
    async getConversation(id) {
      await wait(latencyMs)
      const conversation = need(conversations.find((c) => c.id === id), 'conversation')
      const messages = transcripts.get(id) ?? []
      const inbound = messages.filter((m) => m.direction === 'inbound').length
      return clone({
        conversation,
        messages,
        usage: [
          { kind: 'channel', provider: conversation.channel_type, sku: 'message.inbound', unit: 'message', channel_type: conversation.channel_type, quantity: String(inbound), cost_micros: 0, rated: true },
          { kind: 'llm', provider: 'openai', sku: 'gpt-4.1-mini-2025-04-14', unit: 'input_token', channel_type: conversation.channel_type, quantity: String(inbound * 560), cost_micros: inbound * 207, rated: true },
          { kind: 'llm', provider: 'openai', sku: 'gpt-4.1-mini-2025-04-14', unit: 'output_token', channel_type: conversation.channel_type, quantity: String(inbound * 60), cost_micros: inbound * 89, rated: true },
        ],
        cost_micros: inbound * 296,
        llm_input_tokens: inbound * 560,
        llm_output_tokens: inbound * 60,
        llm_cached_input_tokens: 0,
      })
    },

    async listPlans() {
      await wait(latencyMs)
      return clone(plans.map(withCount))
    },
    async createPlan(input) {
      await wait(latencyMs)
      if (plans.some((p) => p.code === input.code)) throw new ApiError(409, 'already exists')
      const now = new Date().toISOString()
      const plan: Plan = {
        id: `plan-${++seq}`, description: null, monthly_fee_micros: 0, currency: 'EUR', included_messages: {},
        overage_price_micros: {}, margin_pct: '30', allowed_models: [], monthly_token_allowance: null,
        default_overage_mode: 'notify', active: true, subscriptions: 0, created_at: now, updated_at: now, ...input,
      }
      plans.push(plan)
      return clone(withCount(plan))
    },
    async updatePlan(id, patch) {
      await wait(latencyMs)
      const plan = need(planFor(id), 'plan')
      if (patch.code && plans.some((p) => p.id !== id && p.code === patch.code)) throw new ApiError(409, 'already exists')
      Object.assign(plan, patch, { updated_at: new Date().toISOString() })
      return clone(withCount(plan))
    },
    async deletePlan(id) {
      await wait(latencyMs)
      need(planFor(id), 'plan')
      if ([...subscriptions.values()].some((s) => s.plan_id === id)) throw new ApiError(409, 'plan in use')
      plans.splice(plans.findIndex((p) => p.id === id), 1)
    },
    async getPlanPricingInsight(id, days = 30) {
      await wait(latencyMs)
      const plan = need(planFor(id), 'plan')
      const channels = [...new Set([...Object.keys(plan.included_messages), ...Object.keys(plan.overage_price_micros)])]
        .filter((c) => c !== '*')
        .concat(['whatsapp_evolution', 'telegram'])
      const factor = 1 + Number(plan.margin_pct) / 100
      return {
        plan_id: id, margin_pct: plan.margin_pct, days, sample: 'platform',
        channels: [...new Set(channels)].sort().map((channel) => {
          const avg = channel === 'telegram' ? 980 : 1_150
          const configured = overagePrice(plan, channel)
          return {
            channel_type: channel, messages: 1200, avg_cost_micros: avg, suggested_price_micros: Math.round(avg * factor),
            configured_price_micros: configured,
            margin_at_configured_pct: configured === null ? null : ((100 * (configured - avg)) / avg).toFixed(1),
          }
        }),
      }
    },

    async listCostRates() {
      await wait(latencyMs)
      return clone(rates)
    },
    async createCostRate(input) {
      await wait(latencyMs)
      const now = new Date().toISOString()
      const rate: CostRate = { id: `rate-${++seq}`, currency: 'EUR', created_at: now, note: null, ...input, valid_from: input.valid_from ?? now }
      rates.unshift(rate)
      return clone(rate)
    },
    async deleteCostRate(id) {
      await wait(latencyMs)
      need(rates.find((r) => r.id === id), 'cost rate')
      rates.splice(rates.findIndex((r) => r.id === id), 1)
    },
    async listUnratedMeters() {
      await wait(latencyMs)
      const covered = rates.some((r) => r.kind === 'channel' && r.provider === 'telegram')
      return covered ? [] : [{ kind: 'channel', provider: 'telegram', sku: 'message.outbound', unit: 'message', quantity: '1840' }]
    },

    async getSubscription(tenantId) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      return clone(subscriptions.get(tenantId) ?? null)
    },
    async putSubscription(tenantId, input) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      const plan = planFor(input.plan_id)
      if (!plan || !plan.active) throw new ApiError(400, 'plan not found or inactive')
      const current = subscriptions.get(tenantId)
      const subscription: Subscription = {
        tenant_id: tenantId, plan_id: plan.id, plan_code: plan.code, plan_name: plan.name,
        overage_mode: input.overage_mode ?? null, effective_overage_mode: input.overage_mode ?? plan.default_overage_mode,
        spending_cap_micros: input.spending_cap_micros ?? null, started_at: current?.started_at ?? new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      subscriptions.set(tenantId, subscription)
      return clone(subscription)
    },
    async deleteSubscription(tenantId) {
      await wait(latencyMs)
      if (!subscriptions.delete(tenantId)) throw new ApiError(404, 'no subscription')
    },
    async getStatement(tenantId, period) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      return statement(tenantId, period ?? new Date().toISOString().slice(0, 7))
    },
    async listStatements(tenantId) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      return subscriptions.has(tenantId) ? [{ ...statement(tenantId, '2026-08'), status: 'closed' as const }] : []
    },
  }
}
