const LEADING_NOISE = /^(?:[a-zčćžšđ]{1,2}|[a-z]{1,3}\d+[a-z]?|\d+[a-z]|[._\-–—]+)$/i
const PARTICLES = new Set([
  'i', 'a', 'u', 'o', 'da', 'je', 'se', 'od', 'za', 'na', 'sa', 'po', 'iz', 'do', 'te', 'ili',
  'ne', 'pa', 'li', 'uz', 'to', 'tu', 'mu', 'ga', 'ih', 'im', 'će', 'bi', 'ni',
])

export function cleanKnowledgeExcerpt(raw: string, query = ''): string[] {
  const needle = query.trim()
  let text = raw.replace(/\r/g, ' ').replace(/[|]+/g, ' ').replace(/\s+/g, ' ').trim()
  if (needle.length >= 4) {
    text = text.replace(new RegExp(`(${escapeRegExp(needle)})\\s+([a-zčćžšđ])(?=\\s|$)`, 'gi'), '$1$2')
  }
  text = dropLeadingJunk(text, needle)
  text = dropGibberishWords(text)
  if (needle) {
    text = windowAroundQuery(text, needle)
  }
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((item) => item.replace(/^…\s*/, '').replace(/\s*…$/, '').trim())
    .filter((item) => item.replace(/[.…\s]/g, '').length > 12)
  if (sentences.length === 0) return text ? [text] : []
  if (!needle) return sentences.slice(0, 3)
  const lowered = needle.toLowerCase()
  const matchIndex = sentences.findIndex((item) => item.toLowerCase().includes(lowered))
  if (matchIndex < 0) return sentences.slice(0, 3)
  return sentences.slice(matchIndex, matchIndex + 3)
}

export function highlightParts(text: string, query: string): Array<{ text: string; match: boolean }> {
  const needle = query.trim()
  if (!needle) return [{ text, match: false }]
  const pattern = new RegExp(`(${escapeRegExp(needle)})`, 'gi')
  return text
    .split(pattern)
    .filter((part) => part.length > 0)
    .map((part) => ({ text: part, match: part.toLowerCase() === needle.toLowerCase() }))
}

function dropLeadingJunk(text: string, query: string): string {
  const needle = query.trim()
  if (needle) {
    const index = text.toLowerCase().indexOf(needle.toLowerCase())
    if (index > 0 && index <= 28) {
      return text.slice(index)
    }
  }
  const words = text.split(/\s+/).filter(Boolean)
  while (words.length > 3 && isNoiseToken(words[0]) && !PARTICLES.has(words[0].toLowerCase())) {
    words.shift()
  }
  return words.join(' ')
}

function dropGibberishWords(text: string): string {
  return text
    .split(/\s+/)
    .filter((word) => !shouldDropToken(word))
    .join(' ')
    .replace(/\s+([,.;:!?])/g, '$1')
}

function shouldDropToken(word: string): boolean {
  const clean = word.replace(/[()[\]"'“”]/g, '')
  if (!clean) return true
  if (PARTICLES.has(clean.toLowerCase())) return false
  if (/[A-ZČĆŽŠĐ]/.test(clean) && clean.length <= 3) return false
  if (clean.length <= 2 && !/\d/.test(clean)) return true
  if (/^[a-zčćžšđ]{1,2}\d+$/i.test(clean)) return true
  return isGibberish(clean)
}

function isGibberish(word: string): boolean {
  const clean = word.replace(/[()[\]"'“”]/g, '')
  if (clean.length < 8 || /\d/.test(clean)) return false
  if (!/\p{L}/u.test(clean)) return false
  if (/(.)\1{2,}/i.test(clean)) return true
  if (/^[aeioučćžšđ]*(.)\1/i.test(clean) && !/^(pre|naj|ne)/i.test(clean)) return true
  if (/[bcdfghjklmnpqrstvwxyzčćžšđ]{6,}/i.test(clean)) return true
  return false
}

function windowAroundQuery(text: string, query: string): string {
  const index = text.toLowerCase().indexOf(query.toLowerCase())
  if (index < 0) return text
  const radius = 220
  let start = Math.max(0, index - 60)
  let end = Math.min(text.length, index + query.length + radius)
  if (start > 0) {
    const space = text.lastIndexOf(' ', start)
    if (space > 0) start = space + 1
  }
  if (end < text.length) {
    const space = text.indexOf(' ', end)
    if (space > 0) end = space
  }
  const slice = text.slice(start, end).trim()
  return `${start > 0 ? '… ' : ''}${slice}${end < text.length ? ' …' : ''}`
}

function isNoiseToken(word: string): boolean {
  if (/[A-ZČĆŽŠĐ]/.test(word) && word.length <= 3) return false
  return LEADING_NOISE.test(word)
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
