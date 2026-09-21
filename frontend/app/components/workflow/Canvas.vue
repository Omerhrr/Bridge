<script setup lang="ts">
import { VueFlow, useVueFlow, type Connection, type Edge, type Node, type NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

/** Center canvas: Vue Flow graph (spec sections 10/20). */
const props = defineProps<{
  nodes: Node[]
  edges: Edge[]
  errorNodeIds: string[]
}>()

const emit = defineEmits<{
  (e: 'connect', connection: Connection): void
  (e: 'select', nodeId: string | null): void
  (e: 'drop', type: string, position: { x: number; y: number }): void
}>()

const rootEl = ref<HTMLElement | null>(null)
const { screenToFlowCoordinate } = useVueFlow()

/** Add a node at the visual center of the canvas.
 *  Used by mobile mode, where drag-and-drop from the palette is replaced
 *  by tap-to-add in the node sheet. */
function addAtCenter(type: string) {
  const rect = rootEl.value?.getBoundingClientRect()
  const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2
  const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2
  emit('drop', type, screenToFlowCoordinate({ x, y }))
}

defineExpose({ addAtCenter })

function onConnect(connection: Connection) {
  emit('connect', connection)
}

function onNodeClick(event: NodeMouseEvent) {
  emit('select', event.node.id)
}

function onPaneClick() {
  emit('select', null)
}

function onDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData('application/bridge-node')
  if (!type) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  emit('drop', type, position)
}
</script>

<template>
  <div ref="rootEl" class="card flex-1 min-w-0 overflow-hidden relative" @drop="onDrop" @dragover.prevent>
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.3"
      :max-zoom="1.8"
      fit-view-on-init
      @connect="onConnect"
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
    >
      <Background :gap="18" :size="1" pattern-color="#dbe3ec" />
      <Controls position="bottom-left" show-initial />
      <MiniMap position="bottom-right" pannable zoomable />

      <template #node-bridge="nodeProps">
        <WorkflowBridgeNode
          :id="nodeProps.id"
          :data="{ ...nodeProps.data, error: errorNodeIds.includes(nodeProps.id) }"
          :selected="nodeProps.selected"
        />
      </template>
    </VueFlow>

    <div
      v-if="!nodes.length"
      class="absolute inset-0 grid place-items-center pointer-events-none"
    >
      <div class="text-center text-muted">
        <p class="text-sm font-medium text-ink">Empty canvas</p>
        <p class="text-sm mt-1">Drag nodes from the palette to build your communication workflow</p>
      </div>
    </div>
  </div>
</template>
