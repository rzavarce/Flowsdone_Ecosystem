import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ConversationFilters, CostRateInput, PlanInput, Subscription, SubscriptionInput } from './types'
import { invalidateOnboarding } from './hooks'
import { useAdminApi } from './useAdminApi'

/** Cache keys of the conversations and billing screens. */
export const billingKeys = {
  conversations: ['conversations'] as const,
  conversation: ['conversation'] as const,
  plans: ['plans'] as const,
  pricingInsight: ['pricing-insight'] as const,
  costRates: ['cost-rates'] as const,
  unrated: ['unrated-meters'] as const,
  subscription: ['subscription'] as const,
  statement: ['statement'] as const,
  statements: ['statements'] as const,
}

/** Page size of the conversation inbox. */
export const CONVERSATIONS_PAGE = 30

/**
 * Conversation inbox with "load more": each page asks for the conversations
 * whose last activity is older than the last one already shown.
 */
export function useConversations(filters: Omit<ConversationFilters, 'before' | 'limit'>) {
  const api = useAdminApi()
  return useInfiniteQuery({
    queryKey: [...billingKeys.conversations, filters],
    queryFn: ({ pageParam }) => api.listConversations({ ...filters, before: pageParam, limit: CONVERSATIONS_PAGE }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => (last.length < CONVERSATIONS_PAGE ? undefined : last[last.length - 1]!.last_message_at),
  })
}

/** One conversation with its transcript and usage. */
export function useConversation(id?: string) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...billingKeys.conversation, id],
    queryFn: () => api.getConversation(id as string),
    enabled: Boolean(id),
  })
}

/** Commercial plans (admin). */
export function usePlans(enabled = true) {
  const api = useAdminApi()
  return useQuery({ queryKey: billingKeys.plans, queryFn: () => api.listPlans(), enabled })
}

/** Creates or edits a plan (`id` present = edit), then refreshes plans and pricing. */
export function useSavePlan() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id?: string; input: PlanInput }) =>
      id ? api.updatePlan(id, input) : api.createPlan(input as PlanInput & { code: string; name: string }),
    onSuccess: () =>
      Promise.all([billingKeys.plans, billingKeys.pricingInsight, billingKeys.statement].map((queryKey) => qc.invalidateQueries({ queryKey }))),
  })
}

/** Deletes a plan nobody is subscribed to. */
export function useDeletePlan() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deletePlan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: billingKeys.plans }),
  })
}

/** Average cost per message and suggested overage price of a plan. */
export function usePricingInsight(planId?: string, days = 30) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...billingKeys.pricingInsight, planId, days],
    queryFn: () => api.getPlanPricingInsight(planId as string, days),
    enabled: Boolean(planId),
  })
}

/** The cost catalog (admin). */
export function useCostRates() {
  const api = useAdminApi()
  return useQuery({ queryKey: billingKeys.costRates, queryFn: () => api.listCostRates() })
}

/** Meters used recently without a rate (admin). */
export function useUnratedMeters(days = 30) {
  const api = useAdminApi()
  return useQuery({ queryKey: [...billingKeys.unrated, days], queryFn: () => api.listUnratedMeters(days) })
}

/** Invalidates everything a cost rate change affects (costs are computed on read). */
function invalidateCosts(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all(
    [billingKeys.costRates, billingKeys.unrated, billingKeys.pricingInsight, billingKeys.statement, billingKeys.conversation].map(
      (queryKey) => qc.invalidateQueries({ queryKey }),
    ),
  )
}

/** Adds a rate (or a new version of a price). */
export function useCreateCostRate() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({ mutationFn: (input: CostRateInput) => api.createCostRate(input), onSuccess: () => invalidateCosts(qc) })
}

/** Deletes a rate entered by mistake. */
export function useDeleteCostRate() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.deleteCostRate(id), onSuccess: () => invalidateCosts(qc) })
}

/** A tenant's subscription (`null` = none). */
export function useSubscription(tenantId?: string) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...billingKeys.subscription, tenantId],
    queryFn: () => api.getSubscription(tenantId as string),
    enabled: Boolean(tenantId),
  })
}

/** Assigns/changes (input) or removes (`null`) a tenant's plan. */
export function useSaveSubscription() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ tenantId, input }: { tenantId: string; input: SubscriptionInput | null }): Promise<Subscription | null> => {
      if (input) return api.putSubscription(tenantId, input)
      await api.deleteSubscription(tenantId)
      return null
    },
    onSuccess: (_data, { tenantId }) =>
      Promise.all(
        [billingKeys.subscription, billingKeys.statement].map((key) => qc.invalidateQueries({ queryKey: [...key, tenantId] })).concat(
          qc.invalidateQueries({ queryKey: billingKeys.plans }),
          invalidateOnboarding(qc),
        ),
      ),
  })
}

/** A tenant's statement for a month (`YYYY-MM`; current if omitted). */
export function useStatement(tenantId?: string, period?: string) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...billingKeys.statement, tenantId, period ?? 'current'],
    queryFn: () => api.getStatement(tenantId as string, period),
    enabled: Boolean(tenantId),
  })
}
