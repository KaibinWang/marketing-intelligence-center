<template>
  <div v-loading="loading">
    <!-- 统计卡片 -->
    <el-row :gutter="16">
      <el-col :span="6">
        <div class="stat-card bg-primary">
          <div class="stat-value">{{ data.today_count }}</div>
          <div class="stat-label">今日新增</div>
          <el-icon class="stat-icon"><Calendar /></el-icon>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card bg-info">
          <div class="stat-value">{{ data.stats.total }}</div>
          <div class="stat-label">情报总数</div>
          <el-icon class="stat-icon"><DataBase /></el-icon>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card bg-success">
          <div class="stat-value">{{ data.stats.pushed }}</div>
          <div class="stat-label">已推送</div>
          <el-icon class="stat-icon"><Promotion /></el-icon>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card bg-warning">
          <div class="stat-value">{{ data.stats.rate }}%</div>
          <div class="stat-label">推送率</div>
          <el-icon class="stat-icon"><Percent /></el-icon>
        </div>
      </el-col>
    </el-row>

    <!-- 第一行：类型分布 + 来源分布 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>按事件类型分布</template>
          <div v-for="item in data.type_dist" :key="item.event_type" class="bar-row">
            <span class="bar-label">{{ item.event_type }}</span>
            <el-progress :percentage="calcPct(item.count, data.stats.total)" :stroke-width="20" :show-text="false" />
            <span class="bar-count">{{ item.count }}</span>
          </div>
          <el-empty v-if="!data.type_dist.length" description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>按数据来源分布</template>
          <div v-for="item in data.source_dist" :key="item.source" class="bar-row">
            <span class="bar-label">{{ item.source }}</span>
            <el-progress :percentage="calcPct(item.count, data.stats.total)" :stroke-width="20" color="#67c23a" :show-text="false" />
            <span class="bar-count">{{ item.count }}</span>
          </div>
          <el-empty v-if="!data.source_dist.length" description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 第二行：金额分布 + 状态分布 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>按金额分布</template>
          <div v-for="item in data.amount_dist" :key="item.label" class="bar-row">
            <span class="bar-label">{{ item.label }}</span>
            <el-progress :percentage="calcPct(item.count, data.stats.total)" :stroke-width="20" color="#e6a23c" :show-text="false" />
            <span class="bar-count">{{ item.count }}</span>
          </div>
          <el-empty v-if="!data.amount_dist.length" description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>按处理状态分布</template>
          <div v-for="item in data.status_dist" :key="item.status" class="bar-row">
            <span class="bar-label">{{ statusLabel(item.status) }}</span>
            <el-progress
              :percentage="calcPct(item.count, data.stats.total)"
              :stroke-width="20"
              :color="statusColor(item.status)"
              :show-text="false"
            />
            <span class="bar-count">{{ item.count }}</span>
          </div>
          <el-empty v-if="!data.status_dist.length" description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 第三行：企业排行 + 7日趋势 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>企业排行 TOP 10</template>
          <el-table :data="data.top_companies" stripe size="small" v-if="data.top_companies.length">
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="company_name" label="企业名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="count" label="出现次数" width="100" />
          </el-table>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>近 7 天新增趋势</template>
          <el-table :data="trendData" stripe size="small" v-if="trendData.length">
            <el-table-column prop="day" label="日期" />
            <el-table-column prop="count" label="新增数量" />
          </el-table>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStats } from '@/api'

const data = ref({ stats: {}, type_dist: [], source_dist: [], daily_trend: [], amount_dist: [], top_companies: [], status_dist: [] })
const loading = ref(true)

const trendData = computed(() =>
  [...(data.value.daily_trend || [])].slice(-7).reverse()
)

function calcPct(count, total) {
  return Math.round((count || 0) / (total || 1) * 100)
}

function statusLabel(s) {
  const map = { new: '未推送', sent: '已推送', filtered: '已过滤' }
  return map[s] || s
}

function statusColor(s) {
  const map = { new: '#e6a23c', sent: '#67c23a', filtered: '#909399' }
  return map[s] || '#409eff'
}

async function loadData() {
  try {
    data.value = await getStats()
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.stat-card {
  position: relative;
  border-radius: 8px;
  padding: 24px;
  color: #fff;
  overflow: hidden;
}
.stat-value { font-size: 32px; font-weight: 700; }
.stat-label { font-size: 14px; opacity: 0.9; margin-top: 4px; }
.stat-icon {
  position: absolute;
  right: 20px;
  bottom: 16px;
  font-size: 56px;
  opacity: 0.2;
}
.bg-primary { background: linear-gradient(135deg, #409eff, #337ecc); }
.bg-info { background: linear-gradient(135deg, #909399, #606266); }
.bg-success { background: linear-gradient(135deg, #67c23a, #529b2e); }
.bg-warning { background: linear-gradient(135deg, #e6a23c, #b88230); }
.bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.bar-label { min-width: 100px; font-size: 13px; white-space: nowrap; }
.bar-row .el-progress { flex: 1; }
.bar-count { min-width: 36px; text-align: right; font-size: 13px; color: #909399; }
</style>
