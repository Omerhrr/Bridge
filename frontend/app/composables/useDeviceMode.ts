/** Device mode system (spec section 18 adaptation).
 *
 * Bridge ships two tuned UI modes (desktop and mobile) plus an automatic
 * mode that follows the viewport. The preference is explicit (not just media
 * queries) so the app "works best in both worlds":
 *
 *  - desktop: persistent top navigation, three-column workflow builder,
 *    hover-oriented controls, tables.
 *  - mobile: compact top bar, bottom tab navigation, bottom sheets for the
 *    builder palette/inspector, 44px+ touch targets, iOS-zoom-safe inputs.
 *
 * The choice persists in localStorage on this device.
 */
export type DeviceModePref = 'auto' | 'mobile' | 'desktop'

const STORAGE_KEY = 'bridge.deviceMode'

export function useDeviceMode() {
  const pref = useState<DeviceModePref>('bridge.deviceMode.pref', () => 'auto')
  const viewportMobile = useState('bridge.deviceMode.vp', () => false)
  const ready = useState('bridge.deviceMode.ready', () => false)

  /** Call once on the client (layout onMounted). Idempotent. */
  function init() {
    if (ready.value || !import.meta.client) return
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved === 'auto' || saved === 'mobile' || saved === 'desktop') pref.value = saved
    } catch {
      /* storage unavailable (private mode); keep auto */
    }
    const query = window.matchMedia('(max-width: 1023px)')
    const apply = () => { viewportMobile.value = query.matches }
    apply()
    query.addEventListener('change', apply)
    ready.value = true
  }

  /** The mode actually in effect (pref, or the viewport when auto). */
  const mode = computed<'mobile' | 'desktop'>(() =>
    pref.value === 'auto' ? (viewportMobile.value ? 'mobile' : 'desktop') : pref.value,
  )
  const isMobile = computed(() => mode.value === 'mobile')

  function setPref(next: DeviceModePref) {
    pref.value = next
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* ignore */ }
  }

  /** Header toggle: auto → mobile → desktop → auto. */
  function cycle() {
    setPref(pref.value === 'auto' ? 'mobile' : pref.value === 'mobile' ? 'desktop' : 'auto')
  }

  return { pref, mode, isMobile, ready, init, setPref, cycle }
}
