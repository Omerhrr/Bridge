<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { ValidationIssue, WorkflowDefinition } from '~/types'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const store = useWorkflowsStore()

const workflowId = computed(() => Number(route.params.id))

// Canvas state
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const selectedNodeId = ref<string | null>(null)
const nameDraft = ref('')
const showPanel = ref<'validation' | 'run'>('validation')

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
  if (nodeId) showPanel.value = 'validation'
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
}

function onConnect(connection: Connection) {
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
    const ok = await store.saveVersion(workflowId.value, toDefinition(), 'saved from builder')
    if (ok) {
      // Keep local state in sync with the new version
      if (store.current?.current_version) {
        // no-op: canvas already matches what was saved
      }
    }
  } finally {
    saving.value = false
  }
}

async function validate() {
  await store.saveVersion(workflowId.value, toDefinition(), 'validate snapshot')
  await store.validate(workflowId.value)
  showPanel.value = 'validation'
}

const testing = ref(false)
async function test() {
  testing.value = true
  try {
    await store.saveVersion(workflowId.value, toDefinition(), 'test snapshot')
    await store.testRun(workflowId.value)
    showPanel.value = 'run'
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
</script>

<template>
  <div>
    <!-- Builder toolbar (spec section 20) -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <button class="btn-ghost" @click="router.push('/workflows')">← Workflows</button>
      <input
        v-model="nameDraft"
        class="input h-8 w-56 font-medium"
        @change="store.rename(workflowId, nameDraft)"
        @keydown.enter="($event.target as HTMLInputElement).blur()"
      />
      <span :class="store.current?.status === 'active' ? 'pill-success' : 'pill-neutral'">
        {{ store.current?.status === 'active' ? '● Active' : '○ Inactive' }}
      </span>
      <span class="text-xs text-muted">v{{ store.current?.current_version?.version_number ?? '—' }}</span>

      <div class="ml-auto flex items-center gap-2">
        <button class="btn-secondary" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
        <button class="btn-secondary" @click="validate">Validate</button>
        <button class="btn-secondary" :disabled="testing" @click="test">
          {{ testing ? 'Testing…' : 'Test' }}
        </button>
        <button
          class="btn"
          :class="store.current?.status === 'active' ? 'bg-warning text-white hover:bg-warning/90' : 'btn-primary'"
          @click="toggleDeploy"
        >
          {{ store.current?.status === 'active' ? 'Disable' : 'Deploy' }}
        </button>
      </div>
    </div>

    <!-- Three-column builder layout -->
    <div class="flex gap-4 h-[calc(100vh-15rem)] min-h-[480px]">
      <WorkflowNodePalette />
      <ClientOnly>
        <WorkflowCanvas
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
      <div class="flex flex-col gap-4 w-72 shrink-0">
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

    <p v-if="store.error" class="mt-3 text-sm text-error">{{ store.error }}</p>
  </div>
</template>
