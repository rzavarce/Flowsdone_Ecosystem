import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useDeferredValue, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAgents, useChannelConnections, useProjects, useUsers } from '@/core/admin/hooks'
import { useAdminApi } from '@/core/admin/useAdminApi'
import { ALL_TENANTS } from '@/core/tenant/TenantContext'
import { useTenant } from '@/core/tenant/useTenant'
import { channelLabel } from '@/features/billing/labels'
import { cn } from '@/lib/cn'
import { matchesQuery } from '@/lib/search'
import { useNavItems } from './useNavItems'
import { useSearchScope } from './useSearchScope'

/** Minimum characters before searching. */
const SEARCH_MIN_CHARS = 2
/** Maximum results shown per group. */
const PER_GROUP = 5

type Group = 'pages' | 'tenants' | 'conversations' | 'users' | 'agents' | 'channels'

/** One search hit: what to show and where it leads. */
interface Hit {
  key: string
  group: Group
  label: string
  detail?: string
  /** Tenant to activate in the top bar before navigating (`ALL_TENANTS` for "all"). */
  tenantId?: string
  to: string
}

/**
 * Collects the hits for `query` from everything the profile can see:
 * menu sections, tenants, conversations (by contact, asked to the API),
 * users (name/email), agents and channels. Lists are only loaded once the
 * search is in use (`active`) and are shared with the screens' own caches.
 *
 * Args:
 *   query: Text typed (already trimmed/deferred).
 *   active: Whether the search box has been used, to avoid loading lists before.
 *
 * Returns:
 *   The hits in display order and whether any source is still loading.
 */
function useSearchHits(query: string, active: boolean): { hits: Hit[]; loading: boolean } {
  const scope = useSearchScope()
  const api = useAdminApi()
  const pages = useNavItems()
  const { tenants, canSelectAll } = useTenant()
  const ready = query.length >= SEARCH_MIN_CHARS

  const users = useUsers(active && scope.users)
  const agents = useAgents(active && scope.agents)
  const channels = useChannelConnections(active && scope.channels)
  const projects = useProjects(undefined, active && (scope.agents || scope.channels))
  const conversations = useQuery({
    queryKey: ['global-search', 'conversations', query],
    queryFn: () => api.listConversations({ contact: query, limit: PER_GROUP }),
    enabled: ready && scope.conversations,
    staleTime: 30_000,
  })

  const hits = useMemo(() => {
    if (!ready) return []
    const tenantName = new Map(tenants.map((t) => [t.id, t.name]))
    const projectTenant = new Map((projects.data ?? []).map((p) => [p.id, p.tenant_id]))
    const agentName = new Map((agents.data ?? []).map((a) => [a.id, a.name]))
    const out: Hit[] = []
    const push = (items: Hit[]) => out.push(...items.slice(0, PER_GROUP))

    push(
      pages
        .filter((p) => matchesQuery(query, p.label))
        .map((p) => ({ key: `page:${p.to}`, group: 'pages', label: p.label, to: p.to })),
    )
    if (scope.tenants) {
      push(
        tenants
          .filter((t) => matchesQuery(query, t.name))
          .map((t) => ({ key: `tenant:${t.id}`, group: 'tenants', label: t.name, tenantId: t.id, to: '/tenants' })),
      )
    }
    if (scope.conversations) {
      push(
        (conversations.data ?? []).map((c) => ({
          key: `conversation:${c.id}`,
          group: 'conversations',
          label: c.contact,
          detail: [channelLabel(c.channel_type), tenantName.get(c.tenant_id)].filter(Boolean).join(' · '),
          tenantId: c.tenant_id,
          to: `/conversations?c=${encodeURIComponent(c.id)}`,
        })),
      )
    }
    if (scope.users) {
      push(
        (users.data ?? [])
          .filter((u) => matchesQuery(query, u.name, u.email))
          .map((u) =>
            // Client accounts are managed from their tenant's screen, staff from Users.
            u.role === 'client' && u.tenant_ids[0]
              ? { key: `user:${u.id}`, group: 'users', label: u.name || u.email, detail: u.email, tenantId: u.tenant_ids[0], to: '/tenants' }
              : {
                  key: `user:${u.id}`,
                  group: 'users',
                  label: u.name || u.email,
                  detail: u.email,
                  tenantId: canSelectAll ? ALL_TENANTS : undefined,
                  to: `/users?q=${encodeURIComponent(u.email)}`,
                },
          ),
      )
    }
    if (scope.agents) {
      push(
        (agents.data ?? [])
          .filter((a) => matchesQuery(query, a.name))
          .map((a) => {
            const tenantId = projectTenant.get(a.project_id)
            return { key: `agent:${a.id}`, group: 'agents', label: a.name, detail: tenantId && tenantName.get(tenantId), tenantId, to: '/agents' }
          }),
      )
    }
    if (scope.channels) {
      push(
        (channels.data ?? [])
          .filter((c) => matchesQuery(query, c.display_name, c.external_id, channelLabel(c.channel_type)))
          .map((c) => {
            const tenantId = projectTenant.get(c.project_id)
            return {
              key: `channel:${c.id}`,
              group: 'channels',
              label: c.display_name || c.external_id,
              detail: [channelLabel(c.channel_type), agentName.get(c.agent_id)].filter(Boolean).join(' · '),
              tenantId,
              to: '/channels',
            }
          }),
      )
    }
    return out
  }, [ready, query, pages, tenants, canSelectAll, scope.tenants, scope.conversations, scope.users, scope.agents, scope.channels, conversations.data, users.data, agents.data, channels.data, projects.data])

  const loading =
    ready &&
    [
      scope.conversations && conversations.isFetching,
      scope.users && users.isPending,
      scope.agents && agents.isPending,
      scope.channels && channels.isPending,
    ].some(Boolean)
  return { hits, loading }
}

/**
 * The top bar's global search: a combobox over everything the profile can
 * see, grouped by kind. ↑/↓ move, Enter opens, Escape closes; Ctrl/⌘+K
 * focuses it from anywhere. Opening a tenant-bound hit also activates its
 * tenant in the top bar, so the destination screen shows it.
 */
export function GlobalSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { select } = useTenant()
  const inputRef = useRef<HTMLInputElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const listId = useId()
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [used, setUsed] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const query = useDeferredValue(text.trim())
  const { hits, loading } = useSearchHits(query, used)

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [])

  const current = Math.min(activeIndex, Math.max(hits.length - 1, 0))

  function go(hit: Hit) {
    if (hit.tenantId) select(hit.tenantId)
    navigate(hit.to)
    setText('')
    setOpen(false)
    inputRef.current?.blur()
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      if (open) setOpen(false)
      else setText('')
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      if (hits.length) setActiveIndex((current + (e.key === 'ArrowDown' ? 1 : hits.length - 1)) % hits.length)
    } else if (e.key === 'Enter' && open && hits[current]) {
      e.preventDefault()
      go(hits[current])
    }
  }

  const showPanel = open && text.trim().length > 0
  const optionId = (i: number) => `${listId}-${i}`

  return (
    <div ref={rootRef} className="relative hidden w-full max-w-[26.875rem] md:block">
      <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" aria-hidden="true" />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-label={t('layout.search')}
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showPanel && hits.length ? optionId(current) : undefined}
        placeholder={t('layout.searchPlaceholder')}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setActiveIndex(0)
          setOpen(true)
          setUsed(true)
        }}
        onFocus={() => {
          setUsed(true)
          setOpen(true)
        }}
        onKeyDown={onKeyDown}
        className="h-11 w-full rounded-lg border border-border bg-transparent py-2.5 pr-16 pl-12 text-sm shadow-theme-xs placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
      />
      <kbd
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 rounded-lg border border-border bg-background px-2 py-1 font-sans text-xs text-muted"
      >
        Ctrl K
      </kbd>

      {showPanel && (
        <div className="absolute top-full right-0 left-0 z-30 mt-2 max-h-[70vh] overflow-y-auto rounded-xl border border-border bg-surface p-2 shadow-theme-lg">
          <ul id={listId} role="listbox" aria-label={t('layout.searchResults')}>
            {hits.map((hit, i) => (
              <li key={hit.key} role="presentation">
                {(i === 0 || hits[i - 1].group !== hit.group) && (
                  <p aria-hidden="true" className="px-3 pt-2 pb-1 text-xs font-medium tracking-wide text-muted uppercase">
                    {t(`layout.searchGroups.${hit.group}`)}
                  </p>
                )}
                <div
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === current}
                  onPointerDown={(e) => e.preventDefault()}
                  onClick={() => go(hit)}
                  onPointerMove={() => setActiveIndex(i)}
                  className={cn('flex cursor-pointer flex-col rounded-lg px-3 py-2 text-sm', i === current && 'bg-surface-muted')}
                >
                  <span className="truncate font-medium">{hit.label}</span>
                  {hit.detail && <span className="truncate text-xs text-muted">{hit.detail}</span>}
                </div>
              </li>
            ))}
          </ul>
          {hits.length === 0 && (
            <p className="px-3 py-2 text-sm text-muted" role="status">
              {query.length < SEARCH_MIN_CHARS
                ? t('layout.searchMin')
                : loading
                  ? t('layout.searching')
                  : t('layout.searchEmpty', { query })}
            </p>
          )}
          {hits.length > 0 && loading && (
            <p className="px-3 pt-1 text-xs text-muted" role="status">
              {t('layout.searching')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
