<script setup lang="ts">
import { X } from 'lucide-vue-next'

/** Mobile bottom sheet, used by the builder for palette / inspector / results
 * and available anywhere the desktop layout needs a mobile-friendly panel. */
const props = defineProps<{ open: boolean; title?: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

watch(
  () => props.open,
  (open) => {
    if (import.meta.client) document.body.style.overflow = open ? 'hidden' : ''
  },
  { immediate: true }, // handle mounting with open=true (deep-link / restore)
)
onUnmounted(() => {
  if (import.meta.client) document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="sheet-backdrop" @click="emit('close')">
        <div class="sheet-panel" role="dialog" aria-modal="true" @click.stop>
          <div class="sheet-grip" />
          <div class="sheet-head">
            <h3 class="text-sm font-semibold">{{ title }}</h3>
            <button class="btn-ghost h-8 w-8 px-0" aria-label="Close" @click="emit('close')">
              <X class="w-4 h-4" :stroke-width="2" />
            </button>
          </div>
          <div class="sheet-body thin-scroll">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
