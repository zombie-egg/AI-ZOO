"use strict";

const childProcess = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { promisify } = require("util");
const { Jimp } = require("jimp");

const execFile = promisify(childProcess.execFile);

const PAPER_PROFILES = [
  { match: "89x119mm", media: "om_dsc-photo_89x119mm", width: 8900, height: 11900, pixelsWide: 1051, pixelsHigh: 1406 },
  { match: "100x148mm", media: "jpn_hagaki_100x148mm", width: 10000, height: 14800, pixelsWide: 1181, pixelsHigh: 1748 },
  { match: "54x86mm", media: "custom_54x86mm_54x86mm", width: 5400, height: 8600, pixelsWide: 638, pixelsHigh: 1016 },
];

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

function printJobTest(profile) {
  return `{
  NAME "AI ZOO SELPHY photo"
  OPERATION Print-Job
  GROUP operation-attributes-tag
  ATTR charset attributes-charset utf-8
  ATTR language attributes-natural-language zh-cn
  ATTR uri printer-uri $uri
  ATTR name requesting-user-name $user
  ATTR mimeMediaType document-format image/jpeg
  GROUP job-attributes-tag
  ATTR integer copies 1
  ATTR keyword media ${profile.media}
  ATTR collection media-col {
    MEMBER collection media-size {
      MEMBER integer x-dimension ${profile.width}
      MEMBER integer y-dimension ${profile.height}
    }
    MEMBER integer media-left-margin 0
    MEMBER integer media-right-margin 0
    MEMBER integer media-top-margin 0
    MEMBER integer media-bottom-margin 0
    MEMBER keyword media-type photographic
    MEMBER keyword media-source photo
  }
  ATTR keyword print-color-mode color
  ATTR enum print-quality 4
  FILE $filename
  STATUS successful-ok
  STATUS successful-ok-ignored-or-substituted-attributes
  EXPECT job-id OF-TYPE integer WITH-VALUE >0
}
{
  NAME "Wait for SELPHY job completion"
  OPERATION Get-Job-Attributes
  GROUP operation-attributes-tag
  ATTR charset attributes-charset utf-8
  ATTR language attributes-natural-language zh-cn
  ATTR uri printer-uri $uri
  ATTR integer job-id $job-id
  ATTR name requesting-user-name $user
  STATUS successful-ok
  EXPECT job-id
  EXPECT job-state WITH-VALUE >5 REPEAT-NO-MATCH
  DISPLAY job-state
  DISPLAY job-state-reasons
}`;
}

async function printSelphyDirect(printHtml, jobName) {
  const printerUri = await discoverPrinterUri();
  const profile = await currentPaper(printerUri);
  const jpeg = await baselineJpeg(extractEmbeddedJpeg(printHtml), profile);
  const tempDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "ai-zoo-selphy-"));
  const imagePath = path.join(tempDir, "photo.jpg");
  const testPath = path.join(tempDir, "print-and-wait.test");
  try {
    await fs.promises.writeFile(imagePath, jpeg);
    await fs.promises.writeFile(testPath, printJobTest(profile), "utf8");
    const { stdout } = await execFile(
      "/usr/bin/ipptool",
      ["-tv", "-T", "240", "-d", `job-name=${jobName || "AI-ZOO photo"}`, "-f", imagePath, printerUri, testPath],
      { timeout: 300000, maxBuffer: 4 * 1024 * 1024 },
    );
    const output = String(stdout);
    const jobId = Number(output.match(/job-id \(integer\) = (\d+)/)?.[1] || 0);
    if (!jobId) throw new Error("CP1500 未返回有效任务编号");
    return { jobId, reasons: "job-completed-successfully", impressions: 1, media: profile.media };
  } finally {
    await fs.promises.rm(tempDir, { recursive: true, force: true });
  }
}

module.exports = { printSelphyDirect };
