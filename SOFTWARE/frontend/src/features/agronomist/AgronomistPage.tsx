import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, ImagePlus, MessagesSquare, Plus, Send, ShieldAlert, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  loadChatMessageImage,
  sendChatMessage,
} from '@/features/agronomist/api'
import { stripAgronomMarkdown } from '@/features/agronomist/format'
import { ReportProblemForm } from '@/features/health/ReportProblemForm'
import type { ChatMessageRecord, ConversationSummary, KnowledgeSource } from '@/shared/api/types'
import { compressPhoto } from '@/shared/lib/compressImage'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'

export function AgronomistPage() {
  const { conversationId } = useParams()
  const [params] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [attachedPhoto, setAttachedPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [pendingText, setPendingText] = useState<string | null>(null)
  const [pendingPhotoUrl, setPendingPhotoUrl] = useState<string | null>(null)
  const [listOpen, setListOpen] = useState(false)
  const threadRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)
  const sentInitial = useRef<string | null>(null)
  const sendingRef = useRef(false)
  const pendingConversationId = useRef<string | null>(null)
  const conversationIdRef = useRef<string | null>(conversationId || null)
  conversationIdRef.current = conversationId || null

  const reporting = params.get('report') === '1' && !conversationId
  const composing = params.get('new') === '1' && !conversationId && !reporting
  const showHub = !conversationId && !reporting && !composing

  const listQuery = useQuery({ queryKey: ['ai-conversations'], queryFn: listConversations })
  const conversationQuery = useQuery({
    queryKey: ['ai-conversation', conversationId],
    queryFn: () => getConversation(conversationId!),
    enabled: Boolean(conversationId),
  })

  const sendMutation = useMutation({
    mutationFn: ({ id, content, file }: { id: string; content: string; file?: File | null }) =>
      sendChatMessage(id, content, file),
    onSuccess: async (item) => {
      queryClient.setQueryData(['ai-conversation', item.id], item)
      await queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: async (_data, id) => {
      queryClient.removeQueries({ queryKey: ['ai-conversation', id] })
      await queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      if (conversationId === id) navigate('/agronomist', { replace: true })
    },
  })

  function confirmDelete(id: string, title?: string) {
    const label = (title || 'ovaj razgovor').trim()
    if (!window.confirm(`Obrisati razgovor „${label}”?`)) return
    deleteMutation.mutate(id)
  }

  const conversation = conversationId ? conversationQuery.data : undefined
  const conversations = listQuery.data ?? []
  const messages = conversation?.messages ?? []
  const waiting = Boolean(pendingText) || sendMutation.isPending
  const title = conversation?.title || (conversationId ? 'Razgovor' : 'Novi razgovor')
  const canSend = Boolean(draft.trim() || attachedPhoto) && !waiting

  useEffect(() => {
    const node = threadRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [conversation?.messages, pendingText, pendingPhotoUrl, conversationId])

  useEffect(() => {
    setListOpen(false)
    // Don't leak a failed/pending composer draft across conversations.
    const keepPending = sendingRef.current && pendingConversationId.current === (conversationId || null)
    if (!keepPending) {
      setPendingText(null)
      setPendingPhotoUrl(null)
      setDraft('')
      setAttachedPhoto(null)
      sendMutation.reset()
    }
    if (!reporting && !showHub) inputRef.current?.focus()
    // Intentionally omit sendMutation from deps — only reset on conversation/route change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, reporting, showHub])

  useEffect(() => {
    if (!attachedPhoto) {
      setPhotoPreview(null)
      return
    }
    const url = URL.createObjectURL(attachedPhoto)
    setPhotoPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [attachedPhoto])

  async function onPickPhoto(fileList: FileList | null) {
    const file = fileList?.[0]
    if (!file) return
    const isImage =
      file.type.startsWith('image/') ||
      !file.type ||
      /\.(jpe?g|png|gif|webp|heic|heif)$/i.test(file.name)
    if (!isImage) return
    try {
      const compressed = await compressPhoto(file)
      setAttachedPhoto(compressed)
    } catch (error) {
      window.alert(error instanceof Error ? error.message : 'Fotografija nije mogla da se učita.')
    }
    if (photoInputRef.current) photoInputRef.current.value = ''
  }

  function clearPhoto() {
    setAttachedPhoto(null)
  }

  async function ask(content: string, photo?: File | null) {
    const text = content.trim()
    const file = photo ?? attachedPhoto
    if ((!text && !file) || sendingRef.current || sendMutation.isPending) return
    const preview = file ? URL.createObjectURL(file) : null
    sendingRef.current = true
    setDraft('')
    setAttachedPhoto(null)
    setPendingText(text || (file ? 'Fotografija' : null))
    setPendingPhotoUrl(preview)
    let activeId = conversationId || null
    pendingConversationId.current = activeId
    try {
      if (!activeId) {
        const created = await createConversation((text || 'Fotografija').slice(0, 80))
        activeId = created.id
        pendingConversationId.current = activeId
        queryClient.setQueryData(['ai-conversation', created.id], created)
        await queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
        navigate(`/agronomist/${created.id}`, { replace: true })
      }
      await sendMutation.mutateAsync({ id: activeId, content: text, file })
    } catch {
      // Restore draft only if user is still viewing the conversation that failed.
      if (conversationIdRef.current === activeId) {
        setDraft(text)
        if (file) setAttachedPhoto(file)
      }
    } finally {
      if (preview) URL.revokeObjectURL(preview)
      sendingRef.current = false
      pendingConversationId.current = null
      setPendingText(null)
      setPendingPhotoUrl(null)
      inputRef.current?.focus()
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(draft, attachedPhoto)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void ask(draft, attachedPhoto)
    }
  }

  useEffect(() => {
    const initial = (location.state as { initialMessage?: string } | null)?.initialMessage
    if (!conversationId || !initial || sentInitial.current === conversationId) return
    sentInitial.current = conversationId
    navigate(`/agronomist/${conversationId}`, { replace: true, state: {} })
    void ask(initial)
  }, [conversationId, location.state, navigate])

  function goHub() {
    navigate('/agronomist')
  }

  function goNew() {
    navigate('/agronomist?new=1')
  }

  function goReport() {
    navigate('/agronomist?report=1')
  }

  function goConversation(id: string) {
    navigate(`/agronomist/${id}`)
  }

  const heading = reporting ? 'Prijavi problem' : showHub ? 'Agronom' : title
  const subtitle = reporting
    ? 'Uslikajte ili dodajte fotografije, opišite simptome i pošaljite agronomu na analizu.'
    : showHub
      ? 'Izaberite novi razgovor, prijavu problema ili nastavite ranije dopisivanje.'
      : 'Pitajte agronoma o voćnjaku i nastavite prethodni razgovor.'

  return (
    <div className="-mx-4 -mb-4 flex min-h-0 flex-1 flex-col lg:mx-0 lg:mb-0 lg:flex-row lg:gap-4">
      <aside className="hidden w-60 shrink-0 flex-col rounded-xl border border-border bg-card lg:flex">
        <ConversationList
          conversations={conversations}
          conversationId={conversationId}
          reporting={reporting}
          composing={composing}
          hub={showHub}
          loading={listQuery.isLoading}
          deletingId={deleteMutation.isPending ? deleteMutation.variables : null}
          onHub={goHub}
          onNew={goNew}
          onReport={goReport}
          onOpen={goConversation}
          onDelete={confirmDelete}
        />
      </aside>

      {listOpen ? (
        <div className="fixed inset-0 z-[2000] lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Zatvori razgovore" onClick={() => setListOpen(false)} />
          <aside className="relative flex h-full w-[min(20rem,88vw)] flex-col bg-card pt-[env(safe-area-inset-top)] shadow-xl">
            <div className="flex items-center justify-end px-3 pt-2">
              <button
                type="button"
                className="inline-flex h-11 w-11 items-center justify-center rounded-lg hover:bg-muted"
                aria-label="Zatvori"
                onClick={() => setListOpen(false)}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <ConversationList
              conversations={conversations}
              conversationId={conversationId}
              reporting={reporting}
              composing={composing}
              hub={showHub}
              loading={listQuery.isLoading}
              deletingId={deleteMutation.isPending ? deleteMutation.variables : null}
              onHub={() => {
                setListOpen(false)
                goHub()
              }}
              onNew={() => {
                setListOpen(false)
                goNew()
              }}
              onReport={() => {
                setListOpen(false)
                goReport()
              }}
              onOpen={(id) => {
                setListOpen(false)
                goConversation(id)
              }}
              onDelete={confirmDelete}
            />
          </aside>
        </div>
      ) : null}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col border-border bg-card lg:rounded-xl lg:border">
        {!showHub ? (
          <div className="flex items-start gap-2 border-b border-border px-4 py-3 lg:px-5 lg:py-4">
            <Button type="button" variant="outline" size="sm" className="mt-0.5 shrink-0 lg:hidden" onClick={() => setListOpen(true)}>
              <MessagesSquare className="h-4 w-4" />
              Razgovori
            </Button>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-lg font-semibold">{heading}</h2>
              <p className="mt-0.5 hidden text-sm text-muted-foreground sm:block">{subtitle}</p>
            </div>
            {conversationId ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mt-0.5 shrink-0 text-muted-foreground hover:text-danger"
                disabled={deleteMutation.isPending}
                aria-label="Obriši razgovor"
                onClick={() => confirmDelete(conversationId, conversation?.title)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            ) : null}
            <BackButton variant="ghost" fallback="/agronomist" className="mt-0.5 shrink-0">
              Nazad
            </BackButton>
          </div>
        ) : null}

        {showHub ? (
          <HubScreen
            conversations={conversations}
            loading={listQuery.isLoading}
            deletingId={deleteMutation.isPending ? deleteMutation.variables : null}
            onNew={goNew}
            onReport={goReport}
            onOpen={goConversation}
            onDelete={confirmDelete}
          />
        ) : reporting ? (
          <div className="min-h-0 flex-1 overflow-auto px-4 py-4 lg:px-5">
            <ReportProblemForm variant="agronomist" onCancel={goHub} />
          </div>
        ) : (
          <>
            <div ref={threadRef} className="min-h-0 flex-1 space-y-3 overflow-auto px-4 py-4 lg:px-5">
              {conversationId && conversationQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Učitavanje razgovora…</p>
              ) : conversationId && conversationQuery.isError ? (
                <p className="text-sm text-danger">Razgovor nije pronađen.</p>
              ) : messages.length === 0 && !pendingText ? (
                <p className="text-sm text-muted-foreground">
                  Napišite pitanje ili priložite fotografiju. Agronom odgovara na osnovu evidencije voćnjaka.
                </p>
              ) : (
                <>
                  {messages.map((message) => (
                    <ChatBubble key={message.id} message={message} conversationId={conversationId} />
                  ))}
                  {pendingText ? (
                    <>
                      <ChatBubble
                        message={{
                          id: 'pending-user',
                          role: 'user',
                          content: pendingText,
                          created_at: '',
                          sources: null,
                          structured_refs: null,
                        }}
                        previewUrl={pendingPhotoUrl}
                      />
                      <p className="text-sm text-muted-foreground">Agronom piše…</p>
                    </>
                  ) : null}
                </>
              )}
              {sendMutation.isError && !pendingText ? (
                <p className="text-sm text-danger">
                  {sendMutation.error instanceof Error ? sendMutation.error.message : 'Agronom nije mogao da odgovori.'}
                </p>
              ) : null}
            </div>

            <form onSubmit={onSubmit} className="border-t border-border p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              {photoPreview ? (
                <div className="mb-2 flex items-center gap-2">
                  <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-border">
                    <img src={photoPreview} alt="Prilog" className="h-full w-full object-cover" />
                    <button
                      type="button"
                      onClick={clearPhoto}
                      disabled={waiting}
                      className="absolute right-0.5 top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white"
                      aria-label="Ukloni fotografiju"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground">Fotografija će biti poslata sa porukom.</p>
                </div>
              ) : null}
              <div className="flex min-w-0 items-end gap-2 rounded-xl border border-border bg-background px-3 py-2">
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*,.heic,.heif,image/heic,image/heif"
                  className="hidden"
                  onChange={(event) => void onPickPhoto(event.target.files)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-11 shrink-0 px-2 lg:h-8"
                  disabled={waiting}
                  aria-label="Priloži fotografiju"
                  onClick={() => photoInputRef.current?.click()}
                >
                  <ImagePlus className="h-4 w-4" />
                </Button>
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={waiting}
                  placeholder="Napišite poruku ili priložite fotografiju…"
                  className="max-h-32 min-h-11 min-w-0 flex-1 resize-none bg-transparent py-2 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none disabled:opacity-60 lg:min-h-10 lg:text-sm"
                />
                <Button
                  type="submit"
                  size="sm"
                  className="h-11 shrink-0 lg:h-8"
                  disabled={!canSend}
                  aria-label="Pošalji"
                >
                  <Send className="h-4 w-4" />
                  <span className="hidden sm:inline">Pošalji</span>
                </Button>
              </div>
            </form>
          </>
        )}
      </section>
    </div>
  )
}

function HubScreen({
  conversations,
  loading,
  deletingId,
  onNew,
  onReport,
  onOpen,
  onDelete,
}: {
  conversations: ConversationSummary[]
  loading: boolean
  deletingId?: string | null
  onNew: () => void
  onReport: () => void
  onOpen: (id: string) => void
  onDelete: (id: string, title?: string) => void
}) {
  return (
    <div className="min-h-0 flex-1 overflow-auto px-4 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] lg:px-6 lg:py-6">
      <div className="mb-5">
        <p className="kicker">Agronom</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Kako možemo da pomognemo?</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Izaberite novi razgovor ili prijavu problema, ili nastavite jedno od ranijih dopisivanja.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={onNew}
          className="flex items-start gap-3 rounded-xl border border-border bg-background px-4 py-4 text-left transition-colors hover:bg-muted/60"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Plus className="h-5 w-5" />
          </span>
          <span className="min-w-0">
            <span className="block text-base font-semibold">Novi razgovor</span>
            <span className="mt-1 block text-sm text-muted-foreground">Pitanje o voćnjaku, radovima ili zaštiti.</span>
          </span>
        </button>

        <button
          type="button"
          onClick={onReport}
          className="flex items-start gap-3 rounded-xl border border-border bg-background px-4 py-4 text-left transition-colors hover:bg-muted/60"
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-danger/10 text-danger">
            <ShieldAlert className="h-5 w-5" />
          </span>
          <span className="min-w-0">
            <span className="block text-base font-semibold">Prijavi problem</span>
            <span className="mt-1 block text-sm text-muted-foreground">Fotografija i opis simptoma sadnice ili reda.</span>
          </span>
        </button>
      </div>

      <div className="mt-7">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Prethodna dopisivanja</h2>
          {conversations.length > 0 ? (
            <span className="text-xs text-muted-foreground">{conversations.length}</span>
          ) : null}
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">Učitavanje…</p>
        ) : conversations.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center">
            <p className="text-sm text-muted-foreground">Još nema prethodnih dopisivanja.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
            {conversations.map((item) => (
              <li key={item.id} className="flex items-stretch">
                <button
                  type="button"
                  onClick={() => onOpen(item.id)}
                  className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/60"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <MessagesSquare className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{item.title}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {formatDate((item.last_message_at || item.updated_at).slice(0, 10))}
                    </span>
                  </span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  className="inline-flex shrink-0 items-center px-3 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-danger disabled:opacity-50"
                  aria-label={`Obriši razgovor ${item.title}`}
                  disabled={deletingId === item.id}
                  onClick={() => onDelete(item.id, item.title)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function ConversationList({
  conversations,
  conversationId,
  reporting = false,
  composing = false,
  hub = false,
  loading,
  deletingId,
  onHub,
  onNew,
  onReport,
  onOpen,
  onDelete,
}: {
  conversations: ConversationSummary[]
  conversationId?: string
  reporting?: boolean
  composing?: boolean
  hub?: boolean
  loading: boolean
  deletingId?: string | null
  onHub: () => void
  onNew: () => void
  onReport: () => void
  onOpen: (id: string) => void
  onDelete: (id: string, title?: string) => void
}) {
  return (
    <>
      <div className="space-y-3 border-b border-border p-4">
        <button type="button" onClick={onHub} className="block w-full text-left">
          <p className="kicker">Agronom</p>
          <h1 className="mt-1 text-lg font-semibold">Razgovori</h1>
        </button>
        <Button size="sm" className="w-full" variant={composing && !conversationId ? 'default' : 'outline'} onClick={onNew}>
          <Plus className="h-4 w-4" />
          Novi razgovor
        </Button>
        <Button size="sm" className="w-full" variant={reporting ? 'default' : 'outline'} onClick={onReport}>
          <ShieldAlert className="h-4 w-4" />
          Prijavi problem
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-2">
        {loading ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Učitavanje…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Još nema prethodnih dopisivanja.</p>
        ) : (
          <div className="space-y-1">
            {conversations.map((item) => {
              const active = item.id === conversationId
              return (
                <div
                  key={item.id}
                  className={cn(
                    'flex items-stretch rounded-lg',
                    active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/70',
                    hub && !active ? 'opacity-90' : null,
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onOpen(item.id)}
                    className="min-w-0 flex-1 rounded-lg px-3 py-3 text-left lg:py-2"
                  >
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className={cn('mt-0.5 text-[11px]', active ? 'text-primary-foreground/70' : 'text-muted-foreground')}>
                      {formatDate((item.last_message_at || item.updated_at).slice(0, 10))}
                    </p>
                  </button>
                  <button
                    type="button"
                    className={cn(
                      'inline-flex shrink-0 items-center px-2.5 transition-colors disabled:opacity-50',
                      active ? 'text-primary-foreground/80 hover:text-primary-foreground' : 'text-muted-foreground hover:text-danger',
                    )}
                    aria-label={`Obriši razgovor ${item.title}`}
                    disabled={deletingId === item.id}
                    onClick={() => onDelete(item.id, item.title)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}

function ChatBubble({
  message,
  conversationId,
  previewUrl,
}: {
  message: Pick<ChatMessageRecord, 'id' | 'role' | 'content' | 'created_at' | 'sources' | 'structured_refs'>
  conversationId?: string
  previewUrl?: string | null
}) {
  const mine = message.role === 'user'
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [imageUrl, setImageUrl] = useState<string | null>(previewUrl ?? null)
  const sources = !mine ? message.sources ?? [] : []
  const hasChatImage = Boolean(
    previewUrl || message.structured_refs?.some((ref) => ref.kind === 'chat_image'),
  )
  const body = mine ? message.content : stripAgronomMarkdown(message.content)
  const hidePlaceholder =
    mine &&
    hasChatImage &&
    (body === 'Pogledajte priloženu fotografiju.' || body === 'Fotografija')

  useEffect(() => {
    if (previewUrl) {
      setImageUrl(previewUrl)
      return
    }
    if (!conversationId || !hasChatImage || message.id === 'pending-user') return
    let active = true
    let objectUrl: string | null = null
    void loadChatMessageImage(conversationId, message.id)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        objectUrl = url
        setImageUrl(url)
      })
      .catch(() => {
        if (active) setImageUrl(null)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [conversationId, hasChatImage, message.id, previewUrl])

  return (
    <article className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-6',
          mine ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
        )}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Priložena fotografija"
            className={cn(
              'mb-2 max-h-56 w-full rounded-xl object-cover',
              mine ? 'ring-1 ring-primary-foreground/20' : 'ring-1 ring-border/60',
            )}
          />
        ) : null}
        {!hidePlaceholder && body ? <p className="whitespace-pre-wrap">{body}</p> : null}
        {sources.length > 0 ? (
          <div className="mt-2 flex items-center justify-end">
            <button
              type="button"
              className={cn(
                'inline-flex h-5 w-5 items-center justify-center rounded-full border text-[11px] font-semibold leading-none',
                sourcesOpen
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border/80 bg-background/80 text-muted-foreground hover:border-foreground/30 hover:text-foreground',
              )}
              aria-label={sourcesOpen ? 'Sakrij izvore' : 'Prikaži izvore iz priručnika'}
              aria-expanded={sourcesOpen}
              onClick={() => setSourcesOpen((open) => !open)}
            >
              !
            </button>
          </div>
        ) : null}
        {sourcesOpen && sources.length > 0 ? <SourcesPanel sources={sources} /> : null}
      </div>
    </article>
  )
}

function SourcesPanel({ sources }: { sources: KnowledgeSource[] }) {
  return (
    <div className="mt-3 space-y-2 border-t border-border/60 pt-3">
      <p className="text-xs font-medium text-muted-foreground">Izvori iz priručnika</p>
      <ul className="space-y-2">
        {sources.map((source, index) => {
          const params = new URLSearchParams()
          if (source.document_id) params.set('doc', source.document_id)
          if (source.page_number) params.set('page', String(source.page_number))
          const href = params.toString() ? `/knowledge?${params}` : '/knowledge'
          return (
            <li key={`${source.document_title}-${index}`} className="rounded-lg bg-background/70 px-2.5 py-2 text-xs">
              <p className="font-medium text-foreground">{source.document_title}</p>
              <p className="mt-0.5 text-muted-foreground">
                {source.page_number ? `Strana ${source.page_number}` : 'Bez broja strane'}
                {source.section_title ? ` · ${source.section_title}` : ''}
              </p>
              <Link to={href} className="mt-1.5 inline-flex text-primary underline-offset-2 hover:underline">
                Otvori u priručnicima
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
