import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import {
  createInvoice,
  deleteInvoice,
  downloadInvoiceFile,
  listInvoices,
  openInvoiceFile,
} from '@/features/invoices/api'
import { todayKey } from '@/features/journal/calendar'
import type { Invoice, InvoiceCategory, InvoiceKind } from '@/shared/api/types'
import { formatDate, formatMoney } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

function kindLabel(kind: InvoiceKind | null) {
  if (kind === 'machine') return 'Mašine'
  if (kind === 'equipment') return 'Oprema'
  if (kind === 'other') return 'Ostale investicije'
  return null
}

export function InvoicesPage() {
  const invoicesQuery = useQuery({ queryKey: ['invoices'], queryFn: listInvoices })
  const invoices = invoicesQuery.data ?? []
  const fuel = invoices.filter((item) => item.category === 'fuel')
  const other = invoices.filter((item) => item.category === 'other')

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Dokumentacija</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Računi</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Arhiva računa za subvencije i internu evidenciju. Gorivo je posebna kategorija; mašine, oprema i
          ostale investicije idu u drugu listu.
        </p>
      </div>

      {invoicesQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Učitavanje računa…</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <InvoiceColumn category="fuel" title="Računi za gorivo." items={fuel} />
          <InvoiceColumn category="other" title="Ostali računi." items={other} />
        </div>
      )}
    </div>
  )
}

function InvoiceColumn({
  category,
  title,
  items,
}: {
  category: InvoiceCategory
  title: string
  items: Invoice[]
}) {
  const [adding, setAdding] = useState(false)

  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader>
        <h2 className="text-base font-semibold">{title}</h2>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        {items.length === 0 && !adding ? (
          <p className="text-sm text-muted-foreground">Još nema sačuvanih računa u ovoj listi.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <InvoiceRow key={item.id} invoice={item} />
            ))}
          </ul>
        )}
        {adding ? (
          <InvoiceForm category={category} onClose={() => setAdding(false)} />
        ) : (
          <Button type="button" onClick={() => setAdding(true)}>
            + Dodaj račun
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function InvoiceRow({ invoice }: { invoice: Invoice }) {
  const queryClient = useQueryClient()
  const deleteMutation = useMutation({
    mutationFn: () => deleteInvoice(invoice.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
  const kind = kindLabel(invoice.kind)

  return (
    <li className="rounded-lg border border-border px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium">{invoice.title}</p>
          <p className="text-xs text-muted-foreground">
            {formatDate(invoice.issued_on)}
            {invoice.vendor ? ` · ${invoice.vendor}` : ''}
            {kind ? ` · ${kind}` : ''}
          </p>
        </div>
        {invoice.amount ? (
          <p className="shrink-0 font-mono text-sm">{formatMoney(invoice.amount, invoice.currency)}</p>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => void openInvoiceFile(invoice)}>
          Otvori
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => void downloadInvoiceFile(invoice)}>
          Preuzmi
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm('Obrisati ovaj račun i priloženi dokument?')) {
              deleteMutation.mutate()
            }
          }}
        >
          Obriši
        </Button>
      </div>
    </li>
  )
}

function InvoiceForm({ category, onClose }: { category: InvoiceCategory; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [vendor, setVendor] = useState('')
  const [issuedOn, setIssuedOn] = useState(todayKey())
  const [amount, setAmount] = useState('')
  const [kind, setKind] = useState<InvoiceKind>('other')
  const [notes, setNotes] = useState('')
  const [file, setFile] = useState<File | null>(null)

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Izaberite dokument')
      return createInvoice({
        file,
        title: title.trim() || file.name,
        category,
        kind: category === 'other' ? kind : undefined,
        vendor: vendor.trim() || undefined,
        amount: amount.trim() || undefined,
        issued_on: issuedOn,
        notes: notes.trim() || undefined,
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['invoices'] })
      onClose()
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form className="grid gap-3 rounded-xl border border-border p-3" onSubmit={onSubmit}>
      <p className="text-sm font-medium">Novi račun</p>
      <div className="space-y-1.5">
        <Label>Naslov</Label>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Npr. Račun za dizel" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Dobavljač</Label>
          <Input value={vendor} onChange={(event) => setVendor(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Datum</Label>
          <Input type="date" value={issuedOn} onChange={(event) => setIssuedOn(event.target.value)} required />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Iznos (EUR)</Label>
          <Input type="number" step="0.01" min="0" value={amount} onChange={(event) => setAmount(event.target.value)} />
        </div>
        {category === 'other' ? (
          <div className="space-y-1.5">
            <Label>Vrsta</Label>
            <Select value={kind} onChange={(event) => setKind(event.target.value as InvoiceKind)}>
              <option value="machine">Mašine</option>
              <option value="equipment">Oprema</option>
              <option value="other">Ostale investicije</option>
            </Select>
          </div>
        ) : null}
      </div>
      <div className="space-y-1.5">
        <Label>Dokument</Label>
        <Input
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>Beleške</Label>
        <Textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>
      {mutation.isError ? (
        <p className="text-sm text-danger">
          {mutation.error instanceof Error ? mutation.error.message : 'Račun nije sačuvan'}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={mutation.isPending || !file}>
          {mutation.isPending ? 'Čuvanje…' : 'Sačuvaj račun'}
        </Button>
        <Button type="button" variant="outline" disabled={mutation.isPending} onClick={onClose}>
          Otkaži
        </Button>
      </div>
    </form>
  )
}
