<template>
  <div>
    <el-card shadow="never">
      <template #header>数据源状态</template>
      <el-table :data="sources" stripe>
        <el-table-column label="数据源">
          <template #default="{ row }">{{ sourceName(row.source) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.last_run && row.last_run.status === 'success'" type="success" size="small">正常</el-tag>
            <el-tag v-else-if="row.last_run && row.last_run.status === 'failed'" type="danger" size="small">异常</el-tag>
            <el-tag v-else type="info" size="small">从未采集</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近采集时间" width="180">
          <template #default="{ row }">{{ row.last_run?.finished_at || '—' }}</template>
        </el-table-column>
        <el-table-column label="最近结果" width="120">
          <template #default="{ row }">
            <template v-if="row.last_run">
              {{ row.last_run.items_fetched }} 条
              <div v-if="row.last_run.error_msg" class="text-danger small">{{ row.last_run.error_msg.slice(0, 50) }}</div>
            </template>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="成功次数" width="80" prop="success_count" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openCrawl(row.source)">立即采集</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header>最近采集记录</template>
      <el-table :data="history" stripe @row-click="goCrawlDetail" style="cursor:pointer">
        <el-table-column label="数据源">
          <template #default="{ row }">{{ sourceName(row.source) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'success'" type="success" size="small">成功</el-tag>
            <el-tag v-else type="danger" size="small">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="采集条数" width="80" prop="items_fetched" />
        <el-table-column label="开始时间" width="180" prop="started_at" />
        <el-table-column label="完成时间" width="180" prop="finished_at" />
        <el-table-column label="错误信息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error_msg || '—' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!history.length" description="暂无采集记录" />
    </el-card>

    <!-- Crawl Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" :close-on-click-modal="false" @close="closeDialog">
      <!-- Step 1: keyword selection (cninfo only) -->
      <template v-if="step === 'select'">
        <p class="text-muted" style="margin-bottom:12px">勾选需要采集的公告类型：</p>
        <div v-for="group in keywordGroups" :key="group.label" style="margin-bottom:8px">
          <el-checkbox v-model="group.checked" @change="updateKeywords">
            <strong>{{ group.label }}</strong>
            <span class="text-muted">（{{ group.desc }}）</span>
          </el-checkbox>
        </div>
        <el-checkbox v-model="selectAll" @change="toggleAll" style="margin-top:4px">全选/取消</el-checkbox>
      </template>
      <!-- Step 2: progress -->
      <template v-if="step === 'progress'">
        <el-progress :percentage="progressPct" :stroke-width="12" />
        <p style="margin:8px 0;font-size:13px">{{ currentMsg }}</p>
        <div class="log-area" ref="logRef">
          <div v-for="(log, i) in logs" :key="i" :class="log.cls">{{ log.text }}</div>
        </div>
      </template>
      <template #footer>
        <el-button v-if="step === 'select'" @click="dialogVisible = false">取消</el-button>
        <el-button v-if="step === 'select'" type="primary" @click="startCrawl">开始采集</el-button>
        <el-button v-if="step === 'progress' && progressDone" type="primary" @click="dialogVisible = false">关闭</el-button>
        <el-button v-if="step === 'progress' && !progressDone" type="danger" plain @click="handleCancel">取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getSources, getCrawlStatus, cancelCrawl, triggerCrawl } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const sources = ref([])
const history = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const step = ref('select')
const currentMsg = ref('')
const progressPct = ref(0)
const logs = ref([])
const logRef = ref(null)
const progressDone = ref(false)

const currentSource = ref('')
let crawlId = null
let pollTimer = null

const keywordGroups = reactive([
  { label: '中标情报', keywords: ['中标', '成交'], desc: '中标/成交公告', checked: true },
  { label: '融资情报', keywords: ['融资'], desc: '融资相关公告', checked: true },
  { label: '重大事项', keywords: ['对外投资', '扩产', '并购'], desc: '对外投资/扩产/并购', checked: true },
  { label: '政府补助', keywords: ['政府补助'], desc: '政府补助公告', checked: true },
])
const selectAll = ref(true)

function sourceName(src) {
  const names = { cninfo: '巨潮资讯网', pitchhub: '36氪融资快报', gdgov: '广东省政府采购中心', ygp: '广东省公共资源交易平台' }
  return names[src] || src
}

function toggleAll(val) {
  keywordGroups.forEach(g => g.checked = val)
}

function updateKeywords() {
  selectAll.value = keywordGroups.every(g => g.checked)
}

function openCrawl(source) {
  currentSource.value = source
  dialogTitle.value = `立即采集 - ${sourceName(source)}`
  dialogVisible.value = true

  if (source === 'cninfo') {
    step.value = 'select'
  } else {
    step.value = 'progress'
    doCrawl([])
  }
}

function startCrawl() {
  const selected = []
  keywordGroups.forEach(g => {
    if (g.checked) g.keywords.forEach(k => { if (!selected.includes(k)) selected.push(k) })
  })
  step.value = 'progress'
  doCrawl(selected)
}

async function doCrawl(keywords) {
  progressPct.value = 0
  currentMsg.value = '正在启动...'
  logs.value = []
  progressDone.value = false

  try {
    const data = await triggerCrawl(currentSource.value, keywords)
    if (!data.crawl_id) {
      addLog('触发失败', 'err')
      progressDone.value = true
      return
    }
    crawlId = data.crawl_id
    addLog(`任务已启动 (ID: ${data.crawl_id})`, 'done')
    pollStatus()
  } catch (e) {
    addLog('触发失败: ' + (e.message || ''), 'err')
    progressDone.value = true
  }
}

function pollStatus() {
  function tick() {
    getCrawlStatus(crawlId).then(data => {
      const progress = data.progress || []
      const last = progress.length ? progress[progress.length - 1] : null
      if (last) {
        progressPct.value = Math.max(last.pct, 5)
        currentMsg.value = last.message
      }
      const existing = logs.value.length
      for (let i = existing; i < progress.length; i++) {
        const p = progress[i]
        addLog(p.time + ' ' + p.message, p.pct >= 100 ? 'done' : p.pct === 0 ? 'err' : '')
      }

      if (data.status === 'success') {
        currentMsg.value = '采集完成'
        progressPct.value = 100
        progressDone.value = true
        refreshSources()
        return
      }
      if (data.status === 'failed') {
        currentMsg.value = '采集失败'
        addLog(data.error_msg || '未知错误', 'err')
        progressDone.value = true
        refreshSources()
        return
      }
      pollTimer = setTimeout(tick, 1000)
    }).catch(() => {
      pollTimer = setTimeout(tick, 2000)
    })
  }
  tick()
}

function addLog(text, type) {
  const cls = type === 'done' ? 'text-success' : type === 'err' ? 'text-danger' : ''
  logs.value.push({ text, cls })
  nextTick(() => {
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

async function handleCancel() {
  if (!crawlId) return
  addLog('正在请求取消...', 'err')
  try {
    await cancelCrawl(crawlId)
    addLog('已发送取消请求', 'err')
  } catch {}
}

function closeDialog() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  crawlId = null
}

async function refreshSources() {
  const data = await getSources()
  sources.value = data.sources
}

function goCrawlDetail(row) {
  router.push(`/crawl/${row.id}`)
}

onMounted(async () => {
  const data = await getSources()
  sources.value = data.sources
  history.value = data.history || []
})
</script>

<style scoped>
.log-area {
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 12px;
  font-family: monospace;
  max-height: 250px;
  overflow-y: auto;
  line-height: 1.8;
}
.text-muted { color: #909399; }
</style>
