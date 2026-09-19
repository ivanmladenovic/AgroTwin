import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Send, MessagesSquare, X } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { createConversation, getConversation, listConversations, sendChatMessage } from '@/features/agronomist/api'
import type { ChatMessageRecord, ConversationSummary } from '@/shared/api/types'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

export function AgronomistPage() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [pendingText, setPendingText] = useState<string | null>(null)
  const [listOpen, setListOpen] = useState(false)
  const threadRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const listQuery = useQuery({ queryKey: ['ai-conversations'], queryFn: listConversations })
  const conversationQuery = useQuery({
    queryKey: ['ai-conversation', conversationId],
    queryFn: () => getConversation(conversationId!),
    enabled: Boolean(conversationId),
  })

  const sendMutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) => sendChatMessage(id, content),
    onSuccess: async (item) => {
      queryClient.setQueryData(['ai-conversation', item.id], item)
      await queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
    },
  })

  const conversation = conversationId ? conversationQuery.data : undefined
  const conversations = listQuery.data ?? []
  const messages = conversation?.messages ?? []
  const waiting = Boolean(pendingText) || sendMutation.isPending
  const title = conversation?.title || (conversationId ? 'Razgovor' : 'Novi razgovor')

  useEffect(() => {
    const node = threadRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [conversation?.messages, pendingText, conversationId])

  useEffect(() => {
    setListOpen(false)
    inputRef.current?.focus()
  }, [conversationId])

  async function ask(content: string) {
    const text = content.trim()
    if (!text || sendMutation.isPending) return
    setDraft('')
    setPendingText(text)
    try {
      let activeId = conversationId
      if (!activeId) {
        const created = await createConversation(text.slice(0, 80))
        activeId = created.id
        queryClient.setQueryData(['ai-conversation', created.id], created)
        await queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
        navigate(`/agronomist/${created.id}`, { replace: true })
      }
      await sendMutation.mutateAsync({ id: activeId, content: text })
    } catch {
      setDraft(text)
    } finally {
      setPendingText(null)
      inputRef.current?.focus()
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(draft)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void ask(draft)
    }
  }

  return (
    <div className="-mx-4 -mb-4 flex min-h-0 flex-1 flex-col lg:mx-0 lg:mb-0 lg:flex-row lg:gap-4">
      <aside className="hidden w-60 shrink-0 flex-col rounded-xl border border-border bg-card lg:flex">
        <ConversationList
          conversations={conversations}
          conversationId={conversationId}
          loading={listQuery.isLoading}
          onNew={() => navigate('/agronomist')}
          onOpen={(id) => navigate(`/agronomist/${id}`)}
        />
      </aside>

      {listOpen ? (
        <div className="fixed inset-0 z-[2000] lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Zatvori razgovore" onClick={() => setListOpen(false)} />
          <aside className="relative flex h-full w-[min(20rem,88vw)] flex-col bg-card pt-[env(safe-area-inset-top)] shadow-xl">
            <div className="flex items-center justify-end px-3 pt-2">
              <button type="button" className="inline-flex h-11 w-11 items-center justify-center rounded-lg hover:bg-muted" aria-label="Zatvori" onClick={() => setListOpen(false)}>
                <X className="h-5 w-5" />
              </button>
            </div>
            <ConversationList
              conversations={conversations}
              conversationId={conversationId}
              loading={listQuery.isLoading}
              onNew={() => {
                setListOpen(false)
                navigate('/agronomist')
              }}
              onOpen={(id) => navigate(`/agronomist/${id}`)}
            />
          </aside>
        </div>
      ) : null}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col border-border bg-card lg:rounded-xl lg:border">
        <div className="flex items-start gap-2 border-b border-border px-4 py-3 lg:px-5 lg:py-4">
          <Button type="button" variant="outline" size="sm" className="mt-0.5 shrink-0 lg:hidden" onClick={() => setListOpen(true)}>
            <MessagesSquare className="h-4 w-4" />
            Razgovori
          </Button>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold">{title}</h2>
            <p className="mt-0.5 hidden text-sm text-muted-foreground sm:block">
              Pitajte agronoma o voćnjaku i nastavite prethodni razgovor.
            </p>
          </div>
        </div>

        <div ref={threadRef} className="min-h-0 flex-1 space-y-3 overflow-auto px-4 py-4 lg:px-5">
          {conversationId && conversationQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Učitavanje razgovora…</p>
          ) : conversationId && conversationQuery.isError ? (
            <p className="text-sm text-danger">Razgovor nije pronađen.</p>
          ) : messages.length === 0 && !pendingText ? (
            <p className="text-sm text-muted-foreground">Napišite pitanje. Agronom odgovara na osnovu evidencije voćnjaka.</p>
          ) : (
            <>
              {messages.map((message) => (
                <ChatBubble key={message.id} message={message} />
              ))}
              {pendingText ? (
                <>
                  <ChatBubble message={{ id: 'pending-user', role: 'user', content: pendingText, created_at: '', sources: null }} />
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
          <div className="flex min-w-0 items-end gap-2 rounded-xl border border-border bg-background px-3 py-2">
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              disabled={waiting}
              placeholder="Napišite poruku agronomu…"
              className="max-h-32 min-h-11 min-w-0 flex-1 resize-none bg-transparent py-2 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none disabled:opacity-60 lg:min-h-10 lg:text-sm"
            />
            <Button type="submit" size="sm" className="h-11 shrink-0 lg:h-8" disabled={waiting || !draft.trim()} aria-label="Pošalji">
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Pošalji</span>
            </Button>
          </div>
        </form>
      </section>
    </div>
  )
}

function ConversationList({
  conversations,
  conversationId,
  loading,
  onNew,
  onOpen,
}: {
  conversations: ConversationSummary[]
  conversationId?: string
  loading: boolean
  onNew: () => void
  onOpen: (id: string) => void
}) {
  return (
    <>
      <div className="space-y-3 border-b border-border p-4">
        <div>
          <p className="kicker">Agronom</p>
          <h1 className="mt-1 text-lg font-semibold">Razgovori</h1>
        </div>
        <Button size="sm" className="w-full" variant={conversationId ? 'outline' : 'default'} onClick={onNew}>
          <Plus className="h-4 w-4" />
          Novi razgovor
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
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onOpen(item.id)}
                  className={cn(
                    'block w-full rounded-lg px-3 py-3 text-left transition-colors lg:py-2',
                    active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/70',
                  )}
                >
                  <p className="truncate text-sm font-medium">{item.title}</p>
                  <p className={cn('mt-0.5 text-[11px]', active ? 'text-primary-foreground/70' : 'text-muted-foreground')}>
                    {formatDate((item.last_message_at || item.updated_at).slice(0, 10))}
                  </p>
                </button>
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
}: {
  message: Pick<ChatMessageRecord, 'id' | 'role' | 'content' | 'created_at' | 'sources'>
}) {
  const mine = message.role === 'user'
  return (
    <article className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-6',
          mine ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!mine && message.sources && message.sources.length > 0 ? (
          <div className="mt-2 space-y-0.5 border-t border-border/50 pt-2 text-xs opacity-80">
            {message.sources.map((source, index) => (
              <p key={`${source.document_title}-${index}`}>
                {source.document_title}
                {source.page_number ? ` · str. ${source.page_number}` : ''}
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </article>
  )
}
