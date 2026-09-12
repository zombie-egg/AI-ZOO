<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  muted: { type: Boolean, default: false },
});

// These are the curated, database-backed photos already committed to the kiosk.
// Repeating them keeps the morph composition rich without inventing any images.
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
const cards = Array.from({ length: 20 }, (_, index) => {
  const [src, label] = sourceImages[index % sourceImages.length];
  return { src, label, index };
});

const phase = ref("scatter");
const progress = ref(0);
const pointer = ref({ x: 0, y: 0 });
const viewport = ref({ width: window.innerWidth, height: window.innerHeight });
let phaseTimers = [];
let touchStartY = 0;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const lerp = (start, end, amount) => start * (1 - amount) + end * amount;

function updateViewport() {
  viewport.value = { width: window.innerWidth, height: window.innerHeight };
}

function updateProgress(delta) {
  progress.value = clamp(progress.value + delta, 0, 1);
}

function handleWheel(event) {
  // Do not cancel the page's native scrolling: this layer is decorative and
  // remains usable on kiosk browsers, trackpads and ordinary mouse wheels.
  updateProgress(event.deltaY / 1500);
}

function handleTouchStart(event) {
  touchStartY = event.touches[0]?.clientY || 0;
}

function handleTouchMove(event) {
  const nextY = event.touches[0]?.clientY || touchStartY;
  updateProgress((touchStartY - nextY) / 900);
  touchStartY = nextY;
}

function handlePointerMove(event) {
  pointer.value = {
    x: clamp((event.clientX / Math.max(viewport.value.width, 1)) * 2 - 1, -1, 1),
    y: clamp((event.clientY / Math.max(viewport.value.height, 1)) * 2 - 1, -1, 1),
  };
}

function seededScatter(index) {
  // Deterministic positions avoid cards jumping when Vue re-renders.
  const angle = index * 2.399963;
  const radius = 0.35 + ((index * 37) % 100) / 100;
  return {
    x: Math.cos(angle) * (viewport.value.width * radius * 0.72),
    y: Math.sin(angle) * (viewport.value.height * radius * 0.52),
    rotation: ((index * 47) % 120) - 60,
  };
}

const morphAmount = computed(() => progress.value);

function cardStyle(index) {
  const width = viewport.value.width;
  const height = viewport.value.height;
  const isMobile = width < 720;
  const scatter = seededScatter(index);
  const lineSpacing = Math.min(72, Math.max(44, width / 18));
  const line = {
    x: (index - (cards.length - 1) / 2) * lineSpacing,
    y: 0,
    rotation: 0,
  };
  const circleRadius = Math.min(Math.min(width, height) * 0.32, 320);
  const circleAngle = (index / cards.length) * Math.PI * 2;
  const circle = {
    x: Math.cos(circleAngle) * circleRadius,
    y: Math.sin(circleAngle) * circleRadius,
    rotation: (circleAngle * 180) / Math.PI + 90,
  };
  const stripGap = Math.min(82, Math.max(52, width / 13));
  const strip = {
    x: (index - (cards.length - 1) / 2) * stripGap,
    y: height * (isMobile ? 0.31 : 0.35),
    rotation: ((index - cards.length / 2) * (isMobile ? 4 : 3)),
  };

  let target;
  let opacity = 0.12;
  if (phase.value === "scatter") {
    target = scatter;
    opacity = 0;
  } else if (phase.value === "line") {
    target = line;
    opacity = 0.72;
  } else {
    const circleToStrip = morphAmount.value;
    target = {
      x: lerp(circle.x, strip.x, circleToStrip),
      y: lerp(circle.y, strip.y, circleToStrip),
      rotation: lerp(circle.rotation, strip.rotation, circleToStrip),
    };
    opacity = props.muted ? 0.25 : 0.78;
  }

  const parallaxX = pointer.value.x * (index % 3 === 0 ? 12 : 6);
  const parallaxY = pointer.value.y * (index % 2 === 0 ? 8 : 4);
  const scale = phase.value === "circle" ? 1.12 : phase.value === "line" ? 0.95 : 0.82;
  return {
    opacity,
    transform: `translate3d(calc(-50% + ${target.x + parallaxX}px), calc(-50% + ${target.y + parallaxY}px), 0) rotate(${target.rotation}deg) scale(${scale})`,
  };
}

onMounted(() => {
  phaseTimers = [
    window.setTimeout(() => (phase.value = "line"), 450),
    window.setTimeout(() => (phase.value = "circle"), 1900),
  ];
  window.addEventListener("resize", updateViewport, { passive: true });
  window.addEventListener("wheel", handleWheel, { passive: true });
  window.addEventListener("touchstart", handleTouchStart, { passive: true });
  window.addEventListener("touchmove", handleTouchMove, { passive: true });
  window.addEventListener("pointermove", handlePointerMove, { passive: true });
});

onBeforeUnmount(() => {
  phaseTimers.forEach((timer) => window.clearTimeout(timer));
  window.removeEventListener("resize", updateViewport);
  window.removeEventListener("wheel", handleWheel);
  window.removeEventListener("touchstart", handleTouchStart);
  window.removeEventListener("touchmove", handleTouchMove);
  window.removeEventListener("pointermove", handlePointerMove);
});
</script>

<template>
  <div class="scroll-morph-backdrop" :class="{ 'is-muted': muted }" aria-hidden="true">
    <div class="scroll-morph-wash"></div>
    <div class="scroll-morph-stage">
      <div
        v-for="card in cards"
        :key="`${card.src}-${card.index}`"
        class="scroll-morph-card"
        :style="cardStyle(card.index)"
      >
        <img :src="card.src" :alt="card.label" loading="eager" />
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
.scroll-morph-stage { position: absolute; inset: 0; perspective: 1200px; }
.scroll-morph-wash {
  position: absolute;
  z-index: 2;
  inset: 0;
  background:
    radial-gradient(circle at 50% 42%, rgba(255,255,255,.82), rgba(255,255,255,.34) 42%, rgba(255,255,255,.72) 100%),
    linear-gradient(115deg, rgba(229,240,255,.38), transparent 42%, rgba(255,226,204,.38));
}
.scroll-morph-card {
  position: absolute;
  z-index: 1;
  top: 50%;
  left: 50%;
  width: clamp(48px, 5vw, 74px);
  height: clamp(70px, 7vw, 104px);
  overflow: hidden;
  border: 1px solid rgba(12, 18, 16, .22);
  border-radius: 12px;
  background: #e8e9e5;
  box-shadow: 0 12px 30px rgba(12,18,16,.16);
  transform-origin: center;
  transition: transform 1.05s cubic-bezier(.16,1,.3,1), opacity .85s ease;
  will-change: transform, opacity;
}
.scroll-morph-card img { width: 100%; height: 100%; object-fit: cover; }
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
@media (prefers-reduced-motion: reduce) {
  .scroll-morph-card { transition-duration: .01ms; }
}
@media (max-width: 700px) {
  .scroll-morph-caption { right: 12px; bottom: 10px; font-size: 8px; }
}
</style>
