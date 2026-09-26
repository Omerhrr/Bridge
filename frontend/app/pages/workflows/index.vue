<script setup lang="ts">
import { Plus } from 'lucide-vue-next'

definePageMeta({ layout: 'default' })

const store = useWorkflowsStore()
const router = useRouter()
const newName = ref('')
const creating = ref(false)

onMounted(() => store.fetchList())

async function create() {
  const name = newName.value.trim()
  if (!name) return
  creating.value = true
  const workflow = await store.create(name)
  creating.value = false
  if (workflow) router.push(`/workflows/${workflow.id}`)
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">Workflows</h1>
        <p class="text-sm text-muted mt-0.5">Visual communication logic: triggers, AI transformations, responses</p>
      </div>
    </div>

    <!-- Create form -->
    <form class="card p-4 mb-4 flex flex-col sm:flex-row gap-3 sm:items-center" @submit.prevent="create">
      <input v-model="newName" type="text" placeholder="New workflow name, e.g. Voice Translator EN to HA" class="input sm:max-w-md" required />
      <button type="submit" class="btn-primary" :disabled="creating || !newName.trim()">
        <Plus class="w-4 h-4" :stroke-width="2" />
        {{ creating ? 'Creating…' : 'New Workflow' }}
      </button>
    </form>

    <p v-if="store.error" class="text-sm text-error mb-4">{{ store.error }}</p>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="card p-4 h-20 animate-pulse" />
    </div>

    <!-- List -->
    <div v-else-if="store.list.length" class="space-y-3">
      <div
        v-for="workflow in store.list"
        :key="workflow.id"
        class="card p-4 flex flex-col sm:flex-row sm:items-center gap-3 hover:border-signal/40 transition-colors"
      >
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <NuxtLink :to="`/workflows/${workflow.id}`" class="text-sm font-semibold hover:text-signal transition-colors">
              {{ workflow.name }}
            </NuxtLink>
            <span :class="workflow.status === 'active' ? 'pill-success' : 'pill-neutral'">
              {{ workflow.status === 'active' ? '● Active' : '○ Inactive' }}
            </span>
            <span class="pill-neutral">v{{ workflow.current_version?.version_number ?? 1 }}</span>
          </div>
          <p class="text-sm text-muted mt-1 truncate">{{ workflow.description || 'No description' }}</p>
        </div>
        <div class="flex items-center gap-2 sm:shrink-0">
          <span class="text-xs text-muted hidden md:inline">updated {{ formatDate(workflow.updated_at) }}</span>
          <NuxtLink :to="`/workflows/${workflow.id}`" class="btn-secondary">Open builder</NuxtLink>
          <button class="btn-secondary" @click="store.toggleStatus(workflow)">
            {{ workflow.status === 'active' ? 'Disable' : 'Deploy' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="card p-12 text-center">
      <p class="text-sm font-medium">No workflows yet</p>
      <p class="text-sm text-muted mt-1">Create one and build your first communication flow on the canvas.</p>
    </div>
  </div>
</template>
