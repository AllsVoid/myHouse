import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import GeoView from '../views/GeoView.vue'
import HousesView from '../views/HousesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/geo', name: 'geo', component: GeoView },
    { path: '/houses', name: 'houses', component: HousesView }
  ]
})

export default router
