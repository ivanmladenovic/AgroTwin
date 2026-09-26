const MAX_EDGE = 1600
const JPEG_QUALITY = 0.72

export async function compressPhoto(file: File): Promise<File> {
  if (file.type && !file.type.startsWith('image/')) return file

  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    try {
      const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
      const width = Math.max(1, Math.round(bitmap.width * scale))
      const height = Math.max(1, Math.round(bitmap.height * scale))
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d')
      if (!context) return file
      context.drawImage(bitmap, 0, 0, width, height)
      const blob = await canvasToJpeg(canvas, JPEG_QUALITY)
      if (!blob) return file
      if (blob.size >= file.size) return file
      const name = file.name.replace(/\.[^.]+$/, '') || 'photo'
      return new File([blob], `${name}.jpg`, { type: 'image/jpeg', lastModified: file.lastModified || Date.now() })
    } finally {
      bitmap.close()
    }
  } catch {
    return file
  }
}

function canvasToJpeg(canvas: HTMLCanvasElement, quality: number) {
  return new Promise<Blob | null>((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality)
  })
}
