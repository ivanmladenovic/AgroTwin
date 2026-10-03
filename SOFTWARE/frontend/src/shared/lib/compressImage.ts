import { heicTo, isHeic } from 'heic-to'

const MAX_EDGE = 1600
const JPEG_QUALITY = 0.72

const HEIC_MIME = new Set(['image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'])

export async function compressPhoto(file: File): Promise<File> {
  if (file.type && !file.type.startsWith('image/') && !isHeicName(file.name)) return file

  const fromHeic = isHeicCandidate(file)
  const prepared = fromHeic ? await convertHeicToPng(file) : file

  try {
    const bitmap = await createImageBitmap(prepared, { imageOrientation: 'from-image' })
    try {
      const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
      const width = Math.max(1, Math.round(bitmap.width * scale))
      const height = Math.max(1, Math.round(bitmap.height * scale))
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d')
      if (!context) return prepared
      context.drawImage(bitmap, 0, 0, width, height)

      if (fromHeic) {
        const png = await canvasToBlob(canvas, 'image/png')
        if (!png) return prepared
        const name = stem(prepared.name || file.name)
        return new File([png], `${name}.png`, { type: 'image/png', lastModified: file.lastModified || Date.now() })
      }

      const jpeg = await canvasToBlob(canvas, 'image/jpeg', JPEG_QUALITY)
      if (!jpeg) return prepared
      if (jpeg.size >= prepared.size) return prepared
      const name = stem(prepared.name || file.name)
      return new File([jpeg], `${name}.jpg`, { type: 'image/jpeg', lastModified: file.lastModified || Date.now() })
    } finally {
      bitmap.close()
    }
  } catch (error) {
    if (fromHeic) {
      throw error instanceof Error
        ? error
        : new Error('HEIC fotografija nije mogla da se konvertuje. Probajte JPEG ili PNG.')
    }
    return file
  }
}

async function convertHeicToPng(file: File): Promise<File> {
  try {
    const detected = await isHeic(file)
    if (!detected && !isHeicName(file.name) && !HEIC_MIME.has((file.type || '').toLowerCase())) {
      return file
    }
    const converted = await heicTo({ blob: file, type: 'image/png' })
    const blob = Array.isArray(converted) ? converted[0] : converted
    if (!blob) {
      throw new Error('HEIC fotografija nije mogla da se konvertuje.')
    }
    return new File([blob], `${stem(file.name)}.png`, {
      type: 'image/png',
      lastModified: file.lastModified || Date.now(),
    })
  } catch {
    throw new Error('HEIC fotografija nije mogla da se konvertuje. Probajte JPEG ili PNG.')
  }
}

function isHeicCandidate(file: File) {
  return HEIC_MIME.has((file.type || '').toLowerCase()) || isHeicName(file.name)
}

function isHeicName(name: string) {
  return /\.heic$/i.test(name) || /\.heif$/i.test(name)
}

function stem(name: string) {
  return name.replace(/\.[^.]+$/, '') || 'photo'
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number) {
  return new Promise<Blob | null>((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality)
  })
}
