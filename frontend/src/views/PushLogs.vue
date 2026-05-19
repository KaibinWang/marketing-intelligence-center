<template>
  <div>
    <el-card shadow="never" style="margin-bottom:8px">
      <el-form inline @submit.prevent="loadData">
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" style="width:110px">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">筛选</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="table-info">共 <strong>{{ total }}</strong> 条记录，第 <strong>{{ page }}</strong> / <strong>{{ pages }}</strong> 页</div>

    <el-card shadow="never">
      <el-table :data="logs" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="企业名称" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :href="`/event/${row.event_id}`">{{ row.company_name || '—' }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="event_type" label="事件类型" width="100" />
        <el-table-column prop="channel" label="推送渠道" width="100" />
        <el-table-column prop="push_time" label="推送时间" width="170" />
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'success'" type="success" size="small">成功</el-tag>
            <el-tag v-else type="danger" size="small">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error_msg || '—' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!logs.length && !loading" description="暂无推送记录" />
      <div style="margin-top:16px;display:flex;justify-content:center">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          small
          background
          @current-change="loadData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPushLogs } from '@/api'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pages = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getPushLogs(params)
    logs.value = res.items
    total.value = res.total
    pages.value = res.pages
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.table-info { font-size: 13px; color: #909399; margin: 8px 0; }
</style>
