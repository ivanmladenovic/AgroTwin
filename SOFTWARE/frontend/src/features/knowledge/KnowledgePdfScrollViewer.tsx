import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import { fetchKnowledgeDocumentBytes } from '@/features/knowledge/api'

GlobalWorkerOptions.workerSrc = pdfWorker

type Props = {
  documentId: string
  title: string
  page?: number | null
  className?: string
}

export function KnowledgePdfScrollViewer({ documentId, title, page, className }: Props) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [pageCount, setPageCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map())
  const didScroll = useRef(false)
  const startPage = page && page > 0 ? page : 1

  useEffect(() => {
    let cancelled = false
    let doc: PDFDocumentProxy | null = null
    setLoading(true)
    setError(null)
    setPdf(null)
    setPageCount(0)
    didScroll.current = false
    pageRefs.current.clear()

    void (async () => {
      try {
        const data = await fetchKnowledgeDocumentBytes(documentId)
        if (cancelled) return
        doc = await getDocument({ data, disableAutoFetch: true, disableStream: true }).promise
        if (cancelled) {
          await doc.destroy()
          return
        }
        setPdf(doc)
        setPageCount(doc.numPages)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'PDF nije učitan')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
      void doc?.destroy()
    }
  }, [documentId])

  useEffect(() => {
    if (!pdf || pageCount < 1 || didScroll.current) return
    const target = Math.min(Math.max(startPage, 1), pageCount)
    const timer = window.setTimeout(() => {
      const node = pageRefs.current.get(target)
      if (!node) return
      node.scrollIntoView({ block: 'start' })
      didScroll.current = true
    }, 80)
    return () => window.clearTimeout(timer)
  }, [pdf, pageCount, startPage])

  if (loading) {
    return <p className="p-6 text-sm text-muted-foreground">Učitavanje PDF-a…</p>
  }
  if (error || !pdf) {
    return <p className="p-6 text-sm text-danger">{error || 'PDF nije učitan'}</p>
  }

  return (
    <div ref={scrollerRef} className={className ?? 'h-full overflow-auto bg-muted/40'}>
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-3 p-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {Array.from({ length: pageCount }, (_, index) => {
          const pageNumber = index + 1
          return (
            <PdfPageCanvas
              key={pageNumber}
              pdf={pdf}
              pageNumber={pageNumber}
              title={title}
              active={pageNumber === startPage}
              register={(node) => {
                if (node) pageRefs.current.set(pageNumber, node)
                else pageRefs.current.delete(pageNumber)
              }}
            />
          )
        })}
      </div>
    </div>
  )
}

function PdfPageCanvas({
  pdf,
  pageNumber,
  title,
  active,
  register,
}: {
  pdf: PDFDocumentProxy
  pageNumber: number
  title: string
  active: boolean
  register: (node: HTMLElement | null) => void
}) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [visible, setVisible] = useState(pageNumber <= 2 || active)
  const [height, setHeight] = useState(480)

  useEffect(() => {
    const node = hostRef.current
    if (!node) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setVisible(true)
      },
      { rootMargin: '800px 0px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!visible) return
    let cancelled = false
    void (async () => {
      const page = await pdf.getPage(pageNumber)
      if (cancelled) return
      const base = page.getViewport({ scale: 1 })
      const width = Math.min(hostRef.current?.clientWidth || 720, 900)
      const scale = width / base.width
      const viewport = page.getViewport({ scale })
      const canvas = canvasRef.current
      if (!canvas) return
      const context = canvas.getContext('2d')
      if (!context) return
      canvas.width = Math.floor(viewport.width)
      canvas.height = Math.floor(viewport.height)
      setHeight(Math.floor(viewport.height))
      await page.render({ canvas, canvasContext: context, viewport }).promise
    })()
    return () => {
      cancelled = true
    }
  }, [pdf, pageNumber, visible])

  return (
    <div
      ref={(node) => {
        hostRef.current = node
        register(node)
      }}
      data-page={pageNumber}
      className={`overflow-hidden rounded-lg border bg-white shadow-sm ${
        active ? 'border-primary ring-2 ring-primary/30' : 'border-border'
      }`}
      style={{ minHeight: height }}
    >
      <div className="flex items-center justify-between border-b border-border/70 px-3 py-1.5 text-xs text-muted-foreground">
        <span>
          {title} · strana {pageNumber}
        </span>
      </div>
      <canvas ref={canvasRef} className="block h-auto w-full" />
    </div>
  )
}
