<template>
  <div class="event-list">
    <el-card shadow="never" class="filter-card">
      <el-form :model="filters" inline @submit.prevent="search">
        <el-form-item label="事件类型">
          <el-select v-model="filters.event_type" clearable placeholder="全部" style="width:130px">
            <el-option label="中标" value="中标" />
            <el-option label="融资" value="融资" />
            <el-option label="对外投资" value="对外投资" />
            <el-option label="扩产" value="扩产" />
            <el-option label="并购" value="并购" />
            <el-option label="政府补助" value="政府补助" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="企业名称">
          <el-input v-model="filters.company" clearable placeholder="搜索企业名" style="width:150px" />
        </el-form-item>
        <el-form-item label="数据源">
          <el-select v-model="filters.source" clearable placeholder="全部" style="width:170px">
            <el-option label="巨潮资讯网" value="巨潮资讯网" />
            <el-option label="36氪融资快报" value="36氪融资快报" />
            <el-option label="广东省政府采购中心" value="广东省政府采购中心" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width:110px">
            <el-option label="未推送" value="new" />
            <el-option label="已推送" value="sent" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="起始日期"
            end-placeholder="截止日期"
            value-format="YYYY-MM-DD"
            style="width:240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">筛选</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="table-info">
      共 <strong>{{ total }}</strong> 条记录，第 <strong>{{ page }}</strong> / <strong>{{ pages }}</strong> 页
    </div>

    <el-card shadow="never">
      <el-table :data="events" v-loading="loading" stripe @row-click="goDetail" style="cursor:pointer">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="事件类型" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="company_name" label="企业名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="stock_code" label="股票代码" width="90" />
        <el-table-column label="金额" width="100">
          <template #default="{ row }">
            {{ formatAmount(row.amount_estimate) }}
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.source }}</span>
            <el-tag v-if="row.source_url && row.source_url.startsWith('pitchhub://')" size="small" type="info" effect="plain">无原文</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="入库时间" width="160" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'sent'" type="success" size="small">已推送</el-tag>
            <el-tag v-else type="warning" size="small">未推送</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="155" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click.stop="goDetail(row)">查看</el-button>
            <el-button v-if="row.status !== 'sent'" size="small" type="success" @click.stop="handleMarkSent(row)">发送</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          small
          background
          @current-change="loadData"
        />
        <el-popconfirm title="确定要清空所有情报数据吗？此操作不可恢复！" @confirm="handleClear">
          <template #reference>
            <el-button size="small" type="danger" plain>清空全部情报</el-button>
          </template>
        </el-popconfirm>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listEvents, markSent, clearEvents } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const events = ref([])
const total = ref(0)
const page = ref(1)
const pages = ref(1)
const pageSize = 20
const loading = ref(false)

const filters = reactive({
  event_type: '',
  company: '',
  source: '',
  status: '',
})
const dateRange = ref(null)

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filters.event_type) params.event_type = filters.event_type
    if (filters.company) params.company = filters.company
    if (filters.source) params.source = filters.source
    if (filters.status) params.status = filters.status
    if (dateRange.value) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await listEvents(params)
    events.value = res.items
    total.value = res.total
    pages.value = res.pages
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  loadData()
}

function reset() {
  filters.event_type = ''
  filters.company = ''
  filters.source = ''
  filters.status = ''
  dateRange.value = null
  page.value = 1
  loadData()
}

function goDetail(row) {
  router.push(`/event/${row.id}`)
}

async function handleMarkSent(row) {
  try {
    await markSent(row.id)
    ElMessage.success('发送成功')
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  }
}

async function handleClear() {
  try {
    await clearEvents()
    ElMessage.success('已清空全部数据')
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '清空失败')
  }
}

function formatAmount(amount) {
  if (!amount || amount <= 0) return '—'
  if (amount >= 100000000) return (amount / 100000000).toFixed(1) + '亿'
  if (amount >= 10000) return Math.round(amount / 10000) + '万'
  return String(amount)
}

onMounted(loadData)
</script>

<style scoped>
.filter-card { margin-bottom: 12px; }
.filter-card .el-form { display: flex; flex-wrap: wrap; align-items: flex-start; }
.filter-card .el-form-item { margin-bottom: 0; }
.table-info { font-size: 13px; color: #909399; margin: 8px 0; }
.table-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; }
</style>
