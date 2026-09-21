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

    <!-- 服务端收缩：状态多选 + 样例名关键字，可叠加；两种角色均可使用 -->
    <div class="row items-center q-col-gutter-md q-mb-md">
      <div class="col-12 col-md-auto">
        <q-option-group
          v-model="statuses"
          :options="statusOptions"
          option-value="value"
          option-label="label"
          type="checkbox"
          inline
          color="primary"
          class="status-filter-group"
        />
      </div>
      <div class="col-12 col-sm-5 col-md-4 col-lg-3">
        <q-input
          v-model="keyword"
          dense
          outlined
          clearable
          debounce="300"
          label="样例名关键字"
          @update:model-value="onFilterChange"
        >
          <template #append>
            <q-icon name="search" class="q-pr-sm" />
          </template>
        </q-input>
      </div>
      <div class="col-auto">
        <q-btn
          flat
          dense
          icon="clear_all"
          label="清除筛选"
          :disable="!statuses.length && !keyword"
          @click="resetFilters"
        />
      </div>
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
      <!-- 未命中时只给说明，绝不在前端回退成全量 -->
      <template #no-data>
        <div class="full-width flex flex-center q-pa-xl text-grey-7">
          <div class="text-center">
            <q-icon name="filter_alt_off" size="40px" class="q-mb-sm" />
            <div>没有符合当前筛选条件的作业</div>
            <div class="text-caption q-mt-xs">
              服务端未返回数据，可调整勾选状态或关键字后重试
            </div>
          </div>
        </div>
      </template>
    </q-table>
  </q-page>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { useRoute, useRouter } from 'vue-router'
import { listJobs } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const rows = ref([])
const statuses = ref([])
const keyword = ref('')

const VALID_STATUSES = ['pending', 'running', 'success', 'failed']

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

// 选项标签复用既有本地映射，映射本身保持不变
const statusOptions = VALID_STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))

function statusLabel(s) {
  return { pending: '排队中', running: '运行中', success: '成功', failed: '失败' }[s] || s
}

function statusColor(s) {
  return { pending: 'grey', running: 'info', success: 'positive', failed: 'negative' }[s] || 'grey'
}

async function load() {
  loading.value = true
  try {
    // 条件原样带给服务端，空结果即空表，不做任何全量回退
    rows.value = await listJobs({
      statuses: [...statuses.value],
      q: keyword.value,
    })
  } catch (e) {
    $q.notify({ type: 'negative', message: e.message || '加载失败' })
  } finally {
    loading.value = false
  }
}

function syncQuery() {
  // 条件写入 URL，刷新后可恢复
  const query = {}
  if (statuses.value.length) query.status = [...statuses.value]
  if (keyword.value.trim()) query.q = keyword.value.trim()
  router.replace({ query })
}

function onFilterChange() {
  syncQuery()
  load()
}

function resetFilters() {
  statuses.value = []
  keyword.value = ''
  onFilterChange()
}

// 复选勾选立即触发；关键字输入依赖 q-input 的 debounce，到这里已防抖。
// initialized 守卫：避免 onMounted 回填状态时 watch 与显式 load 重复请求。
const initialized = ref(false)
watch(
  statuses,
  () => {
    if (initialized.value) onFilterChange()
  },
  { deep: true },
)

onMounted(() => {
  const raw = route.query.status
  const list = Array.isArray(raw) ? raw : raw ? [raw] : []
  statuses.value = list.filter((s) => VALID_STATUSES.includes(s))
  keyword.value = typeof route.query.q === 'string' ? route.query.q : ''
  initialized.value = true
  load()
})
</script>
