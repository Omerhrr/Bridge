import type { LanguageOption } from '~/types'

/** Languages offered by the backend, fetched once and shared across pages. */
export function useLanguages() {
  const languages = useState<LanguageOption[]>('bridge-languages', () => [])
  const api = useApi()

  async function load() {
    if (languages.value.length) return
    try {
      languages.value = await api<LanguageOption[]>('/languages')
    } catch {
      languages.value = []
    }
  }

  function nameOf(code?: string | null) {
    if (!code) return ''
    return languages.value.find((l) => l.code === code)?.name ?? code
  }

  return { languages, load, nameOf }
}

/** SMS segment math: GSM-7 fits 160 chars (153 per part when split),
 * anything outside basic Latin forces UCS-2 at 70 (67 per part). */
export function smsSegments(text: string) {
  const unicode = /[^\u0000-\u007f£¥èéùìòÇØøÅåÆæßÉÄÖÑÜ§¿äöñüà]/.test(text)
  const single = unicode ? 70 : 160
  const multi = unicode ? 67 : 153
  const length = [...text].length
  const parts = length === 0 ? 0 : length <= single ? 1 : Math.ceil(length / multi)
  return { length, parts, unicode, limit: parts <= 1 ? single : parts * multi }
}
