import { Camera, LoaderCircle, Trash2 } from 'lucide-react'
import { useId, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { AvatarFileError, prepareAvatar } from '@/lib/resizeImage'

/** Props for {@link AvatarField}. */
export interface AvatarFieldProps {
  name: string
  /** Current photo URL, if any. */
  src: string | null
  /** While an upload/removal is in flight. */
  pending?: boolean
  /** Error from the server, already described. */
  error?: string | null
  /** Receives the photo already cropped/downsized to a small square JPEG. */
  onPick: (image: Blob) => void
  onRemove: () => void
}

/**
 * Profile photo with "Change photo" / "Remove photo". The picked file is
 * validated and downsized in the browser (see `prepareAvatar`), so only a few
 * KB are uploaded. Shared by "My profile" and the admin's user dialog.
 */
export function AvatarField({ name, src, pending, error, onPick, onRemove }: AvatarFieldProps) {
  const { t } = useTranslation()
  const inputId = useId()
  const [fileError, setFileError] = useState<string | null>(null)

  async function onChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // permite volver a elegir el mismo archivo
    if (!file) return
    setFileError(null)
    try {
      onPick(await prepareAvatar(file))
    } catch (err) {
      setFileError(t(`profile.avatar.errors.${err instanceof AvatarFileError ? err.reason : 'decode'}`))
    }
  }

  const shown = fileError ?? error
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Avatar name={name} src={src} className="size-20 text-xl" />
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <label
            htmlFor={inputId}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg bg-surface px-3.5 text-sm font-medium text-foreground/85 shadow-theme-xs ring-1 ring-input ring-inset transition hover:bg-surface-muted has-[:disabled]:pointer-events-none has-[:disabled]:opacity-50"
          >
            {pending ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Camera className="size-4" aria-hidden="true" />}
            {src ? t('profile.avatar.change') : t('profile.avatar.upload')}
            <input
              id={inputId}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => void onChange(e)}
              disabled={pending}
            />
          </label>
          {src && (
            <Button variant="ghost" size="sm" onClick={onRemove} disabled={pending}>
              <Trash2 className="size-4" aria-hidden="true" />
              {t('profile.avatar.remove')}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted">{t('profile.avatar.hint')}</p>
        {shown && (
          <p role="alert" className="text-xs text-danger">
            {shown}
          </p>
        )}
      </div>
    </div>
  )
}
