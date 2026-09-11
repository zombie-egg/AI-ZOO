"use strict";

const childProcess = require("child_process");

// CP1500 media families. Width/height are in millimetres here and converted
// to Chromium's micrometre PrintOptions only at the final print call.
const PAPER_PROFILES = [
  {
    id: "l",
    label: "L 相纸（89 × 119 mm）",
    widthMm: 89,
    heightMm: 119,
    names: ["89x119", "89 x 119", "l size", "l-size", "l paper", "kl", "kp-108"],
  },
  {
    id: "postcard",
    label: "明信片相纸（100 × 148 mm）",
    widthMm: 100,
    heightMm: 148,
    names: ["100x148", "100 x 148", "postcard", "4x6", "4 x 6", "rp-108", "rp-54"],
  },
  {
    id: "card",
    label: "卡片相纸（54 × 86 mm）",
    widthMm: 54,
    heightMm: 86,
    names: ["54x86", "54 x 86", "card size", "credit card", "kc-36", "kc-18"],
  },
];

function normalise(value = "") {
  return String(value).toLowerCase().replace(/[×*]/g, "x").replace(/\s+/g, " ").trim();
}

function profileFromText(value = "") {
  const text = normalise(value);
  if (!text) return null;
  return PAPER_PROFILES.find((profile) => profile.names.some((name) => text.includes(name))) || null;
}

function profileFromPageSize(pageSize) {
  const width = Number(pageSize?.width || 0) / 1000;
  const height = Number(pageSize?.height || 0) / 1000;
  if (!width || !height) return null;
  return PAPER_PROFILES.find((profile) =>
    Math.abs(profile.widthMm - Math.min(width, height)) <= 2 &&
    Math.abs(profile.heightMm - Math.max(width, height)) <= 2,
  ) || null;
}

function readWindowsPrintConfiguration(printerName) {
  if (process.platform !== "win32" || !printerName) return "";
  // Get-PrintConfiguration is provided by Windows' PrintManagement module.
  // It returns the paper currently selected in the Canon queue; the CP1500
  // driver uses this selection to match its loaded cassette.
  const escapedName = String(printerName).replace(/'/g, "''");
  const script = [
    "$ErrorActionPreference='Stop'",
    `$c=Get-PrintConfiguration -PrinterName '${escapedName}'`,
    "$c | Select-Object * | ConvertTo-Json -Compress",
  ].join("; ");
  try {
    const output = childProcess.execFileSync(
      `${process.env.SystemRoot || "C:\\Windows"}\\System32\\WindowsPowerShell\\v1.0\\powershell.exe`,
      ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
      { windowsHide: true, timeout: 7000, encoding: "utf8" },
    );
    return String(output || "");
  } catch (error) {
    console.warn(`读取 Windows 打印纸张设置失败：${error.message}`);
    return "";
  }
}

function paperProfileForPrinter(printerName, fallbackPageSize) {
  const fallback = profileFromPageSize(fallbackPageSize);
  if (process.platform !== "win32") return { profile: fallback, source: "request" };

  const configuration = readWindowsPrintConfiguration(printerName);
  const configured = profileFromText(configuration);
  if (configured) return { profile: configured, source: "windows-print-configuration" };

  try {
    // win32-pdf-printer also exposes the Canon driver's reported paper names.
    // Use it only when it unambiguously identifies one CP1500 media family.
    const { getPaperSizeInfo } = require("win32-pdf-printer");
    const info = getPaperSizeInfo({ printer: printerName }) || {};
    const candidates = [...new Set(
      (info.PaperSizes || [])
        .map((size) => profileFromText(size?.PaperName))
        .filter(Boolean),
    )];
    if (candidates.length === 1) return { profile: candidates[0], source: "windows-printer-driver" };
  } catch (error) {
    console.warn(`读取 Canon 纸张能力失败：${error.message}`);
  }
  return { profile: fallback, source: "request-fallback" };
}

function applyPaperProfile(data, printerName) {
  const { profile, source } = paperProfileForPrinter(printerName, data?.pageSize);
  if (!profile || !data) return { profile: null, source };
  data.pageSize = {
    width: Math.round(profile.widthMm * 1000),
    height: Math.round(profile.heightMm * 1000),
    unit: "",
  };
  data.paperName = profile.label;
  if (typeof data.html === "string") {
    data.html = data.html.replace(
      /@page\s*\{\s*size\s*:[^;]+;/i,
      `@page{size:${profile.widthMm}mm ${profile.heightMm}mm;`,
    );
  }
  return { profile, source };
}

module.exports = { PAPER_PROFILES, applyPaperProfile, paperProfileForPrinter };
