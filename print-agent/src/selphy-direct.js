"use strict";

const childProcess = require("child_process");
const { promisify } = require("util");
const ipp = require("ipp");
const { Jimp } = require("jimp");

const execFile = promisify(childProcess.execFile);
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const PAPER_PROFILES = [
  { match: "89x119mm", media: "om_dsc-photo_89x119mm", width: 8900, height: 11900, pixelsWide: 1051, pixelsHigh: 1406 },
  { match: "100x148mm", media: "jpn_hagaki_100x148mm", width: 10000, height: 14800, pixelsWide: 1181, pixelsHigh: 1748 },
  { match: "54x86mm", media: "custom_54x86mm_54x86mm", width: 5400, height: 8600, pixelsWide: 638, pixelsHigh: 1016 },
];

function execute(printer, operation, message) {
  return new Promise((resolve, reject) => {
    printer.execute(operation, message, (error, response) => {
      if (error) reject(error);
      else resolve(response || {});
    });
  });
}

async function discoverPrinterUri() {
  const { stdout } = await execFile("/usr/bin/ippfind", ["-T", "5"], { timeout: 8000 });
  const uri = String(stdout).split(/\r?\n/).map((item) => item.trim()).find(Boolean);
  if (!uri) throw new Error("没有发现 CP1500 的 USB IPP 服务");
  return uri;
}

function extractEmbeddedJpeg(printHtml = "") {
  const match = String(printHtml).match(/data:image\/jpeg;base64,([A-Za-z0-9+/=]+)/i);
  if (!match) throw new Error("打印排版中没有内嵌 JPEG 成品");
  return Buffer.from(match[1], "base64");
}

async function readPrinterState(printerUri) {
  const { stdout } = await execFile(
    "/usr/bin/ipptool",
    ["-tv", printerUri, "/usr/share/cups/ipptool/get-printer-attributes.test"],
    { timeout: 12000, maxBuffer: 2 * 1024 * 1024 },
  );
  const output = String(stdout);
  const state = output.match(/printer-state \(enum\) = ([^\r\n]+)/)?.[1]?.trim() || "unknown";
  const reasons = output.match(/printer-state-reasons \(keyword\) = ([^\r\n]+)/)?.[1]?.trim() || "unknown";
  const mediaReady = output.match(/media-ready \(keyword\) = ([^\r\n]+)/)?.[1]?.trim() || "";
  return { state, reasons, mediaReady };
}

async function currentPaper(printerUri) {
  const status = await readPrinterState(printerUri);
  if (status.state !== "idle" || (status.reasons !== "none" && status.reasons !== "unknown")) {
    throw new Error(`打印机当前不可用：${status.state}, ${status.reasons}`);
  }
  const mediaReady = status.mediaReady;
  const profile = PAPER_PROFILES.find((item) => mediaReady.includes(item.match));
  if (!profile) throw new Error(`无法识别当前相纸：${mediaReady || "未报告纸张"}`);
  return profile;
}

async function baselineJpeg(source, profile) {
  const image = await Jimp.read(source);
  image.cover({ w: profile.pixelsWide, h: profile.pixelsHigh });
  return image.getBuffer("image/jpeg", { quality: 92 });
}

async function waitForJob(printerUri, jobId) {
  const deadline = Date.now() + 180000;
  // Print-Job 只有在设备接受任务并返回 job-id 后才进入这里；即使首轮轮询时
  // 设备已经完成，也应允许 idle 被识别为成功。
  let sawProcessing = true;
  while (Date.now() < deadline) {
    const status = await readPrinterState(printerUri);
    if (status.state === "processing") sawProcessing = true;
    if (status.reasons !== "none" && status.reasons !== "unknown") {
      throw new Error(`CP1500 打印异常：${status.reasons}`);
    }
    if (sawProcessing && status.state === "idle") {
      return { jobId, reasons: "job-completed-successfully", impressions: 1 };
    }
    await sleep(1000);
  }
  throw new Error("CP1500 直连打印超过 180 秒仍未完成");
}

async function printSelphyDirect(printHtml, jobName) {
  const printerUri = await discoverPrinterUri();
  const printer = ipp.Printer(printerUri);
  const profile = await currentPaper(printerUri);
  const jpeg = await baselineJpeg(extractEmbeddedJpeg(printHtml), profile);
  const response = await execute(printer, "Print-Job", {
    "operation-attributes-tag": {
      "attributes-charset": "utf-8",
      "attributes-natural-language": "zh-cn",
      "printer-uri": printerUri,
      "requesting-user-name": process.env.USER || "ai-zoo",
      "job-name": jobName || "AI-ZOO photo",
      "document-format": "image/jpeg",
    },
    "job-attributes-tag": {
      copies: 1,
      media: profile.media,
      "media-col": {
        "media-size": { "x-dimension": profile.width, "y-dimension": profile.height },
        "media-left-margin": 0,
        "media-right-margin": 0,
        "media-top-margin": 0,
        "media-bottom-margin": 0,
        "media-type": "photographic",
        "media-source": "photo",
      },
      "print-color-mode": "color",
      "print-quality": 4,
      "printer-resolution": "300dpi",
    },
    data: jpeg,
  });
  const jobAttrs = response["job-attributes-tag"] || {};
  const jobId = Number(jobAttrs["job-id"] || 0);
  if (!jobId) throw new Error("CP1500 未返回有效任务编号");
  return { ...(await waitForJob(printerUri, jobId)), media: profile.media };
}

module.exports = { printSelphyDirect };
