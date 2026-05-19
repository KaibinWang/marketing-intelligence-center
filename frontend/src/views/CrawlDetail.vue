<template>
  <div>
    <el-button text size="small" @click="goBack" style="margin-bottom:12px">
      <el-icon><ArrowLeft /></el-icon> 返回数据源管理
    </el-button>

    <el-card shadow="never">
      <template #header>采集详情 #{{ crawlId }}</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据源" :span="1">
          {{ sourceName(record.source) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态" :span="1">
          <el-tag v-if="record.status === 'success'" type="success" size="small">成功</el-tag>
          <el-tag v-else-if="record.status === 'failed'" type="danger" size="small">失败</el-tag>
          <el-tag v-else type="info" size="small">运行中</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="采集条数" :span="1">{{ record.items_fetched }}</el-descriptions-item>
        <el-descriptions-item label="开始时间" :span="1">{{ record.started_at }}</el-descriptions-item>
        <el-descriptions-item label="完成时间" :span="1">{{ record.finished_at || '—' }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">
          <span style="white-space:pre-wrap">{{ record.error_msg || '无' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 正常情报 -->
    <el-card shadow="never" style="margin-top:16px">
      <template #header>本次采集的情报（{{ normalEvents.length }} 条）</template>
      <el-table :data="normalEvents" stripe size="small" v-if="normalEvents.length" @row-click="goEvent">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="company_name" label="企业名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="event_type" label="事件类型" width="100" />
        <el-table-column label="金额" width="100">
          <template #default="{ row }">{{ formatAmount(row.amount_estimate) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'sent'" type="success" size="small">已推送</el-tag>
            <el-tag v-else type="warning" size="small">未推送</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="采集时间" width="160" />
      </el-table>
      <el-empty v-else description="本次采集未产生新情报" />
    </el-card>

    <!-- 被过滤的情报 -->
    <el-card shadow="never" style="margin-top:16px" v-if="filteredEvents.length">
      <template #header>被地域规则过滤的情报（{{ filteredEvents.length }} 条）</template>
      <p class="text-muted" style="font-size:13px;margin:0 0 8px">这些情报因不满足当前地域过滤条件，未推送。</p>
      <el-table :data="filteredEvents" stripe size="small" @row-click="goEvent">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="company_name" label="企业名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="event_type" label="事件类型" width="100" />
        <el-table-column label="金额" width="100">
          <template #default="{ row }">{{ formatAmount(row.amount_estimate) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="采集时间" width="160" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getCrawlEvents } from '@/api'

const router = useRouter()
const route = useRoute()
const crawlId = Number(route.params.id)

const record = ref({})
const events = ref([])

const normalEvents = computed(() => events.value.filter(e => e.status !== 'filtered'))
const filteredEvents = computed(() => events.value.filter(e => e.status === 'filtered'))

function sourceName(src) {
  const names = { cninfo: '巨潮资讯网', pitchhub: '36氪融资快报', gdgov: '广东省政府采购中心' }
  return names[src] || src
}

function formatAmount(amount) {
  if (!amount || amount <= 0) return '—'
  if (amount >= 100000000) return (amount / 100000000).toFixed(1) + '亿'
  if (amount >= 10000) return Math.round(amount / 10000) + '万'
  return String(amount)
}

function goBack() {
  router.push('/sources')
}

function goEvent(row) {
  router.push(`/event/${row.id}`)
}

onMounted(async () => {
  const data = await getCrawlEvents(crawlId)
  record.value = data.record || {}
  events.value = data.events || []
})
</script>

<style scoped>
.text-muted { color: #909399; }
</style>
