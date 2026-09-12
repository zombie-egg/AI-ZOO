<script setup>
import { computed } from "vue";

defineProps({
  muted: { type: Boolean, default: false },
});

// Only use finished photos already stored in the project database. Repetition
// is intentional so the ring remains continuous on wide kiosk screens.
const sourceImages = [
  ["/kiosk/card-gallery/panda.jpg", "熊猫"],
  ["/kiosk/card-gallery/red-panda.jpg", "小熊猫"],
  ["/kiosk/card-gallery/elephant.jpg", "大象"],
  ["/kiosk/card-gallery/giraffe.jpg", "长颈鹿"],
  ["/kiosk/card-gallery/flamingo.jpg", "火烈鸟"],
  ["/kiosk/card-gallery/dolphin.jpg", "海豚"],
  ["/kiosk/card-gallery/lemur.jpg", "狐猴"],
  ["/kiosk/card-gallery/white-tiger.jpg", "白虎"],
  ["/kiosk/card-gallery/capybara.jpg", "水豚"],
];

const cards = computed(() =>
  Array.from({ length: 20 }, (_, index) => {
    const [src, label] = sourceImages[index % sourceImages.length];
    return {
      src,
      label,
      angle: `${(index / 20) * 360}deg`,
    };
  }),
);
</script>

<template>
  <div class="scroll-morph-backdrop" :class="{ 'is-muted': muted }" aria-hidden="true">
    <div class="scroll-morph-wash"></div>
    <div class="scroll-morph-stage">
      <div class="scroll-morph-ring">
        <div
          v-for="card in cards"
          :key="`${card.src}-${card.angle}`"
          class="scroll-morph-card"
          :style="{ '--card-angle': card.angle }"
        >
          <img :src="card.src" :alt="card.label" loading="eager" />
        </div>
      </div>
    </div>
    <div class="scroll-morph-caption">AI ZOO · 已完成成品影像</div>
  </div>
</template>

<style>
.scroll-morph-backdrop {
  --morph-paper: #f7f7f4;
  position: fixed;
  z-index: 0;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  background: var(--morph-paper);
}
.scroll-morph-backdrop.is-muted { --morph-paper: #f3f3ef; }
.scroll-morph-stage {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  perspective: 1200px;
}
.scroll-morph-ring {
  position: relative;
  width: min(76vw, 900px);
  height: min(76vw, 900px);
  transform: translateZ(0);
  animation: ring-spin 34s linear infinite;
  will-change: transform;
}
.scroll-morph-wash {
  position: absolute;
  z-index: 2;
  inset: 0;
  background:
    radial-gradient(circle at 50% 50%, rgba(255,255,255,.54), rgba(255,255,255,.14) 46%, rgba(255,255,255,.5) 100%),
    linear-gradient(115deg, rgba(229,240,255,.2), transparent 42%, rgba(255,226,204,.2));
}
.scroll-morph-card {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(64px, 7vw, 102px);
  height: clamp(92px, 10vw, 142px);
  overflow: hidden;
  border: 1px solid rgba(12, 18, 16, .28);
  border-radius: 14px;
  background: #e8e9e5;
  box-shadow: 0 14px 34px rgba(12,18,16,.2);
  transform: rotate(var(--card-angle)) translateY(calc(min(38vw, 450px) * -1));
  transform-origin: center center;
}
.scroll-morph-card img { width: 100%; height: 100%; object-fit: cover; }
.scroll-morph-backdrop.is-muted .scroll-morph-card { opacity: .86; }
.scroll-morph-caption {
  position: absolute;
  z-index: 3;
  right: 20px;
  bottom: 16px;
  color: rgba(17,17,17,.42);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .16em;
  text-transform: uppercase;
}
@keyframes ring-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .scroll-morph-ring { animation-duration: 90s; }
}
@media (max-width: 700px) {
  .scroll-morph-ring { width: 94vw; height: 94vw; }
  .scroll-morph-card { transform: rotate(var(--card-angle)) translateY(-44vw); }
  .scroll-morph-caption { right: 12px; bottom: 10px; font-size: 8px; }
}
</style>
