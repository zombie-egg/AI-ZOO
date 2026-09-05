<script setup>
import { ref } from 'vue'

const grid = ref(null)

function revealGrid(event) {
  if (!grid.value) return
  const bounds = grid.value.getBoundingClientRect()
  grid.value.style.setProperty('--pointer-x', `${event.clientX - bounds.left}px`)
  grid.value.style.setProperty('--pointer-y', `${event.clientY - bounds.top}px`)
}
</script>

<template>
  <div ref="grid" class="infinite-grid" aria-hidden="true" @pointermove="revealGrid">
    <div class="grid-lines grid-lines-soft"></div>
    <div class="grid-lines grid-lines-focus"></div>
    <div class="grid-glow grid-glow-orange"></div>
    <div class="grid-glow grid-glow-cream"></div>
    <div class="grid-glow grid-glow-blue"></div>
  </div>
</template>
