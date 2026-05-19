<template>
  <div>
    <p class="text-muted">修改采集流水线的地域过滤规则。仅影响从「完整采集」页面触发的采集任务。</p>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never">
          <el-form label-position="top" @submit.prevent="handleSave">
            <h5 style="margin:0 0 16px">地域过滤</h5>

            <el-form-item label="包含省份">
              <el-input v-model="form.enabled_provinces" placeholder="例: 广东,上海,浙江" />
              <div class="form-tip">只采集这些省份的情报，多个用逗号分隔</div>
            </el-form-item>

            <el-form-item label="排除城市">
              <el-input v-model="form.excluded_cities" placeholder="例: 深圳,厦门" />
              <div class="form-tip">从包含省份中排除以下城市，多个用逗号分隔</div>
            </el-form-item>

            <el-form-item label="额外包含城市">
              <el-input v-model="form.extra_cities" placeholder="例: 北京,杭州" />
              <div class="form-tip">不限省份，以下城市的情报都采集（可选）</div>
            </el-form-item>

            <el-divider />

            <h5 style="margin:0 0 16px">DeepSeek 大模型配置</h5>
            <div class="form-tip" style="margin-bottom:12px">用于 AI 抽取和营销建议生成。</div>

            <el-form-item label="API Key">
              <el-input v-model="form.deepseek_api_key" type="password" placeholder="sk-..." show-password />
            </el-form-item>
            <el-form-item label="API 地址">
              <el-input v-model="form.deepseek_api_url" placeholder="https://api.deepseek.com" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="form.deepseek_model" placeholder="deepseek-chat" />
            </el-form-item>

            <el-divider />

            <h5 style="margin:0 0 16px">推送设置</h5>
            <el-form-item label="企业微信 Webhook 地址">
              <el-input v-model="form.wecom_webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
              <div class="form-tip">清空则使用 config.json 中的值</div>
            </el-form-item>

            <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
            <span v-if="saveMsg" :class="saveMsgType" style="margin-left:12px;font-size:13px">{{ saveMsg }}</span>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>当前规则预览</template>
          <div class="rule-preview">
            <div>包含省份：<strong>{{ ruleConfig.enabled_provinces?.join('、') }}</strong></div>
            <div>排除城市：<strong>{{ ruleConfig.excluded_cities?.join('、') }}</strong></div>
            <div v-if="ruleConfig.extra_cities?.length">额外城市：<strong>{{ ruleConfig.extra_cities?.join('、') }}</strong></div>
            <el-divider />
            <div class="text-muted">
              例：广州的企业 → <span class="text-success">通过</span><br>
              深圳的企业 → <span class="text-danger">过滤</span>
              <template v-if="ruleConfig.extra_cities?.length">
                <br>{{ ruleConfig.extra_cities[0] }}的企业 → <span class="text-success">通过</span>
              </template>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSettings, updateSettings } from '@/api'
import { ElMessage } from 'element-plus'

const form = reactive({
  enabled_provinces: '广东',
  excluded_cities: '深圳',
  extra_cities: '',
  deepseek_api_key: '',
  deepseek_api_url: 'https://api.deepseek.com',
  deepseek_model: 'deepseek-chat',
  wecom_webhook_url: '',
})

const ruleConfig = ref({})
const saving = ref(false)
const saveMsg = ref('')
const saveMsgType = ref('')

async function handleSave() {
  saving.value = true
  saveMsg.value = '保存中...'
  saveMsgType.value = 'text-muted'
  try {
    const data = { ...form }
    Object.keys(data).forEach(k => data[k] = data[k].trim())
    const res = await updateSettings(data)
    ruleConfig.value = res.filter_config
    saveMsg.value = '已保存'
    saveMsgType.value = 'text-success'
    setTimeout(() => { saveMsg.value = '' }, 3000)
  } catch (e) {
    saveMsg.value = '保存失败'
    saveMsgType.value = 'text-danger'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await getSettings()
    const s = data.settings || {}
    form.enabled_provinces = s.enabled_provinces || '广东'
    form.excluded_cities = s.excluded_cities || '深圳'
    form.extra_cities = s.extra_cities || ''
    form.deepseek_api_key = s.deepseek_api_key || ''
    form.deepseek_api_url = s.deepseek_api_url || 'https://api.deepseek.com'
    form.deepseek_model = s.deepseek_model || 'deepseek-chat'
    form.wecom_webhook_url = s.wecom_webhook_url || ''
    ruleConfig.value = data.filter_config || {}
  } catch {}
})
</script>

<style scoped>
.text-muted { color: #909399; font-size: 13px; }
.form-tip { font-size: 12px; color: #909399; margin-top: 4px; }
.rule-preview { font-size: 13px; line-height: 1.8; }
</style>
