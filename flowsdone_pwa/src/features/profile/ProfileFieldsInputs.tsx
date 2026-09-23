import { useTranslation } from 'react-i18next'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { SOCIAL_NETWORKS, type SocialNetwork } from '@/core/auth/types'
import { MAX_ADDRESS, profileFieldsErrors, type ProfileFieldsPart, type ProfileFieldsValue } from '@/lib/profile'

/** Props for {@link ProfileFieldsInputs}. */
export interface ProfileFieldsInputsProps {
  value: ProfileFieldsValue
  onChange: (value: ProfileFieldsValue) => void
  /** Show validation errors (after the first submit). */
  showErrors?: boolean
  /** Blocks to render; all of them by default. */
  parts?: ProfileFieldsPart[]
}

/**
 * Inputs for phone, address and social links - all optional. Shared by
 * "My profile" and the admin's user dialog.
 */
export function ProfileFieldsInputs({ value, onChange, showErrors, parts = ['phone', 'address', 'social'] }: ProfileFieldsInputsProps) {
  const { t } = useTranslation()
  const errors = showErrors ? profileFieldsErrors(value) : {}
  const err = (key: string) => (errors[key] ? t(errors[key] as 'profile.errors.url') : undefined)
  const setLink = (network: SocialNetwork, url: string) =>
    onChange({ ...value, social_links: { ...value.social_links, [network]: url } })

  return (
    <>
      {parts.includes('phone') && (
        <Field label={t('profile.fields.phone')} hint={t('common.optional')} error={err('phone')}>
          <Input type="tel" value={value.phone} onChange={(e) => onChange({ ...value, phone: e.target.value })} placeholder="+34 600 000 000" autoComplete="tel" />
        </Field>
      )}
      {parts.includes('address') && (
        <Field label={t('profile.fields.address')} hint={t('common.optional')} error={err('address')}>
          <Input
            value={value.address}
            onChange={(e) => onChange({ ...value, address: e.target.value })}
            placeholder={t('profile.fields.addressPlaceholder')}
            autoComplete="street-address"
            maxLength={MAX_ADDRESS}
          />
        </Field>
      )}
      {parts.includes('social') && (
        <fieldset className="space-y-3">
          <legend className="mb-2 text-sm font-medium text-foreground/80">{t('profile.fields.social')}</legend>
          {SOCIAL_NETWORKS.map((network) => (
            <Field key={network} label={t(`profile.networks.${network}`)} error={err(network)}>
              <Input
                type="url"
                value={value.social_links[network] ?? ''}
                onChange={(e) => setLink(network, e.target.value)}
                placeholder={t(`profile.placeholders.${network}`)}
                autoComplete="url"
              />
            </Field>
          ))}
        </fieldset>
      )}
    </>
  )
}

