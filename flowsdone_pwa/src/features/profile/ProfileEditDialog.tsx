import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import type { ProfileUpdate } from '@/core/auth/types'
import { useAuth } from '@/core/auth/useAuth'
import { describeError } from '@/core/http/describeError'
import { cleanLinks, profileFieldsErrors, type ProfileFieldsValue } from '@/lib/profile'
import { AvatarField } from './AvatarField'
import { ProfileFieldsInputs } from './ProfileFieldsInputs'

/** Which part of the profile the dialog edits. */
export type ProfileSection = 'photo' | 'personal' | 'address' | 'social'

/** Props for {@link ProfileEditDialog}. */
export interface ProfileEditDialogProps {
  section: ProfileSection
  onClose: () => void
}

const FORM_ID = 'profile-edit-form'

/**
 * Edits one section of the signed-in user's own profile (`PATCH /me/profile`,
 * or `PUT/DELETE /me/avatar` for the photo, which saves as soon as it's picked).
 * Mounted only while open, so it always starts from the current values.
 */
export function ProfileEditDialog({ section, onClose }: ProfileEditDialogProps) {
  const { t } = useTranslation()
  const { user, avatarUrl, updateProfile, uploadAvatar, removeAvatar } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [fields, setFields] = useState<ProfileFieldsValue>({
    phone: user?.phone ?? '',
    address: user?.address ?? '',
    social_links: { ...user?.social_links },
  })
  const [submitted, setSubmitted] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!user) return null

  const nameError = section === 'personal' && !name.trim() ? t('common.nameRequired') : undefined
  const invalid = Boolean(nameError) || Object.keys(profileFieldsErrors(fields)).length > 0

  async function run(action: () => Promise<unknown>, closeAfter: boolean) {
    setPending(true)
    setError(null)
    try {
      await action()
      if (closeAfter) onClose()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setPending(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (invalid) return
    const patch: ProfileUpdate =
      section === 'personal'
        ? { name: name.trim(), phone: fields.phone.trim() }
        : section === 'address'
          ? { address: fields.address.trim() }
          : { social_links: cleanLinks(fields.social_links) }
    void run(() => updateProfile(patch), true)
  }

  const photo = section === 'photo'
  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={t(`profile.sections.${section}`)}
      description={t(`profile.edit.${section}`)}
      footer={
        photo ? (
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.close')}
          </Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose} disabled={pending}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" form={FORM_ID} disabled={pending}>
              {pending ? t('common.saving') : t('common.saveChanges')}
            </Button>
          </>
        )
      }
    >
      {photo ? (
        <AvatarField
          name={user.name}
          src={avatarUrl}
          pending={pending}
          error={error}
          onPick={(image) => void run(() => uploadAvatar(image), false)}
          onRemove={() => void run(() => removeAvatar(), false)}
        />
      ) : (
        <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
          {section === 'personal' && (
            <Field label={t('profile.fields.fullName')} error={submitted ? nameError : undefined}>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </Field>
          )}
          <ProfileFieldsInputs
            value={fields}
            onChange={setFields}
            showErrors={submitted}
            parts={section === 'personal' ? ['phone'] : section === 'address' ? ['address'] : ['social']}
          />
          {error && <Alert tone="danger">{error}</Alert>}
        </form>
      )}
    </Dialog>
  )
}
