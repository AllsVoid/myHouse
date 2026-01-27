<template>
  <div class="nav-page">
    <main class="nav-container">
      <header class="nav-header">
        <h1>项目功能导航</h1>
        <p>请选择要进入的功能模块。</p>
      </header>
      <section class="nav-grid">
        <RouterLink class="nav-card" to="/geo">
          <h2>GeoJSON 预览器</h2>
          <p>加载、编辑与保存面/点数据。</p>
        </RouterLink>
        <RouterLink class="nav-card" to="/houses">
          <h2>房屋管理</h2>
          <p>登记房屋信息，支持本地管理与筛选。</p>
        </RouterLink>
      </section>
    </main>
  </div>
</template>
