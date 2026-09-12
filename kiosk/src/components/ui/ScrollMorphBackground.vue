<script setup>
import { computed } from "vue";

defineProps({
  muted: { type: Boolean, default: false },
});

// Existing, curated database outputs only. Each track is duplicated in the
// template so the vertical waterfall can loop without a visible seam.
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

const leftTrack = computed(() => [...sourceImages, ...sourceImages]);
const rightTrack = computed(() => {
  const reversed = [...sourceImages].reverse();
  return [...reversed, ...reversed];
});
const ringCards = computed(() =>
  Array.from({ length: 16 }, (_, index) => {
    const photo = sourceImages[index % sourceImages.length];
    return { ...photo, angle: `${(index / 16) * 360}deg` };
  }),
);
</script>

<template>
  <div class="scroll-morph-backdrop" :class="{ 'is-muted': muted }" aria-hidden="true">
    <div class="scroll-morph-gallery">
      <div class="scroll-morph-column scroll-morph-column-left">
        <div class="scroll-morph-track">
          <figure v-for="(photo, index) in leftTrack" :key="`left-${index}`" class="scroll-morph-photo">
            <img :src="photo[0]" :alt="photo[1]" loading="eager" />
          </figure>
        </div>
      </div>
      <div class="scroll-morph-column scroll-morph-column-right">
        <div class="scroll-morph-track">
          <figure v-for="(photo, index) in rightTrack" :key="`right-${index}`" class="scroll-morph-photo">
            <img :src="photo[0]" :alt="photo[1]" loading="eager" />
          </figure>
        </div>
      </div>
    </div>
    <div class="scroll-morph-ring">
      <figure
        v-for="(photo, index) in ringCards"
        :key="`ring-${index}`"
        class="scroll-morph-ring-photo"
        :style="{ '--ring-angle': photo.angle }"
      >
        <img :src="photo[0]" :alt="photo[1]" loading="eager" />
      </figure>
    </div>
    <div class="scroll-morph-center-wash"></div>
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
.scroll-morph-gallery {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: minmax(108px, 19vw) minmax(108px, 19vw);
  justify-content: space-between;
  gap: clamp(18px, 5vw, 76px);
  padding: 0 clamp(18px, 4vw, 76px);
}
.scroll-morph-column {
  position: relative;
  height: 100%;
  overflow: hidden;
}
.scroll-morph-column-right { padding-top: clamp(56px, 12vh, 150px); }
.scroll-morph-track {
  display: grid;
  gap: clamp(12px, 1.5vw, 24px);
  padding: clamp(18px, 3vh, 42px) 0;
  animation: waterfall-up 46s linear infinite;
  will-change: transform;
}
.scroll-morph-column-right .scroll-morph-track {
  animation-name: waterfall-down;
  animation-duration: 53s;
  animation-delay: -17s;
}
.scroll-morph-ring {
  position: absolute;
  z-index: 1;
  top: 39%;
  left: 50%;
  width: min(47vw, 590px);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  animation: ring-orbit 58s linear infinite;
  will-change: transform;
}
.scroll-morph-ring-photo {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(48px, 5vw, 76px);
  height: clamp(70px, 7.5vw, 108px);
  margin: 0;
  overflow: hidden;
  border: 1px solid rgba(12,18,16,.2);
  border-radius: 12px;
  background: #e8e9e5;
  box-shadow: 0 10px 24px rgba(12,18,16,.14);
  opacity: .8;
  transform: rotate(var(--ring-angle)) translateY(calc(min(23.5vw, 295px) * -1));
}
.scroll-morph-ring-photo img { width: 100%; height: 100%; object-fit: cover; }
.scroll-morph-photo {
  width: 100%;
  height: clamp(156px, 22vh, 290px);
  margin: 0;
  overflow: hidden;
  border: 1px solid rgba(12,18,16,.2);
  border-radius: clamp(14px, 1.5vw, 24px);
  background: #e8e9e5;
  box-shadow: 0 14px 34px rgba(12,18,16,.14);
}
.scroll-morph-photo img { width: 100%; height: 100%; object-fit: cover; }
.scroll-morph-backdrop.is-muted .scroll-morph-photo { opacity: .84; }
.scroll-morph-center-wash {
  position: absolute;
  z-index: 2;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255,255,255,.05) 0%, rgba(255,255,255,.62) 18%, rgba(255,255,255,.9) 34%, rgba(255,255,255,.94) 50%, rgba(255,255,255,.9) 66%, rgba(255,255,255,.62) 82%, rgba(255,255,255,.05) 100%),
    linear-gradient(180deg, rgba(255,255,255,.22), transparent 24%, transparent 76%, rgba(255,255,255,.28));
}
@keyframes waterfall-up {
  from { transform: translateY(0); }
  to { transform: translateY(-50%); }
}
@keyframes waterfall-down {
  from { transform: translateY(-50%); }
  to { transform: translateY(0); }
}
@keyframes ring-orbit {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .scroll-morph-track { animation-duration: 120s; }
  .scroll-morph-ring { animation-duration: 150s; }
}
@media (max-width: 700px) {
  .scroll-morph-gallery {
    grid-template-columns: minmax(76px, 25vw) minmax(76px, 25vw);
    gap: 8px;
    padding: 0 8px;
  }
  .scroll-morph-photo {
    height: clamp(112px, 17vh, 190px);
    border-radius: 12px;
  }
  .scroll-morph-column-right { padding-top: 9vh; }
  .scroll-morph-track { gap: 8px; padding: 10px 0; }
  .scroll-morph-ring {
    top: 37%;
    width: 58vw;
  }
  .scroll-morph-ring-photo {
    width: 42px;
    height: 62px;
    transform: rotate(var(--ring-angle)) translateY(-29vw);
  }
  .scroll-morph-center-wash {
    background: linear-gradient(90deg, rgba(255,255,255,.05), rgba(255,255,255,.82) 24%, rgba(255,255,255,.92) 50%, rgba(255,255,255,.82) 76%, rgba(255,255,255,.05));
  }
}
</style>
