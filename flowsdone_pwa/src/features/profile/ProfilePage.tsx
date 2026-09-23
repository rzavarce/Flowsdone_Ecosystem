import { Building2, KeyRound, LoaderCircle, LogOut, Pencil } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { SocialIcon } from '@/components/ui/SocialIcon'
import { AuthError } from '@/core/auth/AuthApi'
import { ROLE_META } from '@/core/auth/permissions'
import { SOCIAL_NETWORKS } from '@/core/auth/types'
import { useAuth } from '@/core/auth/useAuth'
import { ProfileEditDialog, type ProfileSection } from './ProfileEditDialog'

/** Inner, bordered block of the profile card (TailAdmin "User Profile" style). */
function Section({ title, action, children }: { title?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border p-5 lg:p-6">
      {(title || action) && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

/** Label/value pair of an info grid; shows a dash when the value is empty. */
function InfoItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="mb-2 text-xs text-muted">{label}</dt>
      <dd className="text-sm font-medium break-words">{children || '—'}</dd>
    </div>
  )
}

/**
 * "My profile": the signed-in user's own account, for every role, in the
 * TailAdmin "User Profile" layout. Each block has an "Edit" button that
 * opens {@link ProfileEditDialog}: photo, name + phone, address and social
 * links are self-service (`/me/profile`, `/me/avatar`); email, role and
 * tenants only change through an admin. The password is changed through
 * the recovery flow (a link emailed to the user's own address).
 */
export function ProfilePage() {
  const { t } = useTranslation()
  const { user, avatarUrl, logout, requestPasswordReset } = useAuth()
  const [editing, setEditing] = useState<ProfileSection | null>(null)
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!user) return null
  const role = ROLE_META[user.role]
  const links = SOCIAL_NETWORKS.filter((n) => user.social_links?.[n])

  const editButton = (section: ProfileSection) => (
    <Button variant="secondary" size="sm" onClick={() => setEditing(section)} aria-label={t('profile.editSection', { section: t(`profile.sections.${section}`) })}>
      <Pencil className="size-4" aria-hidden="true" />
      {t('common.edit')}
    </Button>
  )

  async function sendPasswordLink() {
    if (!user) return
    setPending(true)
    setError(null)
    try {
      await requestPasswordReset(user.email)
      setSent(true)
    } catch (err) {
      setError(err instanceof AuthError ? err.message : t('common.unexpectedError'))
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <PageHeader title={t('profile.title')} />
      <Card className="space-y-6 p-5 lg:p-6">
        <h2 className="text-lg font-semibold">{t('profile.account')}</h2>

        <Section>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-col items-center gap-5 sm:flex-row">
              <Avatar name={user.name} src={avatarUrl} className="size-20 text-xl" />
              <div className="text-center sm:text-left">
                <p className="text-lg font-semibold">{user.name}</p>
                <div className="mt-2 flex flex-col items-center gap-1 text-sm text-muted sm:flex-row sm:gap-3">
                  <span>{role.label}</span>
                  <span className="hidden h-3.5 w-px bg-border sm:block" aria-hidden="true" />
                  <span>{user.email}</span>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {links.length > 0 && (
                <ul className="flex items-center gap-2" aria-label={t('profile.fields.social')}>
                  {links.map((network) => (
                    <li key={network}>
                      <a
                        href={user.social_links?.[network]}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={t(`profile.networks.${network}`)}
                        className="inline-flex size-11 items-center justify-center rounded-full border border-border text-foreground/70 shadow-theme-xs transition hover:bg-surface-muted hover:text-foreground"
                      >
                        <SocialIcon network={network} />
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {editButton('photo')}
            </div>
          </div>
        </Section>

        <Section title={t('profile.sections.personal')} action={editButton('personal')}>
          <dl className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
            <InfoItem label={t('profile.fields.fullName')}>{user.name}</InfoItem>
            <InfoItem label={t('auth.email')}>{user.email}</InfoItem>
            <InfoItem label={t('profile.fields.phone')}>{user.phone}</InfoItem>
            <InfoItem label={t('profile.fields.role')}>{role.label}</InfoItem>
          </dl>
          <p className="mt-6 text-xs text-muted">{t('profile.adminOnly')}</p>
        </Section>

        <Section title={t('profile.sections.address')} action={editButton('address')}>
          <dl>
            <InfoItem label={t('profile.fields.address')}>{user.address}</InfoItem>
          </dl>
        </Section>

        <Section title={t('profile.sections.social')} action={editButton('social')}>
          {links.length === 0 ? (
            <p className="text-sm text-muted">{t('profile.noLinks')}</p>
          ) : (
            <dl className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
              {links.map((network) => (
                <InfoItem key={network} label={t(`profile.networks.${network}`)}>
                  <a href={user.social_links?.[network]} target="_blank" rel="noopener noreferrer" className="text-primary-ink hover:underline">
                    {user.social_links?.[network]}
                  </a>
                </InfoItem>
              ))}
            </dl>
          )}
        </Section>

        <Section title={t('profile.sections.tenants')}>
          {user.tenants.length === 0 ? (
            <p className="text-sm text-muted">{t('profile.noTenants')}</p>
          ) : (
            <ul className="flex flex-wrap gap-2" aria-label={t('profile.tenantsList')}>
              {user.tenants.map((tenant) => (
                <li key={tenant.id}>
                  <Badge tone="neutral" className="px-3 py-1 text-sm">
                    <Building2 className="size-3.5" aria-hidden="true" />
                    {tenant.name}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title={t('profile.sections.security')}>
          <div className="divide-y divide-border">
            <div className="flex flex-wrap items-center justify-between gap-4 pb-5">
              <div>
                <p className="font-medium">{t('profile.password.title')}</p>
                <p className="mt-1 text-sm text-muted">{t('profile.password.description', { email: user.email })}</p>
              </div>
              <Button variant="secondary" onClick={() => void sendPasswordLink()} disabled={pending || sent}>
                {pending ? (
                  <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <KeyRound className="size-4" aria-hidden="true" />
                )}
                {sent ? t('profile.password.sent') : t('profile.password.title')}
              </Button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4 pt-5">
              <div>
                <p className="font-medium">{t('profile.session.title')}</p>
                <p className="mt-1 text-sm text-muted">{t('profile.session.description')}</p>
              </div>
              <Button variant="secondary" onClick={() => void logout()}>
                <LogOut className="size-4" aria-hidden="true" />
                {t('layout.logout')}
              </Button>
            </div>
          </div>
          {sent && (
            <Alert tone="success" className="mt-5" onDismiss={() => setSent(false)}>
              {t('profile.password.checkEmail')}
            </Alert>
          )}
          {error && (
            <Alert tone="danger" className="mt-5">
              {error}
            </Alert>
          )}
        </Section>
      </Card>
      {editing && <ProfileEditDialog section={editing} onClose={() => setEditing(null)} />}
    </>
  )
}
