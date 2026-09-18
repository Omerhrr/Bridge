<script setup lang="ts">
interface Health {
  status: string;
  service: string;
  version: string;
}

interface Item {
  id: number;
  name: string;
  description: string;
}

const config = useRuntimeConfig();
const apiBase = config.public.apiBase || "";

const health = ref<Health | null>(null);
const items = ref<Item[]>([]);
const newName = ref("");
const newDescription = ref("");
const error = ref("");

async function fetchHealth() {
  try {
    health.value = await $fetch<Health>(`${apiBase}/api/health`);
  } catch {
    health.value = null;
  }
}

async function fetchItems() {
  try {
    items.value = await $fetch<Item[]>(`${apiBase}/api/items`);
  } catch (e) {
    error.value = "Could not reach the API. Is the backend running on port 8000?";
  }
}

async function addItem() {
  if (!newName.value.trim()) return;
  try {
    await $fetch(`${apiBase}/api/items`, {
      method: "POST",
      body: { name: newName.value, description: newDescription.value },
    });
    newName.value = "";
    newDescription.value = "";
    error.value = "";
    await fetchItems();
  } catch {
    error.value = "Failed to create item.";
  }
}

async function removeItem(id: number) {
  try {
    await $fetch(`${apiBase}/api/items/${id}`, { method: "DELETE" });
    await fetchItems();
  } catch {
    error.value = "Failed to delete item.";
  }
}

onMounted(async () => {
  await Promise.all([fetchHealth(), fetchItems()]);
});
</script>

<template>
  <main class="container">
    <header>
      <h1>Bridge</h1>
      <p class="subtitle">FastAPI + Nuxt + Vue starter</p>
      <p v-if="health" class="badge badge-ok">
        API online · {{ health.service }} v{{ health.version }}
      </p>
      <p v-else class="badge badge-down">
        API offline — start the backend: <code>uvicorn app.main:app --reload</code>
      </p>
    </header>

    <section class="panel">
      <h2>Add an item</h2>
      <form class="form" @submit.prevent="addItem">
        <input v-model="newName" type="text" placeholder="Name" required />
        <input v-model="newDescription" type="text" placeholder="Description (optional)" />
        <button type="submit">Add</button>
      </form>
    </section>

    <section class="panel">
      <h2>Items</h2>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="items.length === 0" class="empty">No items yet — add one above.</p>
      <ul v-else class="item-list">
        <li v-for="item in items" :key="item.id" class="item">
          <div>
            <strong>{{ item.name }}</strong>
            <span v-if="item.description" class="desc"> — {{ item.description }}</span>
          </div>
          <button class="danger" @click="removeItem(item.id)">Delete</button>
        </li>
      </ul>
    </section>
  </main>
</template>
