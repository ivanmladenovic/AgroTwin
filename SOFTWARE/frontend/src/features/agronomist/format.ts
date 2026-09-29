/** Strip common Markdown markers so Agronom replies read as plain text. */
export function stripAgronomMarkdown(text: string): string {
  return text
    .replace(/\r\n/g, '\n')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/\*([^*\n]+)\*/g, '$1')
    .replace(/_([^_\n]+)_/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^[\t ]*[\*\-]\s+/gm, '- ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
