import { defineStore } from 'pinia'
import type {
  NodeMeta,
  ValidationReport,
  Workflow,
  WorkflowDefinition,
  WorkflowRun,
} from '~/types'

export const useWorkflowsStore = defineStore('workflows', {
  state: () => ({
    list: [] as Workflow[],
    current: null as Workflow | null,
    nodeTypes: [] as NodeMeta[],
    lastReport: null as ValidationReport | null,
    lastRun: null as WorkflowRun | null,
    loading: false,
    saving: false,
    error: '' as string,
  }),

  actions: {
    async fetchList() {
      const api = useApi()
      this.loading = true
      this.error = ''
      try {
        this.list = await api<Workflow[]>('/workflows')
      } catch {
        this.error = 'Could not reach the Bridge backend. Is the API server running?'
      } finally {
        this.loading = false
      }
    },

    async fetchOne(id: number) {
      const api = useApi()
      this.loading = true
      this.error = ''
      try {
        this.current = await api<Workflow>(`/workflows/${id}`)
      } catch {
        this.error = 'Could not load this workflow.'
      } finally {
        this.loading = false
      }
    },

    async fetchNodeTypes() {
      if (this.nodeTypes.length) return
      const api = useApi()
      try {
        this.nodeTypes = await api<NodeMeta[]>('/workflows/node-types')
      } catch {
        this.nodeTypes = []
      }
    },

    async create(name: string): Promise<Workflow | null> {
      const api = useApi()
      try {
        const created = await api<Workflow>('/workflows', { method: 'POST', body: { name } })
        await this.fetchList()
        return created
      } catch {
        this.error = 'Could not create the workflow.'
        return null
      }
    },

    async saveVersion(id: number, definition: WorkflowDefinition, comment = '') {
      const api = useApi()
      this.saving = true
      try {
        this.current = await api<Workflow>(`/workflows/${id}/versions`, {
          method: 'POST',
          body: { definition, comment },
        })
        return true
      } catch {
        this.error = 'Saving the workflow failed.'
        return false
      } finally {
        this.saving = false
      }
    },

    async validate(id: number) {
      const api = useApi()
      try {
        this.lastReport = await api<ValidationReport>(`/workflows/${id}/validate`, { method: 'POST' })
      } catch {
        this.lastReport = null
      }
    },

    async testRun(id: number, payload: Record<string, unknown> = {}) {
      const api = useApi()
      this.lastRun = null
      try {
        this.lastRun = await api<WorkflowRun>(`/workflows/${id}/test-run`, {
          method: 'POST',
          body: { payload },
        })
      } catch {
        this.lastRun = null
      }
    },

    async rename(id: number, name: string) {
      const api = useApi()
      try {
        this.current = await api<Workflow>(`/workflows/${id}`, { method: 'PATCH', body: { name } })
        const entry = this.list.find((w) => w.id === id)
        if (entry) entry.name = name
      } catch {
        this.error = 'Renaming the workflow failed.'
      }
    },

    async toggleStatus(workflow: Workflow) {
      const api = useApi()
      const next = workflow.status === 'active' ? 'inactive' : 'active'
      try {
        await api(`/workflows/${workflow.id}`, { method: 'PATCH', body: { status: next } })
        workflow.status = next
        if (this.current?.id === workflow.id) this.current.status = next
      } catch {
        this.error = 'Could not change the workflow status.'
      }
    },
  },
})
