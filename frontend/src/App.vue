<template>
  <RouterView v-slot="{ Component }">
    <keep-alive include="GeoView">
      <component :is="Component" />
    </keep-alive>
  </RouterView>
</template>
