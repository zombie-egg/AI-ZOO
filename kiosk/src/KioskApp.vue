<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import QRCode from "qrcode";
import { ArrowRight } from "lucide-vue-next";
import InfiniteGrid from "./components/ui/InfiniteGrid.vue";
import { kioskConfig } from "./config";
import { kioskApi } from "./services/api";
import {
  captureBestJpeg,
  openPreferredCamera,
  stopCamera,
} from "./services/camera";
import {
  closePrintAgent,
  connectPrintAgent,
  printPhoto,
} from "./services/printAgent";

const stages = [
  "idle",
  "people",
  "scan",
  "consent",
  "scene",
  "pose",
  "capture",
  "capture_review",
  "group_review",
  "pay",
  "generating",
  "quality_review",
  "printing",
  "result",
  "error",
];
const screen = ref("idle");
const busy = ref(false);
const paymentBusy = ref(false);
const message = ref("");
const countdown = ref(0);
const progress = ref(0);
const secondsLeft = ref(0);
const order = ref(null);
const scenes = ref([]);
const poses = ref([]);
const selectedScene = ref(null);
const selectedPose = ref(null);
const participantCount = ref(1);
const currentParticipantIndex = ref(0);
const participantShots = ref([[]]);
const groupRetakeMode = ref(false);
const finalUrl = ref("");
const printPayloadUrl = ref("");
const qr = ref("");
const downloadQr = ref("");
const paymentMode = ref("");
const paymentAmount = ref(kioskConfig.price);
const consent = ref(false);
const minor = ref(false);
const guardianConfirmed = ref(false);
const errorInfo = ref({
  title: "",
  detail: "",
  recoverable: true,
  returnScreen: "scene",
});
const videoEl = ref(null);
const cameraStream = ref(null);
const printerOnline = ref(false);
const deliveryPrinted = ref(false);
const heroTitle = "AI ZOO".split("");
let inactivityTimer;
let flowTimer;

const shotGuides = [
  {
    type: "body_anchor",
    title: "半身正面自然照",
    hint: "正对镜头，拍清发型、穿搭和体型",
    icon: "①",
  },
  {
    type: "front_smile",
    title: "正面轻微微笑",
    hint: "看镜头，轻轻微笑，不要夸张表情",
    icon: "②",
  },
  {
    type: "left_three_quarter",
    title: "左转 30°",
    hint: "身体不动，脸向左轻转一点",
    icon: "③",
  },
  {
    type: "right_three_quarter",
    title: "右转 30°",
    hint: "身体不动，脸向右轻转一点",
    icon: "④",
  },
];
const shots = ref([]);
const currentShot = computed(() => shotGuides[shots.value.length]);
const currentParticipantNo = computed(() => currentParticipantIndex.value + 1);
const canConsent = computed(
  () => consent.value && (!minor.value || guardianConfirmed.value),
);
const statusText = computed(() =>
  screen.value === "idle"
    ? printerOnline.value
      ? "相机与打印已就绪"
      : "相机就绪 · 电子版可用"
    : `流程 ${Math.max(1, stages.indexOf(screen.value))}/${stages.length - 2}`,
);

function animalEmoji(sceneId = "") {
  if (sceneId.includes("PANDA") && !sceneId.includes("RED")) return "🐼";
  if (sceneId.includes("RED_PANDA")) return "🦊";
  if (sceneId.includes("ELEPHANT")) return "🐘";
  if (sceneId.includes("GIRAFFE")) return "🦒";
  if (sceneId.includes("FLAMINGO")) return "🦩";
  if (sceneId.includes("DOLPHIN")) return "🐬";
  if (sceneId.includes("LEMUR")) return "🐒";
  if (sceneId.includes("TIGER")) return "🐯";
  if (sceneId.includes("CAPYBARA")) return "🦫";
  return "🐾";
}

function clearFlowTimer() {
  if (flowTimer) window.clearInterval(flowTimer);
  flowTimer = null;
}

function resetInactivity() {
  window.clearTimeout(inactivityTimer);
  if (screen.value !== "idle")
    inactivityTimer = window.setTimeout(resetAll, kioskConfig.inactivityMs);
}

function go(next) {
  clearFlowTimer();
  screen.value = next;
  message.value = "";
  paymentBusy.value = false;
  progress.value = 0;
  resetInactivity();
}

function releaseShotUrls() {
  for (const group of participantShots.value) {
    for (const shot of group)
      if (shot.localUrl) URL.revokeObjectURL(shot.localUrl);
  }
}

function resetAll() {
  clearFlowTimer();
  stopCamera(cameraStream.value);
  cameraStream.value = null;
  releaseShotUrls();
  screen.value = "idle";
  order.value = null;
  selectedScene.value = null;
  selectedPose.value = null;
  participantCount.value = 1;
  currentParticipantIndex.value = 0;
  participantShots.value = [[]];
  groupRetakeMode.value = false;
  finalUrl.value = "";
  printPayloadUrl.value = "";
  qr.value = "";
  downloadQr.value = "";
  paymentMode.value = "";
  paymentAmount.value = kioskConfig.price;
  consent.value = false;
  minor.value = false;
  guardianConfirmed.value = false;
  shots.value = [];
  message.value = "";
  deliveryPrinted.value = false;
  Object.assign(errorInfo.value, {
    title: "",
    detail: "",
    recoverable: true,
    returnScreen: "scene",
  });
  window.clearTimeout(inactivityTimer);
}

async function loadScenes() {
  if (scenes.value.length && poses.value.length) return;
  const result = await kioskApi.getScenes();
  scenes.value = result.scenes || [];
  poses.value = result.poses || [];
  if (!scenes.value.length) throw new Error("没有已启用的文字场景");
  if (!poses.value.length) throw new Error("没有已启用的人物姿势");
}

async function startScan() {
  try {
    await loadScenes();
    go("people");
  } catch (error) {
    fail("场景服务暂时不可用", error.message, true, "idle");
  }
}

async function chooseParticipantCount(count) {
  participantCount.value = count;
  participantShots.value = Array.from({ length: count }, () => []);
  currentParticipantIndex.value = 0;
  try {
    go("scan");
    const value = `${location.origin}/mobile/pages/kiosk/start`;
    qr.value = await QRCode.toDataURL(value, {
      width: 320,
      margin: 1,
      color: { dark: "#143128", light: "#ffffff" },
    });
  } catch (error) {
    fail("场景服务暂时不可用", error.message, true, "idle");
  }
}

async function finishScan() {
  try {
    order.value = await kioskApi.createOrder({
      source: "kiosk",
      consent_given: false,
      participant_count: participantCount.value,
    });
    currentParticipantIndex.value = 0;
    go("consent");
  } catch (error) {
    fail("订单创建失败", error.message, true, "scan");
  }
}

async function acceptConsent() {
  if (!canConsent.value) return;
  try {
    await kioskApi.recordConsent(order.value.id, {
      participant_no: currentParticipantNo.value,
      consent_given: true,
      minor_involved: minor.value,
      guardian_confirmed: guardianConfirmed.value,
    });
    if (currentParticipantNo.value < participantCount.value) {
      currentParticipantIndex.value += 1;
      consent.value = false;
      minor.value = false;
      guardianConfirmed.value = false;
      message.value = `第 ${currentParticipantNo.value - 1} 位已完成授权，请第 ${currentParticipantNo.value} 位确认`;
    } else {
      currentParticipantIndex.value = 0;
      go("scene");
    }
  } catch (error) {
    fail("授权记录失败", error.message, true, "consent");
  }
}

async function chooseScene(scene) {
  if (busy.value) return;
  busy.value = true;
  try {
    await kioskApi.selectScene(order.value.id, scene.scene_id);
    selectedScene.value = scene;
    selectedPose.value = null;
    go("pose");
  } catch (error) {
    fail("场景暂时不可用", error.message, true, "scene");
  } finally {
    busy.value = false;
  }
}

async function choosePose(pose) {
  if (busy.value) return;
  busy.value = true;
  try {
    await kioskApi.selectPose(order.value.id, pose.pose_id);
    selectedPose.value = pose;
    currentParticipantIndex.value = 0;
    shots.value = participantShots.value[0];
    go("capture");
    await nextTick();
    cameraStream.value = await openPreferredCamera(
      videoEl.value,
      kioskConfig.cameraLabel,
    );
    message.value = `已连接：${cameraStream.value.kioskDeviceLabel} · ${cameraStream.value.kioskResolution}`;
  } catch (error) {
    stopCamera(cameraStream.value);
    cameraStream.value = null;
    fail(
      "相机或姿势暂时不可用",
      `${error.message}。请检查 USB 连接与浏览器相机权限。`,
      true,
      "pose",
    );
  } finally {
    busy.value = false;
  }
}

async function takeShot() {
  if (!currentShot.value || busy.value || !cameraStream.value) return;
  busy.value = true;
  message.value = "";
  for (let number = 3; number >= 1; number -= 1) {
    countdown.value = number;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  countdown.value = 0;
  try {
    message.value = "正在连拍 3 帧并选择最清晰的一张…";
    const blob = await captureBestJpeg(videoEl.value, cameraStream.value, 3);
    const uploaded = await kioskApi.uploadPhoto(
      order.value.id,
      blob,
      currentShot.value.type,
      currentParticipantNo.value,
    );
    if (!uploaded.quality?.passed) {
      message.value = `这张需要重拍：${uploaded.quality?.reason || "请看清镜头并保持光线充足"}`;
      return;
    }
    shots.value.push({
      ...currentShot.value,
      ...uploaded.quality,
      localUrl: URL.createObjectURL(blob),
    });
    participantShots.value[currentParticipantIndex.value] = shots.value;
    message.value = `✓ ${uploaded.quality.reason}`;
    if (shots.value.length === shotGuides.length) {
      stopCamera(cameraStream.value);
      cameraStream.value = null;
      setTimeout(() => go("capture_review"), 350);
    }
  } catch (error) {
    message.value = `拍摄上传失败：${error.message}`;
  } finally {
    busy.value = false;
  }
}

async function redoShot(
  index,
  participantIndex = currentParticipantIndex.value,
) {
  const returnToGroupReview = screen.value === "group_review";
  groupRetakeMode.value = returnToGroupReview;
  currentParticipantIndex.value = participantIndex;
  shots.value = participantShots.value[participantIndex];
  for (const removed of shots.value.splice(index)) {
    if (removed.localUrl) URL.revokeObjectURL(removed.localUrl);
  }
  go("capture");
  await nextTick();
  try {
    cameraStream.value = await openPreferredCamera(
      videoEl.value,
      kioskConfig.cameraLabel,
    );
    message.value = `请从第 ${index + 1} 张开始重拍`;
  } catch (error) {
    fail(
      "相机暂时不可用",
      error.message,
      true,
      returnToGroupReview ? "group_review" : "capture_review",
    );
  }
}

async function confirmParticipantPhotos() {
  participantShots.value[currentParticipantIndex.value] = shots.value;
  if (groupRetakeMode.value) {
    groupRetakeMode.value = false;
    go("group_review");
    return;
  }
  if (currentParticipantNo.value >= participantCount.value) {
    go("group_review");
    return;
  }
  currentParticipantIndex.value += 1;
  shots.value = participantShots.value[currentParticipantIndex.value];
  go("capture");
  await nextTick();
  try {
    cameraStream.value = await openPreferredCamera(
      videoEl.value,
      kioskConfig.cameraLabel,
    );
    message.value = `请第 ${currentParticipantNo.value} 位参与者进入拍摄区`;
  } catch (error) {
    fail("相机暂时不可用", error.message, true, "capture_review");
  }
}

async function proceedToPayment() {
  go("pay");
  try {
    const payment = await kioskApi.createPayment(order.value.id);
    paymentMode.value = payment.payment_mode || "wechat_native";
    paymentAmount.value = Number(payment.amount ?? kioskConfig.price);
    if (payment.paid) {
      await beginGeneration(false);
      return;
    }
    qr.value = await QRCode.toDataURL(payment.code_url, {
      width: 330,
      margin: 1,
    });
    pollPayment();
  } catch (error) {
    fail("支付二维码生成失败", error.message, true, "group_review");
  }
}

async function simulateWechatPayment() {
  if (paymentBusy.value || paymentMode.value !== "mock") return;
  paymentBusy.value = true;
  message.value = "正在模拟接收微信支付成功通知…";
  try {
    await kioskApi.simulatePayment(order.value.id);
    message.value = "已收到模拟支付成功通知，正在确认订单状态…";
  } catch (error) {
    message.value = `模拟支付失败：${error.message}`;
  } finally {
    paymentBusy.value = false;
  }
}

function pollPayment() {
  flowTimer = window.setInterval(async () => {
    try {
      const state = await kioskApi.getStatus(order.value.id);
      if (state.unlock_status === "paid") {
        clearFlowTimer();
        await beginGeneration(false);
      }
    } catch (error) {
      message.value = `支付状态重连中：${error.message}`;
    }
  }, 2000);
}

async function beginGeneration(operatorTest = false) {
  if (busy.value) return;
  busy.value = true;
  try {
    await kioskApi.startGeneration(order.value.id, operatorTest);
    go("generating");
    secondsLeft.value = 90;
    pollGeneration();
  } catch (error) {
    fail("GPT-image-2 任务创建失败", error.message, true, "pay");
  } finally {
    busy.value = false;
  }
}

function pollGeneration() {
  const started = Date.now();
  flowTimer = window.setInterval(async () => {
    const elapsed = Math.floor((Date.now() - started) / 1000);
    progress.value = Math.max(
      progress.value,
      Math.min(94, Math.round((elapsed / 90) * 86)),
    );
    secondsLeft.value = Math.max(1, 90 - elapsed);
    try {
      const state = await kioskApi.getGenerationStatus(order.value.id);
      progress.value = state.progress ?? progress.value;
      secondsLeft.value = state.eta_seconds ?? secondsLeft.value;
      if (state.status === "review_required") {
        clearFlowTimer();
        finalUrl.value = state.final_url;
        go("quality_review");
      } else if (state.status === "failed") {
        fail(
          "本次真实生成失败",
          state.error_msg || "没有生成可交付成品，请联系工作人员重试或退款。",
          false,
          "group_review",
        );
      }
    } catch (error) {
      message.value = `生成状态重连中：${error.message}`;
    }
  }, 3000);
}

async function approveAndDeliver() {
  if (busy.value) return;
  busy.value = true;
  try {
    const approved = await kioskApi.approveResult(order.value.id);
    printPayloadUrl.value = approved.print_payload || "";
    await beginPrinting();
  } catch (error) {
    fail("成品确认失败", error.message, true, "quality_review");
  } finally {
    busy.value = false;
  }
}

async function rejectResult() {
  fail(
    "成品未通过人工确认",
    "本单不会自动打印。请由工作人员查看原图和生成记录，再决定重新生成或退款。",
    false,
    "quality_review",
  );
}

async function beginPrinting() {
  if (!printerOnline.value || !printPayloadUrl.value) {
    deliveryPrinted.value = false;
    message.value = "打印机未连接，已保留高清电子版。";
    await finishResult();
    return;
  }
  go("printing");
  secondsLeft.value = 90;
  try {
    await kioskApi.reportPrintStatus(order.value.id, "printing");
    flowTimer = window.setInterval(() => {
      progress.value = Math.min(92, progress.value + 2);
      secondsLeft.value = Math.max(1, secondsLeft.value - 1);
    }, 1000);
    const html = await fetch(printPayloadUrl.value, {
      credentials: "include",
    }).then((response) => {
      if (!response.ok) throw new Error("打印排版下载失败");
      return response.text();
    });
    await printPhoto({ html, orderNo: order.value.order_no, copies: 1 });
    clearFlowTimer();
    progress.value = 100;
    deliveryPrinted.value = true;
    await kioskApi.reportPrintStatus(order.value.id, "done");
    await finishResult();
  } catch (error) {
    clearFlowTimer();
    try {
      await kioskApi.reportPrintStatus(order.value.id, "failed", error.message);
    } catch {}
    fail(
      "照片未能正常打印",
      `${error.message}。高清电子版仍然可用，可由工作人员补打。`,
      false,
      "quality_review",
    );
  }
}

async function finishResult() {
  downloadQr.value = await QRCode.toDataURL(finalUrl.value, {
    width: 280,
    margin: 1,
  });
  go("result");
}

function fail(title, detail, recoverable = true, returnScreen = "scene") {
  clearFlowTimer();
  errorInfo.value = { title, detail, recoverable, returnScreen };
  screen.value = "error";
}

function recover() {
  go(errorInfo.value.returnScreen || "scene");
}

watch(screen, (value) => {
  document.title = `AI 动物合照机 · ${value}`;
});

onMounted(async () => {
  connectPrintAgent((state) => {
    printerOnline.value = Boolean(state.online);
  });
  try {
    await loadScenes();
  } catch (error) {
    message.value = error.message;
  }
  for (const event of ["pointerdown", "keydown", "touchstart"]) {
    window.addEventListener(event, resetInactivity, { passive: true });
  }
  window.addEventListener("contextmenu", (event) => event.preventDefault());
  window.addEventListener("dragstart", (event) => event.preventDefault());
});

onBeforeUnmount(() => {
  clearFlowTimer();
  window.clearTimeout(inactivityTimer);
  stopCamera(cameraStream.value);
  releaseShotUrls();
  closePrintAgent();
});
</script>

<template>
  <main class="kiosk-shell" :data-screen="screen">
    <InfiniteGrid v-if="screen !== 'idle'" />
    <header v-if="screen !== 'idle'" class="topbar">
      <div class="brand-mark">AI</div>
      <div>
        <p class="eyebrow">ANIMAL PHOTO MOMENT</p>
        <h1>AI 动物合照机</h1>
      </div>
      <div class="service-pill"><span></span>{{ statusText }}</div>
    </header>

    <section v-if="screen === 'idle'" class="prisma-hero">
      <video
        class="prisma-video"
        autoplay
        loop
        muted
        playsinline
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_170732_8a9ccda6-5cff-4628-b164-059c500a2b41.mp4"
      ></video>
      <div class="prisma-noise"></div>
      <div class="prisma-video-shade"></div>
      <nav class="prisma-nav">
        <span>真实四连拍</span><span>场景与姿势</span><span>智能美颜</span
        ><span>成品确认</span><span>现场打印</span
        ><span class="prisma-nav-status"
          ><i></i>{{ printerOnline ? "相机与打印已就绪" : "相机就绪" }}</span
        >
      </nav>
      <div class="prisma-content">
        <h2 class="prisma-title">
          <span
            v-for="(char, index) in heroTitle"
            :key="index"
            :style="{ '--char-index': index }"
            >{{ char === " " ? "\u00a0" : char }}</span
          ><sup>*</sup>
        </h2>
        <div class="prisma-side">
          <p>
            支持 1–4 人动物合照。每个人分别完成四连拍，AI
            严格区分身份与穿搭，再合成一张姿势协调的自然合照，并逐人完成瘦脸、美白与磨皮；确认后才会打印。
          </p>
          <button class="prisma-start" @click="startScan">
            开始拍摄<b><ArrowRight :size="20" /></b></button
          ><small>逐人采集 · 身份分组 · 多人智能构图 · 高清电子版同步交付</small>
        </div>
      </div>
    </section>

    <section v-else-if="screen === 'people'" class="content-panel people-panel">
      <button class="back-button" @click="resetAll">← 返回首页</button>
      <p class="scene-kicker">第 1 步 · 选择合照人数</p>
      <div class="section-heading">
        <h2>这次有几个人一起拍？</h2>
        <span>每个人会单独完成四连拍</span>
      </div>
      <div class="people-option-grid">
        <button
          v-for="count in 4"
          :key="count"
          @click="chooseParticipantCount(count)"
        >
          <b>{{ count }}</b
          ><strong>{{ count }} 人合照</strong
          ><span>{{
            count === 1
              ? "单人动物合照"
              : `${count} 位参与者分别拍摄，AI 合成一张自然合照`
          }}</span>
        </button>
      </div>
    </section>

    <section v-else-if="screen === 'scan'" class="center-panel compact">
      <button class="back-button" @click="go('people')">← 重选人数</button>
      <p class="scene-kicker">第 2 步 · 扫码开始 · {{ participantCount }} 人</p>
      <h2>请用微信扫码开始</h2>
      <img class="qr-image" :src="qr" alt="开始体验二维码" /><button
        v-if="kioskConfig.localOperatorMode"
        class="primary-action small"
        @click="finishScan"
      >
        本机联调：跳过微信扫码
      </button>
      <p class="privacy-note">
        随后 {{ participantCount }} 位参与者将依次完成人脸信息授权。
      </p>
    </section>

    <section
      v-else-if="screen === 'consent'"
      class="content-panel consent-panel"
    >
      <button class="back-button" @click="go('scan')">← 上一步</button>
      <p class="scene-kicker">
        第 3 步 · 第 {{ currentParticipantNo }}/{{ participantCount }} 位授权
      </p>
      <h2>请第 {{ currentParticipantNo }} 位参与者确认</h2>
      <div class="policy-grid">
        <article>
          <b>每人四张原图</b
          ><span
            >每个人的照片独立分组，只用于保留自己的身份、发型、穿搭和体型。</span
          >
        </article>
        <article>
          <b>不同人物不会混用</b
          ><span>生图请求会明确区分1号、2号等身份组，禁止互换五官和服装。</span>
        </article>
        <article>
          <b>逐人检查后才打印</b
          ><span>成品需要确认每个人都正确自然，确认前不会打印。</span>
        </article>
      </div>
      <label class="check-row"
        ><input v-model="consent" type="checkbox" /><span
          >我已阅读并同意处理第
          {{ currentParticipantNo }} 位的四张人脸照片</span
        ></label
      ><label class="check-row"
        ><input v-model="minor" type="checkbox" /><span
          >第 {{ currentParticipantNo }} 位是未成年人</span
        ></label
      ><label v-if="minor" class="check-row guardian"
        ><input v-model="guardianConfirmed" type="checkbox" /><span
          >我是监护人，已知情并同意本次拍摄</span
        ></label
      ><button
        class="primary-action small"
        :disabled="!canConsent"
        @click="acceptConsent"
      >
        {{
          currentParticipantNo < participantCount
            ? `确认并请第 ${currentParticipantNo + 1} 位授权 →`
            : "全部授权完成，选择场景 →"
        }}
      </button>
      <p class="status-note">{{ message }}</p>
    </section>

    <section v-else-if="screen === 'scene'" class="content-panel scene-panel">
      <button class="back-button" @click="go('consent')">← 上一步</button>
      <p class="scene-kicker">第 4 步 · 文字选择</p>
      <div class="section-heading">
        <h2>想拍什么样的合照？</h2>
        <span>每个选项对应一份固定长 Prompt</span>
      </div>
      <div class="scene-option-grid">
        <button
          v-for="scene in scenes"
          :key="scene.scene_id"
          :disabled="busy"
          @click="chooseScene(scene)"
        >
          <b>{{ animalEmoji(scene.scene_id) }}</b
          ><strong>{{ scene.title }}</strong
          ><span>{{ scene.description }}</span
          ><small>{{ scene.prompt_version }}</small>
        </button>
      </div>
    </section>

    <section v-else-if="screen === 'pose'" class="content-panel pose-panel">
      <button class="back-button" @click="go('scene')">← 重选场景</button>
      <p class="scene-kicker">第 5 步 · 姿势选择</p>
      <div class="section-heading">
        <h2>这张照片想用什么朝向？</h2>
        <span
          >已选：{{ animalEmoji(selectedScene?.scene_id) }}
          {{ selectedScene?.title }}</span
        >
      </div>
      <div class="pose-option-grid">
        <button
          v-for="pose in poses"
          :key="pose.pose_id"
          :disabled="busy"
          @click="choosePose(pose)"
        >
          <b>{{ pose.icon }}</b
          ><strong>{{ pose.title }}</strong
          ><span>{{ pose.description }}</span
          ><small>自动匹配构图 · 强化瘦脸美颜</small>
        </button>
      </div>
      <p class="pose-note">
        “背影”采用自然回眸：身体面向动物，脸部保留可识别角度，美白、磨皮、瘦脸仍会完整执行。
      </p>
    </section>

    <section v-else-if="screen === 'capture'" class="capture-layout">
      <div class="camera-stage">
        <video ref="videoEl" muted playsinline></video>
        <div class="camera-mask"></div>
        <strong v-if="countdown" class="countdown">{{ countdown }}</strong>
        <div class="participant-badge">
          第 {{ currentParticipantNo }}/{{ participantCount }} 位
        </div>
        <div class="quality-message" :class="{ good: message.startsWith('✓') }">
          {{ message || currentShot?.hint }}
        </div>
      </div>
      <aside class="capture-guide">
        <p class="scene-kicker">
          逐人拍摄 · 第 {{ currentParticipantNo }}/{{ participantCount }} 位
        </p>
        <h2>{{ currentShot?.title || "拍摄完成" }}</h2>
        <p>
          请只让第 {{ currentParticipantNo }} 位留在镜头前 · 成品姿势：{{
            selectedPose?.title
          }}
        </p>
        <ol class="shot-list">
          <li
            v-for="(guide, index) in shotGuides"
            :key="guide.type"
            :class="{ done: shots[index], active: index === shots.length }"
          >
            <b>{{ guide.icon }}</b
            ><span
              >{{ guide.title
              }}<small>{{
                shots[index] ? "已选出最清晰帧" : guide.hint
              }}</small></span
            >
          </li>
        </ol>
        <button
          class="primary-action small"
          :disabled="busy || !currentShot"
          @click="takeShot"
        >
          {{ busy ? "正在拍摄…" : "开始 3 秒倒计时" }}
        </button>
      </aside>
    </section>

    <section
      v-else-if="screen === 'capture_review'"
      class="content-panel capture-review"
    >
      <p class="scene-kicker">
        第 {{ currentParticipantNo }}/{{ participantCount }} 位 · 确认四张原图
      </p>
      <h2>第 {{ currentParticipantNo }} 位的本人、发型和衣服都拍清楚了吗？</h2>
      <div class="shot-review-grid">
        <article v-for="(shot, index) in shots" :key="shot.type">
          <img :src="shot.localUrl" :alt="shot.title" /><strong>{{
            shot.title
          }}</strong
          ><button @click="redoShot(index)">从这张开始重拍</button>
        </article>
      </div>
      <button class="primary-action small" @click="confirmParticipantPhotos">
        {{
          currentParticipantNo < participantCount
            ? `确认，请第 ${currentParticipantNo + 1} 位进入 →`
            : "完成全部拍摄，查看汇总 →"
        }}
      </button>
    </section>

    <section
      v-else-if="screen === 'group_review'"
      class="content-panel group-review"
    >
      <button class="back-button" @click="redoShot(0, participantCount - 1)">
        ← 返回最后一位
      </button>
      <p class="scene-kicker">全部参与者 · 分组确认</p>
      <h2>{{ participantCount }} 位参与者都拍摄完成</h2>
      <div class="participant-review-grid">
        <section
          v-for="(group, personIndex) in participantShots"
          :key="personIndex"
        >
          <header>
            <b>{{ personIndex + 1 }}</b
            ><strong>第 {{ personIndex + 1 }} 位</strong
            ><button @click="redoShot(0, personIndex)">重新拍摄此人</button>
          </header>
          <div>
            <img
              v-for="shot in group"
              :key="shot.type"
              :src="shot.localUrl"
              :alt="shot.title"
            />
          </div>
        </section>
      </div>
      <button class="primary-action small" @click="proceedToPayment">
        确认所有人，继续生成 →
      </button>
    </section>

    <section v-else-if="screen === 'pay'" class="center-panel compact">
      <button class="back-button" @click="go('group_review')">
        ← 返回全员确认
      </button>
      <p class="scene-kicker">
        {{ participantCount }} 人合照 · 付款成功后生成
      </p>
      <h2>微信扫码支付 ¥{{ paymentAmount.toFixed(2) }}</h2>
      <img
        v-if="qr"
        class="qr-image"
        :src="qr"
        alt="微信支付二维码"
      />
      <button
        class="primary-action small mock-payment-action"
        :disabled="paymentBusy || !paymentMode"
        @click="simulateWechatPayment"
      >
        {{ paymentBusy ? "正在确认…" : "模拟完成微信支付" }}
      </button>
      <p v-if="paymentMode === 'mock'" class="payment-mode-note">
        当前未接入微信商户号，上方为流程测试二维码。
      </p>
      <p class="subcopy">
        将按人物分组发送
        {{ participantCount * 4 }} 张原图，严格区分每个人的身份与服装，并使用“{{
          selectedScene?.title
        }}
        · {{ selectedPose?.title }}”构图及逐人美颜。
      </p>
      <p class="status-note">
        {{
          message ||
          (paymentMode === "mock"
            ? "点击模拟支付后，系统仍会等待后端确认 paid 状态。"
            : "正在安全轮询微信支付状态…")
        }}
      </p>
    </section>

    <section v-else-if="screen === 'generating'" class="center-panel">
      <div class="brush-light">✦</div>
      <p class="scene-kicker">
        {{ participantCount }} 组 × 四张原图 · 多人身份锁定
      </p>
      <h2>正在直接生成全新合照</h2>
      <p class="subcopy">
        逐人保留身份和穿搭，并统一所有人物、动物与环境的空间关系、姿势和真实光影。
      </p>
      <div class="progress-track gold">
        <i :style="{ width: `${progress}%` }"></i>
      </div>
      <b class="progress-number">{{ progress }}% · 预计 {{ secondsLeft }} 秒</b>
      <p class="status-note">{{ message || "不会生成或使用任何模板母版…" }}</p>
    </section>

    <section v-else-if="screen === 'quality_review'" class="preview-layout">
      <div class="preview-frame">
        <img :src="finalUrl" alt="最终候选合照" />
      </div>
      <div class="decision-panel">
        <p class="scene-kicker">成品 · 逐人确认</p>
        <h2>每个人都像本人，姿势和瘦脸也自然吗？</h2>
        <p>
          请逐人检查五官、脸宽、下颌线、肤色、眼镜、发型与衣服，再检查手部、多人站位，以及人物和动物的光影与空间关系。确认前不会打印。
        </p>
        <button
          class="primary-action small"
          :disabled="busy"
          @click="approveAndDeliver"
        >
          确认合格，交付并打印 →</button
        ><button class="secondary-action" @click="rejectResult">
          不合格，停止打印并找工作人员
        </button>
      </div>
    </section>

    <section v-else-if="screen === 'printing'" class="printing-layout">
      <div class="printer-illustration">
        <div class="paper">
          <img :src="finalUrl" /><small>{{ order?.order_no?.slice(-6) }}</small>
        </div>
      </div>
      <div>
        <p class="scene-kicker">第 10 步 · Canon SELPHY CP1500</p>
        <h2>正在打印，请稍候</h2>
        <p class="subcopy">请不要拉扯照片，等它完全落入出纸托盘。</p>
        <div class="progress-track">
          <i :style="{ width: `${progress}%` }"></i>
        </div>
        <b class="progress-number">{{ progress }}% · 约 {{ secondsLeft }} 秒</b>
      </div>
    </section>

    <section v-else-if="screen === 'result'" class="result-layout">
      <div class="success-mark">✓</div>
      <div>
        <p class="scene-kicker">交付完成</p>
        <h2>{{ deliveryPrinted ? "照片打印完成" : "高清电子版已生成" }}</h2>
        <p class="subcopy">
          {{
            deliveryPrinted
              ? "请从出纸口取片；电子版链接 24 小时内有效。"
              : "当前打印机未连接，没有假装打印；可扫码保存高清电子版。"
          }}
        </p>
        <button class="secondary-action" @click="resetAll">
          结束并返回首页
        </button>
      </div>
      <div class="download-card">
        <img :src="downloadQr" alt="高清照片直接下载二维码" /><b>扫码直接下载高清照片</b
        ><span>这是取片码，不是支付码 · 链接 24 小时内有效</span>
      </div>
    </section>

    <section v-else-if="screen === 'error'" class="center-panel error-panel">
      <div class="error-icon">!</div>
      <p class="scene-kicker">需要工作人员协助</p>
      <h2>{{ errorInfo.title }}</h2>
      <p class="subcopy">{{ errorInfo.detail }}</p>
      <div class="error-actions">
        <button
          v-if="errorInfo.recoverable"
          class="primary-action small"
          @click="recover"
        >
          返回重试</button
        ><button class="secondary-action" @click="resetAll">
          结束本次体验
        </button>
      </div>
      <p class="status-note">
        付费但未交付的订单应由工作人员重试或按原路退款。
      </p>
    </section>
  </main>
</template>
