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
        <RouterLink class="nav-settings-link" to="/settings" aria-label="设置">
          <svg viewBox="0 0 24 24" fill="none" role="img">
            <path
              d="M12 3.5h0.7l0.6 2.2a7.5 7.5 0 0 1 2.1 1.1l2-1.1 1 1.8-1.8 1.3c.2.7.3 1.4.3 2.1s-.1 1.4-.3 2.1l1.8 1.3-1 1.8-2-1.1a7.5 7.5 0 0 1-2.1 1.1l-.6 2.2H12l-.7-2.2a7.5 7.5 0 0 1-2.1-1.1l-2 1.1-1-1.8 1.8-1.3a7.5 7.5 0 0 1 0-4.2l-1.8-1.3 1-1.8 2 1.1a7.5 7.5 0 0 1 2.1-1.1L12 3.5Z"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linejoin="round"
            />
            <circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.6" />
          </svg>
        </RouterLink>
      </section>
    </main>
  </div>
</template>
