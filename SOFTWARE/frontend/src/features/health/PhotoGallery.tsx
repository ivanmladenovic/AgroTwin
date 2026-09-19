import { useEffect, useState } from 'react'

import { fetchObjectUrl } from '@/shared/lib/api'
import type { PhotoRecord } from '@/shared/api/types'

export function PhotoGallery({ photos }: { photos: PhotoRecord[] }) {
  const [active, setActive] = useState<PhotoRecord | null>(null)

  if (photos.length === 0) {
    return <p className="text-sm text-muted-foreground">Još nema fotografija.</p>
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {photos.map((photo) => (
          <PhotoThumb key={photo.id} photo={photo} onOpen={() => setActive(photo)} />
        ))}
      </div>
      {active ? <PhotoViewer photo={active} onClose={() => setActive(null)} /> : null}
    </>
  )
}

function PhotoThumb({ photo, onOpen }: { photo: PhotoRecord; onOpen: () => void }) {
  const src = useAuthorizedImage(photo.url)
  return (
    <button
      type="button"
      onClick={onOpen}
      className="overflow-hidden border border-border bg-muted text-left hover:border-primary"
    >
      {src ? (
        <img src={src} alt={photo.caption || photo.original_filename} className="h-28 w-full object-cover" />
      ) : (
        <div className="flex h-28 items-center justify-center text-xs text-muted-foreground">Učitavanje…</div>
      )}
      <p className="truncate px-2 py-1 text-xs text-muted-foreground">{photo.caption || photo.original_filename}</p>
    </button>
  )
}

function PhotoViewer({ photo, onClose }: { photo: PhotoRecord; onClose: () => void }) {
  const src = useAuthorizedImage(photo.url)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/70 p-3 sm:p-6" onClick={onClose} role="dialog">
      <div className="max-h-full max-w-4xl rounded-xl border border-border bg-card p-4" onClick={(event) => event.stopPropagation()}>
        {src ? (
          <img src={src} alt={photo.caption || photo.original_filename} className="max-h-[75vh] w-full object-contain" />
        ) : (
          <p className="text-sm text-muted-foreground">Učitavanje fotografije…</p>
        )}
        <div className="mt-3 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium">{photo.caption || photo.original_filename}</p>
            <p className="text-xs text-muted-foreground">{photo.original_filename}</p>
          </div>
          <button type="button" className="text-sm hover:underline" onClick={onClose}>
            Zatvori
          </button>
        </div>
      </div>
    </div>
  )
}

function useAuthorizedImage(path: string) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    void fetchObjectUrl(path).then((url) => {
      if (cancelled) {
        URL.revokeObjectURL(url)
        return
      }
      objectUrl = url
      setSrc(url)
    })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path])

  return src
}
