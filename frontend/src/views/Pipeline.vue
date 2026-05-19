<template>
  <div>
    <div style="text-align:center;padding:24px 0">
      <el-button type="primary" size="large" :loading="running" @click="handleRun">
        <el-icon style="margin-right:6px"><VideoPlay /></el-icon>
        执行完整采集
      </el-button>
      <p v-if="statusMsg" class="text-muted" style="margin-top:8px">{{ statusMsg }}</p>
    </div>

    <div v-if="latestRunVisible" style="margin-bottom:16px">
      <el-card shadow="never">
        <template #header>最近一次采集结果</template>
        <div v-if="latestResult">
          <el-row :gutter="16" class="result-stats">
            <el-col :span="6"><div class="stat-item"><span class="text-success stat-num">{{ latestResult.total_new }}</span><small>新增情报</small></div></el-col>
            <el-col :span="6"><div class="stat-item"><span class="text-warning stat-num">{{ latestResult.total_dup }}</span><small>重复跳过</small></div></el-col>
            <el-col :span="6"><div class="stat-item"><span class="text-secondary stat-num">{{ latestResult.total_filtered }}</span><small>地域过滤</small></div></el-col>
            <el-col :span="6"><div class="stat-item"><span class="text-primary stat-num">{{ latestResult.total_pushed }}</span><small>已推送</small></div></el-col>
          </el-row>
          <el-table :data="sourceRows" stripe size="small" style="margin-top:12px">
            <el-table-column label="数据源">
              <template #default="{ row }">{{ sourceName(row.name) }}</template>
            </el-table-column>
            <el-table-column prop="new" label="新增" width="60" />
            <el-table-column prop="dup" label="重复" width="60" />
            <el-table-column prop="filtered" label="过滤" width="60" />
            <el-table-column prop="pushed" label="推送" width="60" />
          </el-table>
          <div v-if="latestResult.errors && latestResult.errors.length" style="margin-top:12px">
            <el-alert title="错误信息" type="error" :description="latestResult.errors.join('; ')" show-icon />
          </div>
        </div>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header>采集历史</template>
      <el-table :data="history" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'running'" type="info" size="small">运行中</el-tag>
            <el-tag v-else-if="row.status === 'completed'" type="success" size="small">完成</el-tag>
            <el-tag v-else type="danger" size="small">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="180" />
        <el-table-column prop="finished_at" label="完成时间" width="180" />
        <el-table-column label="新增" width="60">
          <template #default="{ row }">{{ row.summary?.total_new || '—' }}</template>
        </el-table-column>
        <el-table-column label="推送" width="60">
          <template #default="{ row }">{{ row.summary?.total_pushed || '—' }}</template>
        </el-table-column>
        <el-table-column label="错误" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.summary?.errors?.length" class="text-danger">{{ row.summary.errors.length }} 个</span>
            <span v-else-if="row.error_msg" class="text-danger">{{ row.error_msg.slice(0, 40) }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!history.length" description="暂无采集记录" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { runPipeline, getPipelineLatest, getPipelineRuns } from '@/api'
import { ElMessage } from 'element-plus'

const running = ref(false)
const statusMsg = ref('')
const latestRunVisible = ref(false)
const latestResult = ref(null)
const history = ref([])

const sourceRows = computed(() => {
  if (!latestResult.value?.sources) return []
  return Object.entries(latestResult.value.sources).map(([name, data]) => ({ name, ...data }))
})

function sourceName(src) {
  const names = { cninfo: '巨潮资讯网', pitchhub: '36氪融资快报', gdgov: '广东省政府采购中心' }
  return names[src] || src
}

async function handleRun() {
  running.value = true
  statusMsg.value = '正在启动完整采集...'
  try {
    await runPipeline()
    statusMsg.value = '采集已触发，轮询结果...'
    await pollResult()
  } catch (e) {
    statusMsg.value = '触发失败'
    running.value = false
  }
}

async function pollResult() {
  const maxAttempts = 120
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 1000))
    try {
      const data = await getPipelineLatest()
      if (data.status === 'running') {
        statusMsg.value = `采集中... (${i + 1}s)`
        continue
      }
      if (data.status === 'completed') {
        latestResult.value = data.summary || {}
        latestRunVisible.value = true
        statusMsg.value = '采集完成'
        running.value = false
        await loadHistory()
        // Reload page to refresh everything
        setTimeout(() => location.reload(), 2000)
        return
      }
      break
    } catch {}
  }
  statusMsg.value = '采集超时'
  running.value = false
}

async function loadHistory() {
  try {
    const data = await getPipelineRuns(20)
    history.value = data.items || []
  } catch {}
}

onMounted(async () => {
  await loadHistory()
  const latest = await getPipelineLatest()
  if (latest && latest.status === 'completed' && latest.summary) {
    latestResult.value = latest.summary
    latestRunVisible.value = true
  }
})
</script>

<style scoped>
.result-stats { text-align: center; }
.stat-item { padding: 12px 0; }
.stat-num { display: block; font-size: 28px; font-weight: 700; }
.stat-item small { font-size: 13px; color: #909399; }
.text-muted { color: #909399; font-size: 13px; }
</style>
