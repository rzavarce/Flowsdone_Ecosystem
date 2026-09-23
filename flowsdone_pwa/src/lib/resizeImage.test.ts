import { describe, expect, it } from 'vitest'
import { AvatarFileError, MAX_SOURCE_BYTES, assertAvatarFile, prepareAvatar } from './resizeImage'

const file = (type: string, size = 10) => new File([new Uint8Array(size)], 'foto', { type })

describe('assertAvatarFile', () => {
  it('acepta JPEG, PNG y WebP', () => {
    for (const type of ['image/jpeg', 'image/png', 'image/webp']) expect(() => assertAvatarFile(file(type))).not.toThrow()
  })

  it('rechaza otros tipos (SVG incluido) y archivos enormes', () => {
    expect(() => assertAvatarFile(file('image/svg+xml'))).toThrow(AvatarFileError)
    expect(() => assertAvatarFile(file('application/pdf'))).toThrow(expect.objectContaining({ reason: 'type' }))
    expect(() => assertAvatarFile(file('image/png', MAX_SOURCE_BYTES + 1))).toThrow(expect.objectContaining({ reason: 'size' }))
  })
})

describe('prepareAvatar', () => {
  it('si el navegador no puede decodificar la imagen falla con reason=decode', async () => {
    // jsdom no implementa createImageBitmap: equivale a una imagen ilegible.
    await expect(prepareAvatar(file('image/png'))).rejects.toMatchObject({ reason: 'decode' })
  })
})
