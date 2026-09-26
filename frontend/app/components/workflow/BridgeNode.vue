<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import {
  PhoneIncoming, PhoneOutgoing, PhoneOff, MessageSquare, Hash, Mic, AudioLines,
  TextCursorInput, Volume2, Send, Captions, Languages, Speech, GitBranch,
  Shuffle, Clock, Variable, Square, Circle, List, CornerDownLeft, Smartphone,
  ArrowLeftRight, BookOpen,
} from 'lucide-vue-next'
import type { NodeMeta } from '~/types'

/** Custom compact node used on the canvas (spec section 21). */
const props = defineProps<{
  id: string
  data: { type: string; label?: string; config?: Record<string, unknown>; error?: boolean }
  selected?: boolean
}>()

const store = useWorkflowsStore()

const meta = computed<NodeMeta | undefined>(() =>
  store.nodeTypes.find((n) => n.type === props.data.type),
)

const iconMap: Record<string, any> = {
  'phone-incoming': PhoneIncoming,
  'phone-outgoing': PhoneOutgoing,
  'phone-off': PhoneOff,
  'message-square-in': MessageSquare,
  hash: Hash,
  mic: Mic,
  'audio-lines': AudioLines,
  'text-cursor-input': TextCursorInput,
  'volume-2': Volume2,
  send: Send,
  captions: Captions,
  languages: Languages,
  speech: Speech,
  'git-branch': GitBranch,
  shuffle: Shuffle,
  clock: Clock,
  variable: Variable,
  list: List,
  'corner-down-left': CornerDownLeft,
  smartphone: Smartphone,
  'arrow-left-right': ArrowLeftRight,
  'book-open': BookOpen,
  square: Square,
  circle: Circle,
}

const icon = computed(() => iconMap[meta.value?.icon ?? 'circle'] ?? Circle)

const categoryStyles: Record<string, string> = {
  trigger: 'bg-comms-soft text-comms border-comms/30',
  voice: 'bg-signal-soft text-signal border-signal/30',
  ai: 'bg-navy text-white border-navy',
  messaging: 'bg-success-soft text-success border-success/30',
  telecom: 'bg-comms-soft text-comms border-comms/40',
  logic: 'bg-warning-soft text-warning border-warning/30',
  flow: 'bg-canvas text-muted border-line',
}

/** One-line summary of configured values shown under the label. */
const summary = computed(() => {
  const config = props.data.config ?? {}
  const schema = meta.value?.config_schema ?? []
  const parts: string[] = []
  for (const field of schema) {
    const value = config[field.name]
    if (value === undefined || value === null || String(value).trim() === '') continue
    if (field.name === 'text' && String(value).length > 18) {
      parts.push(`${field.label}: ${String(value).slice(0, 18)}…`)
    } else {
      parts.push(String(value))
    }
    if (parts.length >= 2) break
  }
  return parts.join(' · ')
})

const isConfigured = computed(() => {
  const schema = meta.value?.config_schema ?? []
  const required = schema.filter((f) => f.required)
  if (!required.length) return true
  return required.every((f) => String(props.data.config?.[f.name] ?? '').trim() !== '')
})

const handleOrder = ['true', 'false', 'default']
const outputs = computed(() => {
  let outs = meta.value?.outputs ?? ['out']
  // Switch nodes expose one handle per configured case plus "default" —
  // the cases live in the node config, not the static metadata, so the
  // handles can only be derived here (required to wire USSD menus).
  if (props.data.type === 'switch') {
    const cases = String(props.data.config?.cases ?? '')
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c && c !== 'default')
    outs = [...cases, 'default']
  }
  return [...outs].sort((a, b) => {
    const ia = handleOrder.indexOf(a), ib = handleOrder.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
})

function handleClass(name: string) {
  if (name === 'true') return 'handle-success'
  if (name === 'false') return 'handle-error'
  return ''
}
</script>

<template>
  <div
    class="w-52 bg-surface border rounded-lg shadow-sm transition-shadow"
    :class="[
      selected ? 'border-signal ring-2 ring-signal/25 shadow-md' : 'border-line',
      data.error ? 'border-error ring-2 ring-error/20' : '',
    ]"
  >
    <Handle v-if="meta?.inputs?.length" type="target" :position="Position.Left" id="in" />

    <div class="flex items-start gap-2.5 p-3">
      <span class="grid place-items-center w-8 h-8 rounded-md border shrink-0" :class="categoryStyles[meta?.category ?? 'flow']">
        <component :is="icon" class="w-4 h-4" :stroke-width="1.8" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-medium leading-tight truncate">{{ meta?.label ?? data.label ?? data.type }}</p>
        <p class="text-[11px] text-muted leading-snug mt-0.5 line-clamp-2">{{ meta?.description }}</p>
        <p v-if="summary" class="text-[11px] text-signal leading-snug mt-1 truncate">{{ summary }}</p>
      </div>
      <span
        class="w-2 h-2 rounded-full mt-1 shrink-0"
        :class="data.error ? 'bg-error' : isConfigured ? 'bg-success' : 'bg-warning'"
        :title="data.error ? 'Validation error' : isConfigured ? 'Configured' : 'Missing configuration'"
      />
    </div>

    <Handle
      v-for="(output, index) in outputs"
      :key="output"
      :id="output"
      type="source"
      :position="Position.Right"
      :class="handleClass(output)"
      :style="{ top: `${50 + (index - (outputs.length - 1) / 2) * 22}%` }"
    />
  </div>
</template>
