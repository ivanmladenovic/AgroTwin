import { Camera, ImagePlus, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/shared/ui/button'

type PhotoPickerProps = {
  files: File[]
  onChange: (files: File[]) => void
  description?: string
}

export function PhotoPicker({ files, onChange, description }: PhotoPickerProps) {
  const galleryInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const [cameraOpen, setCameraOpen] = useState(false)

  function addFiles(incoming: File[]) {
    const images = incoming.filter((file) => file.type.startsWith('image/'))
    if (images.length === 0) return
    onChange([...files, ...images])
  }

  function openCamera() {
    if (prefersNativeCamera()) {
      cameraInputRef.current?.click()
      return
    }
    if (navigator.mediaDevices?.getUserMedia) {
      setCameraOpen(true)
      return
    }
    cameraInputRef.current?.click()
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {description ?? 'U voćnjaku otvorite kameru i uslikajte simptom, ili izaberite fotografiju iz galerije.'}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={openCamera}>
          <Camera className="h-4 w-4" />
          Uslikaj
        </Button>
        <Button type="button" variant="outline" onClick={() => galleryInputRef.current?.click()}>
          <ImagePlus className="h-4 w-4" />
          Izaberi fotografiju
        </Button>
      </div>
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []))
          event.target.value = ''
        }}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []))
          event.target.value = ''
        }}
      />
      {files.length > 0 ? (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {files.map((file, index) => (
            <PhotoPreview
              key={`${file.name}-${file.lastModified}-${index}`}
              file={file}
              onRemove={() => onChange(files.filter((_, itemIndex) => itemIndex !== index))}
            />
          ))}
        </ul>
      ) : null}
      {cameraOpen ? (
        <CameraCapture
          onCapture={(file) => {
            addFiles([file])
            setCameraOpen(false)
          }}
          onClose={() => setCameraOpen(false)}
          onFallback={() => {
            setCameraOpen(false)
            cameraInputRef.current?.click()
          }}
        />
      ) : null}
    </div>
  )
}

function PhotoPreview({ file, onRemove }: { file: File; onRemove: () => void }) {
  const url = useMemo(() => URL.createObjectURL(file), [file])
  useEffect(() => () => URL.revokeObjectURL(url), [url])

  return (
    <li className="relative overflow-hidden rounded-lg border border-border bg-muted">
      <img src={url} alt={file.name} className="h-24 w-full object-cover" />
      <button
        type="button"
        onClick={onRemove}
        className="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-black/70 text-white hover:bg-black"
        aria-label={`Ukloni ${file.name}`}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </li>
  )
}

function CameraCapture({
  onCapture,
  onClose,
  onFallback,
}: {
  onCapture: (file: File) => void
  onClose: () => void
  onFallback: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
        })
        if (cancelled) {
          stopStream(stream)
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          await video.play()
          setReady(true)
        }
      } catch {
        if (!cancelled) {
          setError('Kamera nije dostupna. Dozvolite pristup ili uslikajte telefonom.')
        }
      }
    }

    void start()
    return () => {
      cancelled = true
      if (streamRef.current) stopStream(streamRef.current)
    }
  }, [])

  function capture() {
    const video = videoRef.current
    if (!video || video.videoWidth === 0) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
        onCapture(new File([blob], `uslikano-${stamp}.jpg`, { type: 'image/jpeg' }))
      },
      'image/jpeg',
      0.92,
    )
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-t-2xl border border-border bg-card shadow-lg sm:rounded-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-medium">Kamera</p>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Zatvori kameru">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="relative bg-black">
          {error ? (
            <div className="space-y-3 p-6 text-sm text-white">
              <p>{error}</p>
              <Button type="button" variant="outline" onClick={onFallback}>
                Uslikaj telefonom
              </Button>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className="aspect-video max-h-[60vh] min-h-[240px] w-full bg-black object-contain"
              />
              {ready ? null : (
                <p className="absolute inset-0 flex items-center justify-center text-sm text-white/80">Otvaranje kamere…</p>
              )}
            </>
          )}
        </div>
        <div className="flex justify-end gap-2 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <Button type="button" variant="outline" onClick={onClose}>
            Otkaži
          </Button>
          <Button type="button" onClick={capture} disabled={!ready || Boolean(error)}>
            Uslikaj
          </Button>
        </div>
      </div>
    </div>
  )
}

function prefersNativeCamera() {
  return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
}

function stopStream(stream: MediaStream) {
  for (const track of stream.getTracks()) {
    track.stop()
  }
}
