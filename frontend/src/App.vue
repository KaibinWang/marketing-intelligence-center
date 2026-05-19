<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-left">
        <span class="brand">营销情报中心</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        router
        class="header-menu"
      >
        <el-menu-item index="/">
          <el-icon><List /></el-icon>情报列表
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataAnalysis /></el-icon>统计看板
        </el-menu-item>
        <el-menu-item index="/sources">
          <el-icon><Connection /></el-icon>数据源管理
        </el-menu-item>
        <el-menu-item index="/pipeline">
          <el-icon><VideoPlay /></el-icon>完整采集
        </el-menu-item>
        <el-menu-item index="/push-logs">
          <el-icon><Promotion /></el-icon>推送记录
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>过滤设置
        </el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/event/')) return '/'
  return path
})
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
.app-container {
  min-height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.header-left {
  margin-right: 32px;
}
.brand {
  font-size: 18px;
  font-weight: 700;
  color: #409eff;
  white-space: nowrap;
}
.header-menu {
  flex: 1;
  border-bottom: none !important;
}
.app-main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
</style>
