<template>
  <div v-loading="loading">
    <el-button text @click="$router.back()">
      <el-icon><ArrowLeft /></el-icon> 返回列表
    </el-button>

    <template v-if="event">
      <h2 style="margin:16px 0">{{ event.event_type }}情报</h2>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>基本信息</template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="企业名称">{{ event.company_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="股票代码">{{ event.stock_code || '—' }}</el-descriptions-item>
              <el-descriptions-item label="事件类型">
                <el-tag type="info" size="small">{{ event.event_type }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="项目/事项">{{ event.project_or_subject || '—' }}</el-descriptions-item>
              <el-descriptions-item label="金额">{{ formatAmount(event.amount_estimate) }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
          <el-card shadow="never" style="margin-top:16px">
            <template #header>来源信息</template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="数据来源">{{ event.source || '—' }}</el-descriptions-item>
              <el-descriptions-item label="发布时间">{{ event.pub_date || '—' }}</el-descriptions-item>
              <el-descriptions-item label="入库时间">{{ event.created_at }}</el-descriptions-item>
              <el-descriptions-item label="原文链接">
                <template v-if="!event.source_url">
                  <el-tag type="info" size="small">无原文链接</el-tag>
                </template>
                <template v-else-if="event.source_url.startsWith('pitchhub://') || event.source_url.startsWith('ygp://')">
                  <el-tag type="info" size="small">无独立原文页面</el-tag>
                </template>
                <template v-else-if="event.source_url.includes('ygp.gdzwfw.gov.cn') && !event.source_url.includes('bizCode')">
                  <span>{{ event.source_url.slice(0, 60) }}…
                    <el-tag type="warning" size="small">链接可能无法直接访问</el-tag>
                  </span>
                </template>
                <el-link v-else :href="event.source_url" type="primary" target="_blank">查看原文</el-link>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>AI 营销建议</template>
            <div class="suggestion-box">{{ event.marketing_suggestion || '暂无建议' }}</div>
          </el-card>
          <el-card shadow="never" style="margin-top:16px">
            <template #header>推送状态</template>
            <el-tag v-if="event.status === 'sent'" type="success" size="large">已推送</el-tag>
            <el-button v-else type="success" @click="handleMarkSent">标记为已推送</el-button>
          </el-card>
        </el-col>
      </el-row>

      <el-card v-if="event.detail_text" shadow="never" style="margin-top:16px">
        <template #header>原文详情</template>
        <div class="scrollable-text">{{ event.detail_text }}</div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getEvent, markSent } from '@/api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const event = ref(null)
const loading = ref(true)

async function loadData() {
  try {
    event.value = await getEvent(route.params.id)
  } finally {
    loading.value = false
  }
}

async function handleMarkSent() {
  try {
    await markSent(route.params.id)
    ElMessage.success('标记成功')
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

function formatAmount(amount) {
  if (!amount || amount <= 0) return '未披露'
  if (amount >= 100000000) return (amount / 100000000).toFixed(1) + ' 亿元'
  if (amount >= 10000) return Math.round(amount / 10000) + ' 万元'
  return amount + ' 元'
}

onMounted(loadData)
</script>

<style scoped>
.suggestion-box {
  background: #ecf5ff;
  border-left: 4px solid #409eff;
  padding: 16px;
  border-radius: 0 4px 4px 0;
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 14px;
}
.scrollable-text {
  max-height: 300px;
  overflow-y: auto;
  background: #f8f9fa;
  border: 1px solid #e4e7ed;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.6;
}
</style>
