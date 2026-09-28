const LEADING_NOISE = /^(?:[a-zčćžšđ]{1,2}|[a-z]{1,3}\d+[a-z]?|\d+[a-z]|[._\-–—]+)$/i
const PARTICLES = new Set([
  'i', 'a', 'u', 'o', 'da', 'je', 'se', 'od', 'za', 'na', 'sa', 'po', 'iz', 'do', 'te', 'ili',
  'ne', 'pa', 'li', 'uz', 'to', 'tu', 'mu', 'ga', 'ih', 'im', 'će', 'bi', 'ni',
])

/** Return at most one readable sentence that contains the search query. */
export function cleanKnowledgeExcerpt(raw: string, query = ''): string[] {
  const needle = query.trim()
  let text = raw.replace(/\r/g, '\n').replace(/[|]+/g, ' ').replace(/[ \t]+/g, ' ').trim()
  if (!text) return []

  if (needle.length >= 4) {
    text = text.replace(new RegExp(`(${escapeRegExp(needle)})\\s+([a-zčćžšđ])(?=\\s|$)`, 'gi'), '$1$2')
  }

  text = dropGibberishWords(text)
  text = text.replace(/\s+/g, ' ').trim()
  if (!text) return []

  if (!needle) {
    const first = splitSentences(text).find((item) => looksReadable(item))
    return first ? [first] : []
  }

  const match = pickSentenceWithQuery(text, needle)
  if (!match) return []
  const cleaned = polishSentence(match, needle)
  return cleaned ? [cleaned] : []
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

function pickSentenceWithQuery(text: string, query: string): string | null {
  const lowered = query.toLowerCase()
  const sentences = splitSentences(text)
  const containing = sentences.filter((item) => item.toLowerCase().includes(lowered) && looksReadable(item))
  if (containing.length > 0) {
    // Prefer the shortest readable sentence that still includes the query.
    containing.sort((a, b) => a.length - b.length)
    return containing[0] ?? null
  }

  // PDF chunks often lack punctuation — carve one clause around the match.
  const index = text.toLowerCase().indexOf(lowered)
  if (index < 0) return null
  return carveAroundQuery(text, index, query.length)
}

function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?…])\s+|\n+/)
    .map((item) => item.replace(/^[\s•\-–—*]+/, '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
}

function carveAroundQuery(text: string, index: number, queryLength: number): string | null {
  const before = text.slice(0, index)
  const after = text.slice(index + queryLength)

  let start = 0
  const softStart = Math.max(
    before.lastIndexOf('. '),
    before.lastIndexOf('! '),
    before.lastIndexOf('? '),
    before.lastIndexOf('\n'),
    before.lastIndexOf('; '),
  )
  if (softStart >= 0 && softStart >= index - 220) {
    start = softStart + (before[softStart] === '\n' ? 1 : 2)
  } else {
    // Keep a short lead-in of whole words before the match.
    const lead = before.trimEnd().split(/\s+/).filter(Boolean).slice(-8).join(' ')
    start = index - (lead ? lead.length + 1 : 0)
    if (start < 0) start = 0
  }

  let end = Math.min(text.length, index + queryLength + 160)
  const softEndCandidates = ['.', '!', '?', ';', '\n']
    .map((mark) => {
      const at = after.search(new RegExp(`[${escapeRegExp(mark)}]\\s`))
      return at >= 0 ? index + queryLength + at + 1 : -1
    })
    .filter((at) => at > index && at <= index + queryLength + 220)
  if (softEndCandidates.length > 0) {
    end = Math.min(...softEndCandidates)
  } else {
    const trail = after.trimStart().split(/\s+/).filter(Boolean).slice(0, 14).join(' ')
    end = index + queryLength + (trail ? trail.length + 1 : 0)
    if (end > text.length) end = text.length
  }

  const slice = text.slice(start, end).replace(/\s+/g, ' ').trim()
  if (!looksReadable(slice)) return null
  return slice
}

function polishSentence(sentence: string, query: string): string {
  let text = dropLeadingJunk(sentence, query).replace(/\s+/g, ' ').trim()
  text = text.replace(/^…\s*/, '').replace(/\s*…$/, '').trim()
  if (!text.toLowerCase().includes(query.toLowerCase())) return ''
  if (!looksReadable(text)) return ''
  // Capitalize first letter if the carve started mid-sentence.
  if (/^[a-zčćžšđ]/.test(text)) {
    text = text.charAt(0).toUpperCase() + text.slice(1)
  }
  return text
}

function looksReadable(text: string): boolean {
  const letters = (text.match(/\p{L}/gu) ?? []).length
  const words = text.split(/\s+/).filter(Boolean)
  if (words.length < 4 || letters < 18) return false
  const gibberishWords = words.filter((word) => isGibberish(word.replace(/[()[\]"'“”.,;:!?]/g, ''))).length
  if (gibberishWords > Math.max(1, Math.floor(words.length / 4))) return false
  return true
}

function dropLeadingJunk(text: string, query: string): string {
  const needle = query.trim()
  if (needle) {
    const index = text.toLowerCase().indexOf(needle.toLowerCase())
    // Keep a little context before the query when it is near the start.
    if (index > 0 && index <= 18) {
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

function isNoiseToken(word: string): boolean {
  if (/[A-ZČĆŽŠĐ]/.test(word) && word.length <= 3) return false
  return LEADING_NOISE.test(word)
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
