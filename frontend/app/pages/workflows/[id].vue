<script setup lang="ts">
import { Save, ClipboardCheck, Play, Power, Plus, SlidersHorizontal, ClipboardList } from 'lucide-vue-next'
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { ValidationIssue, WorkflowDefinition } from '~/types'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const store = useWorkflowsStore()
const dm = useDeviceMode()

const workflowId = computed(() => Number(route.params.id))

// Canvas state
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const selectedNodeId = ref<string | null>(null)
const nameDraft = ref('')
const showPanel = ref<'validation' | 'run'>('validation')
const canvasRef = ref<any>(null)

// Mobile sheets: palette / inspector / results (desktop uses side columns)
const sheet = ref<null | 'palette' | 'inspector' | 'panel'>(null)

await store.fetchNodeTypes()

// Load the workflow and its current definition
await store.fetchOne(workflowId.value)
if (store.current) {
  nameDraft.value = store.current.name
  const definition = store.current.current_version?.definition
  if (definition) {
    nodes.value = definition.nodes.map((n) => ({
      id: n.id,
      type: 'bridge',
      position: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
      data: { type: n.type, config: { ...n.config } },
    }))
    edges.value = definition.edges.map((e, index) => ({
      id: `e-${e.source}-${e.target}-${e.source_handle ?? index}`,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_handle ?? undefined,
      targetHandle: e.target_handle ?? undefined,
    }))
  }
}

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  const node = nodes.value.find((n) => n.id === selectedNodeId.value)
  if (!node) return null
  return { id: node.id, type: node.data.type, config: node.data.config }
})

const errorNodeIds = computed<string[]>(() => {
  if (!store.lastReport) return []
  return store.lastReport.issues
    .filter((issue: ValidationIssue) => issue.level === 'error' && issue.node_id)
    .map((issue) => issue.node_id as string)
})

function selectNode(nodeId: string | null) {
  selectedNodeId.value = nodeId
  if (nodeId) {
    showPanel.value = 'validation'
    // Mobile: tapping a node opens its settings as a bottom sheet
    if (dm.isMobile.value) sheet.value = 'inspector'
  } else if (sheet.value === 'inspector') {
    sheet.value = null
  }
}

function updateSelectedConfig(config: Record<string, unknown>) {
  const node = nodes.value.find((n) => n.id === selectedNodeId.value)
  if (node) node.data = { ...node.data, config }
}

function deleteSelectedNode() {
  if (!selectedNodeId.value) return
  nodes.value = nodes.value.filter((n) => n.id !== selectedNodeId.value)
  edges.value = edges.value.filter(
    (e) => e.source !== selectedNodeId.value && e.target !== selectedNodeId.value,
  )
  selectedNodeId.value = null
  sheet.value = null
}

function onConnect(connection: Connection) {
  // Ignore duplicate connections between the same ports.
  const exists = edges.value.some(
    (e) =>
      e.source === connection.source &&
      e.target === connection.target &&
      (e.sourceHandle ?? null) === (connection.sourceHandle ?? null),
  )
  if (exists) return
  edges.value.push({
    id: `e-${connection.source}-${connection.target}-${connection.sourceHandle ?? Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle ?? undefined,
    targetHandle: connection.targetHandle ?? undefined,
  })
}

let nodeCounter = 100
function onDrop(type: string, position: { x: number; y: number }) {
  const meta = store.nodeTypes.find((n) => n.type === type)
  const config: Record<string, unknown> = {}
  for (const field of meta?.config_schema ?? []) {
    if (field.default !== undefined && field.default !== '') config[field.name] = field.default
  }
  nodeCounter += 1
  nodes.value.push({
    id: `n${nodeCounter}`,
    type: 'bridge',
    position,
    data: { type, config },
  })
}

/** Palette tap (mobile sheet): add the node at the canvas center. */
function addFromPalette(type: string) {
  canvasRef.value?.addAtCenter(type)
  sheet.value = null
}

function toDefinition(): WorkflowDefinition {
  return {
    nodes: nodes.value.map((n) => ({
      id: n.id,
      type: n.data.type,
      position: { x: n.position.x, y: n.position.y },
      config: n.data.config ?? {},
    })),
    edges: edges.value.map((e) => ({
      source: e.source,
      target: e.target,
      source_handle: e.sourceHandle ?? null,
      target_handle: e.targetHandle ?? null,
    })),
  }
}

const saving = ref(false)
async function save() {
  saving.value = true
  try {
    await store.saveVersion(workflowId.value, toDefinition(), 'saved from builder')
  } finally {
    saving.value = false
  }
}

async function validate() {
  // Lint the canvas as-is; no version is created, so repeated Validate
  // clicks do not pollute the immutable version history.
  await store.validateDefinition(toDefinition())
  showPanel.value = 'validation'
  if (dm.isMobile.value) sheet.value = 'panel'
}

const testing = ref(false)
async function test() {
  testing.value = true
  try {
    await store.saveVersion(workflowId.value, toDefinition(), 'test snapshot')
    await store.testRun(workflowId.value)
    showPanel.value = 'run'
    if (dm.isMobile.value) sheet.value = 'panel'
  } finally {
    testing.value = false
  }
}

async function toggleDeploy() {
  if (store.current) await store.toggleStatus(store.current)
}

const panelTitle = computed(() =>
  showPanel.value === 'run' ? 'Test result' : 'Validation result',
)

/** Builder area height: desktop reserves less chrome than mobile (top bar +
 *  toolbar + action row + bottom nav). */
const areaClass = computed(() =>
  dm.isMobile.value
    ? 'h-[calc(100dvh-18.5rem)] min-h-[360px]'
    : 'h-[calc(100vh-15rem)] min-h-[480px]',
)

const hasResults = computed(() => !!store.lastReport || !!store.lastRun)
</script>

<template>
  <div>
    <!-- Builder toolbar (spec section 20); text labels collapse to icons in mobile mode -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <button class="btn-ghost shrink-0" title="Back to workflows" @click="router.push('/workflows')">
        ← <span class="hidden sm:inline">Workflows</span>
      </button>
      <input
        v-model="nameDraft"
        class="input h-8 font-medium flex-1 min-w-0 sm:flex-none sm:w-56"
        @change="store.rename(workflowId, nameDraft)"
        @keydown.enter="($event.target as HTMLInputElement).blur()"
      />
      <span class="hidden sm:inline-flex" :class="store.current?.status === 'active' ? 'pill-success' : 'pill-neutral'">
        {{ store.current?.status === 'active' ? '● Active' : '○ Inactive' }}
      </span>
      <span class="text-xs text-muted shrink-0">v{{ store.current?.current_version?.version_number ?? 'n/a' }}</span>

      <div class="ml-auto flex items-center gap-1.5 sm:gap-2">
        <button class="btn-secondary shrink-0" :disabled="saving" title="Save version" @click="save">
          <Save class="w-4 h-4 sm:hidden" :stroke-width="1.8" />
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
        <button class="btn-secondary shrink-0" title="Validate workflow" @click="validate">
          <ClipboardCheck class="w-4 h-4" :stroke-width="1.8" />
          <span class="hidden sm:inline">Validate</span>
        </button>
        <button class="btn-secondary shrink-0" :disabled="testing" title="Test run" @click="test">
          <Play class="w-4 h-4" :stroke-width="1.8" />
          <span class="hidden sm:inline">{{ testing ? 'Testing…' : 'Test' }}</span>
        </button>
        <button
          class="btn shrink-0"
          :class="store.current?.status === 'active' ? 'bg-warning text-white hover:bg-warning/90' : 'btn-primary'"
          title="Deploy / disable on live numbers"
          @click="toggleDeploy"
        >
          <Power class="w-4 h-4" :stroke-width="1.8" />
          <span class="hidden sm:inline">{{ store.current?.status === 'active' ? 'Disable' : 'Deploy' }}</span>
        </button>
      </div>
    </div>

    <!-- Builder area: three columns on desktop, full-width canvas + sheets on mobile -->
    <div class="flex gap-4" :class="areaClass">
      <WorkflowNodePalette :class="dm.isMobile.value ? 'hidden' : ''" />
      <ClientOnly>
        <WorkflowCanvas
          ref="canvasRef"
          :nodes="nodes"
          :edges="edges"
          :error-node-ids="errorNodeIds"
          @connect="onConnect"
          @select="selectNode"
          @drop="onDrop"
        />
        <template #fallback>
          <div class="card flex-1 grid place-items-center">
            <p class="text-sm text-muted">Loading canvas…</p>
          </div>
        </template>
      </ClientOnly>
      <div :class="dm.isMobile.value ? 'hidden' : 'flex flex-col gap-4 w-72 shrink-0'">
        <WorkflowInspector
          v-if="selectedNode"
          class="flex-1"
          :node="selectedNode"
          @update:config="updateSelectedConfig"
          @delete="deleteSelectedNode"
        />
        <WorkflowInspectorOverview v-else class="flex-1" />
        <template v-if="showPanel === 'validation' && store.lastReport">
          <WorkflowValidationPanel
            :issues="store.lastReport.issues"
            :checks-passed="store.lastReport.checks_passed"
            @select="selectNode"
          />
        </template>
        <WorkflowTestRunPanel v-if="showPanel === 'run' && store.lastRun" :run="store.lastRun" />
      </div>
    </div>

    <!-- Mobile action row: tap-to-add / node settings / results -->
    <div :class="dm.isMobile.value ? 'flex gap-2 mt-3' : 'hidden'">
      <button class="btn-secondary flex-1" @click="sheet = 'palette'">
        <Plus class="w-4 h-4" :stroke-width="2" /> Add node
      </button>
      <button class="btn-secondary flex-1" :disabled="!selectedNode" @click="sheet = 'inspector'">
        <SlidersHorizontal class="w-4 h-4" :stroke-width="2" />
        {{ selectedNode ? 'Node settings' : 'Select a node' }}
      </button>
      <button v-if="hasResults" class="btn-secondary shrink-0" @click="sheet = 'panel'">
        <ClipboardList class="w-4 h-4" :stroke-width="2" />
      </button>
    </div>

    <p :class="dm.isMobile.value ? 'mt-2 text-xs text-muted text-center' : 'hidden'">
      Drag handles between nodes to connect · tap a node to configure it
    </p>

    <p v-if="store.error" class="mt-3 text-sm text-error">{{ store.error }}</p>

    <!-- Mobile sheets -->
    <ClientOnly>
      <UiBottomSheet :open="sheet === 'palette'" title="Node library: tap to add" @close="sheet = null">
        <WorkflowNodePalette variant="sheet" @add="addFromPalette" />
      </UiBottomSheet>

      <UiBottomSheet :open="sheet === 'inspector'" title="Node settings" @close="sheet = null">
        <WorkflowInspector
          v-if="selectedNode"
          :node="selectedNode"
          @update:config="updateSelectedConfig"
          @delete="deleteSelectedNode"
        />
        <WorkflowInspectorOverview v-else />
      </UiBottomSheet>

      <UiBottomSheet :open="sheet === 'panel'" :title="panelTitle" @close="sheet = null">
        <template v-if="showPanel === 'validation' && store.lastReport">
          <WorkflowValidationPanel
            :issues="store.lastReport.issues"
            :checks-passed="store.lastReport.checks_passed"
            @select="selectNode"
          />
        </template>
        <WorkflowTestRunPanel v-if="showPanel === 'run' && store.lastRun" :run="store.lastRun" />
      </UiBottomSheet>
    </ClientOnly>
  </div>
</template>
