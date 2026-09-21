<template>
  <q-page class="page-pad">
    <div class="row items-center q-mb-md">
      <div class="text-h5">作业历史</div>
      <q-space />
      <q-btn flat icon="refresh" label="刷新" @click="load" :loading="loading" />
      <q-btn
        v-if="auth.role === 'bioops'"
        color="primary"
        class="q-ml-sm"
        label="新建作业"
        to="/jobs/new"
      />
    </div>

    <div class="row items-center q-gutter-sm q-mb-md">
      <q-select
        v-model="selectedStatuses"
        :options="statusOptions"
        multiple
        emit-value
        map-options
        use-chips
        options-dense
        dense
        outlined
        label="状态（可多选）"
        style="min-width: 280px"
      />
      <q-input
        v-model="keyword"
        dense
        outlined
        clearable
        debounce="400"
        label="样例名关键字"
        placeholder="按样例名模糊匹配"
        style="min-width: 220px"
      />
      <q-btn
        v-if="hasFilter"
        flat
        dense
        color="primary"
        label="清除筛选"
        @click="resetFilters"
      />
    </div>

    <q-table
      flat
      bordered
      row-key="id"
      :rows="rows"
      :columns="columns"
      :loading="loading"
      hide-pagination
      :pagination="{ rowsPerPage: 0 }"
    >
      <template #body-cell-status="props">
        <q-td :props="props">
          <q-badge :color="statusColor(props.row.status)">
            {{ statusLabel(props.row.status) }}
          </q-badge>
        </q-td>
      </template>
      <template #body-cell-metrics="props">
        <q-td :props="props">
          <span v-if="props.row.metrics">
            Q={{ props.row.metrics.mean_quality ?? '—' }}
            · N={{ props.row.metrics.n_rate ?? '—' }}
            · reads={{ props.row.metrics.reads ?? '—' }}
          </span>
          <span v-else class="text-grey-6">—</span>
        </q-td>
      </template>
      <template #body-cell-actions="props">
        <q-td :props="props">
          <q-btn dense flat color="primary" label="详情" :to="`/jobs/${props.row.id}`" />
        </q-td>
      </template>
      <template #no-data>
        <div class="full-width column items-center q-pa-xl text-grey-7">
          <q-icon name="search_off" size="42px" class="q-mb-sm" />
          <template v-if="hasFilter">
            <div>没有命中当前筛选条件的作业记录（{{ filterSummary }}）</div>
            <div class="text-caption q-mt-xs">筛选在服务端生效，结果为空时不会回退为全量列表</div>
            <q-btn
              flat
              dense
              color="primary"
              class="q-mt-sm"
              label="清除筛选条件"
              @click="resetFilters"
            />
          </template>
          <div v-else>暂无作业记录</div>
        </div>
      </template>
    </q-table>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { listJobs } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const rows = ref([])

const KNOWN_STATUSES = ['pending', 'running', 'success', 'failed']

function parseStatuses(value) {
  if (!value) return []
  const parts = Array.isArray(value) ? value : String(value).split(',')
  return parts.map((s) => s.trim()).filter((s) => KNOWN_STATUSES.includes(s))
}

// 从 URL query 恢复筛选条件（刷新后条件可恢复）
const selectedStatuses = ref(parseStatuses(route.query.status))
const keyword = ref(typeof route.query.keyword === 'string' ? route.query.keyword : '')

const keywordText = computed(() => (keyword.value ?? '').trim())
const hasFilter = computed(() => selectedStatuses.value.length > 0 || keywordText.value !== '')
const filterSummary = computed(() => {
  const parts = []
  if (selectedStatuses.value.length) {
    parts.push(`状态：${selectedStatuses.value.map(statusLabel).join('、')}`)
  }
  if (keywordText.value) {
    parts.push(`关键字：${keywordText.value}`)
  }
  return parts.join(' · ')
})

const columns = [
  { name: 'id', label: 'ID', field: 'id', align: 'left' },
  { name: 'sample_name', label: '样例', field: 'sample_name', align: 'left' },
  { name: 'status', label: '状态', field: 'status', align: 'left' },
  { name: 'created_by', label: '提交人', field: 'created_by', align: 'left' },
  { name: 'metrics', label: '指标摘要', field: 'metrics', align: 'left' },
  {
    name: 'created_at',
    label: '创建时间',
    field: 'created_at',
    align: 'left',
    format: (v) => (v ? new Date(v).toLocaleString() : ''),
  },
  { name: 'actions', label: '操作', field: 'actions', align: 'left' },
]

function statusLabel(s) {
  return { pending: '排队中', running: '运行中', success: '成功', failed: '失败' }[s] || s
}

function statusColor(s) {
  return { pending: 'grey', running: 'info', success: 'positive', failed: 'negative' }[s] || 'grey'
}

const statusOptions = KNOWN_STATUSES.map((s) => ({ label: statusLabel(s), value: s }))

async function load() {
  loading.value = true
  try {
    rows.value = await listJobs({
      statuses: selectedStatuses.value,
      keyword: keywordText.value,
    })
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '加载失败' })
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  selectedStatuses.value = []
  keyword.value = ''
}

// 条件变化：同步到 URL query（可刷新恢复）并重新向服务端请求
watch([selectedStatuses, keyword], () => {
  const query = {}
  if (selectedStatuses.value.length) query.status = selectedStatuses.value.join(',')
  if (keywordText.value) query.keyword = keywordText.value
  router.replace({ query })
  load()
})

onMounted(load)
</script>
