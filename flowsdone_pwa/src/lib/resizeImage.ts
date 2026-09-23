/** Side of the square photo that gets uploaded, in px. */
export const AVATAR_SIZE = 256

/** Biggest file accepted from the device before resizing (the upload itself is a few KB). */
export const MAX_SOURCE_BYTES = 10 * 1024 * 1024

/** Why a picked file can't be used as a photo. */
export class AvatarFileError extends Error {
  readonly reason: 'type' | 'size' | 'decode'

  constructor(reason: 'type' | 'size' | 'decode') {
    super(reason)
    this.name = 'AvatarFileError'
    this.reason = reason
  }
}

/**
 * Checks a picked file before decoding it.
 *
 * @param file - What the user selected.
 * @throws AvatarFileError `type` if it isn't a JPEG/PNG/WebP image, `size` if over {@link MAX_SOURCE_BYTES}.
 */
export function assertAvatarFile(file: File): void {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new AvatarFileError('type')
  if (file.size > MAX_SOURCE_BYTES) throw new AvatarFileError('size')
}

/**
 * Center-crops and downsizes a photo to an {@link AVATAR_SIZE}-px square JPEG,
 * so what travels and gets stored is a few KB whatever the camera produced.
 *
 * @param file - A JPEG/PNG/WebP image.
 * @returns The JPEG to upload.
 * @throws AvatarFileError if the file is not acceptable or can't be decoded.
 */
export async function prepareAvatar(file: File): Promise<Blob> {
  assertAvatarFile(file)
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    throw new AvatarFileError('decode')
  }
  const side = Math.min(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = AVATAR_SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new AvatarFileError('decode')
  ctx.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, AVATAR_SIZE, AVATAR_SIZE)
  bitmap.close()
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.88))
  if (!blob) throw new AvatarFileError('decode')
  return blob
}
