import { ChevronDown, CircleHelp, CircleUserRound, Globe, LogOut, Settings, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Avatar } from '@/components/ui/Avatar'
import { can, ROLE_META } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { LANGUAGES, currentLanguage } from '@/core/i18n/i18n'
import { cn } from '@/lib/cn'
import { LanguageOptions } from './LanguageMenu'

const ITEM =
  'group flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-foreground/80 transition hover:bg-surface-muted hover:text-foreground'
const ITEM_ICON = 'size-5 shrink-0 text-muted group-hover:text-foreground/80'

/** A link entry of the user dropdown. */
interface MenuLink {
  to: string
  label: string
  icon: LucideIcon
}

/**
 * Top bar avatar + name with a dropdown (TailAdmin style): user header,
 * links to the profile, settings (if allowed) and support (FAQ), the
 * language switcher, and sign out. Closes on outside click, Escape or after
 * choosing an entry.
 */
export function UserMenu() {
  const { t } = useTranslation()
  const { user, avatarUrl, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [languagesOpen, setLanguagesOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null

  const links: MenuLink[] = [
    { to: '/profile', label: t('layout.myProfile'), icon: CircleUserRound },
    ...(can(user, 'settings:view') ? [{ to: '/settings', label: t('nav.settings'), icon: Settings }] : []),
    { to: '/support', label: t('layout.support'), icon: CircleHelp },
  ]
  const language = LANGUAGES.find((l) => l.id === currentLanguage())

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o)
          setLanguagesOpen(false)
        }}
        aria-label={t('layout.userMenu')}
        aria-haspopup="true"
        aria-expanded={open}
        className="flex cursor-pointer items-center gap-3 rounded-full text-foreground/80"
      >
        <Avatar name={user.name} src={avatarUrl} className="size-11 text-sm" />
        <span className="hidden max-w-32 truncate text-sm font-medium xl:block">{user.name.split(' ')[0]}</span>
        <ChevronDown
          className={cn('hidden size-4 text-muted transition-transform duration-200 xl:block', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="absolute top-full right-0 z-30 mt-4 flex w-[16.25rem] flex-col rounded-2xl border border-border bg-surface p-3 shadow-theme-lg">
          <div className="px-1">
            <p className="truncate text-sm font-medium text-foreground/85">{user.name}</p>
            <p className="mt-0.5 truncate text-xs text-muted">{user.email}</p>
            <p className="mt-0.5 truncate text-xs text-muted">{ROLE_META[user.role].label}</p>
          </div>

          <ul className="flex flex-col gap-1 border-b border-border pt-4 pb-3">
            {links.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <Link to={to} onClick={() => setOpen(false)} className={ITEM}>
                  <Icon className={ITEM_ICON} strokeWidth={1.75} aria-hidden="true" />
                  {label}
                </Link>
              </li>
            ))}
            <li>
              <button
                type="button"
                onClick={() => setLanguagesOpen((o) => !o)}
                aria-expanded={languagesOpen}
                className={ITEM}
              >
                <Globe className={ITEM_ICON} strokeWidth={1.75} aria-hidden="true" />
                {t('layout.language')}
                <span className="ml-auto rounded-lg border border-border bg-background px-2 py-0.5 text-xs font-medium text-foreground/80">
                  {language?.name}
                </span>
              </button>
              {languagesOpen && <LanguageOptions onPicked={() => setOpen(false)} />}
            </li>
          </ul>

          <button type="button" onClick={() => void logout()} className={cn(ITEM, 'mt-3')}>
            <LogOut className={ITEM_ICON} strokeWidth={1.75} aria-hidden="true" />
            {t('layout.logout')}
          </button>
        </div>
      )}
    </div>
  )
}
