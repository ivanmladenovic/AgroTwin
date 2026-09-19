import { apiDownload, apiRequest, apiUpload, fetchObjectUrl } from '@/shared/lib/api'
import type { Invoice, InvoiceCategory, InvoiceKind } from '@/shared/api/types'

export type InvoiceCreateInput = {
  file: File
  title: string
  category: InvoiceCategory
  kind?: InvoiceKind
  vendor?: string
  amount?: string
  issued_on: string
  notes?: string
}

export function listInvoices() {
  return apiRequest<Invoice[]>('/invoices')
}

export function createInvoice(input: InvoiceCreateInput) {
  const form = new FormData()
  form.append('file', input.file)
  form.append('title', input.title)
  form.append('category', input.category)
  form.append('issued_on', input.issued_on)
  if (input.kind) form.append('kind', input.kind)
  if (input.vendor) form.append('vendor', input.vendor)
  if (input.amount) form.append('amount', input.amount)
  if (input.notes) form.append('notes', input.notes)
  return apiUpload<Invoice>('/invoices', form)
}

export function deleteInvoice(invoiceId: string) {
  return apiRequest<void>(`/invoices/${invoiceId}`, { method: 'DELETE' })
}

export function downloadInvoiceFile(invoice: Invoice) {
  return apiDownload(`/invoices/${invoice.id}/file`, invoice.original_filename)
}

export async function openInvoiceFile(invoice: Invoice) {
  const url = await fetchObjectUrl(`/invoices/${invoice.id}/file`)
  window.open(url, '_blank', 'noopener')
}
