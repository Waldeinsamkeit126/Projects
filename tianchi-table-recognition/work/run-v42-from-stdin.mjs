import fs from "node:fs";
import { spawn } from "node:child_process";

const workspaceId = "ws-zpzcvtpmb0e3zl4f";
const expectedKeyPrefix = "sk-ws-H.PDRPHRH";
const args = [
  "outputs/table_competition_solution/run.mjs",
  "--tests", "work/competition_data/multimodal_table_recognition/tests.xlsx",
  "--template", "work/competition_data/multimodal_table_recognition/submit-template.xlsx",
  "--media", "work/competition_data/multimodal_table_recognition/files",
  "--output", "outputs/table_competition_solution/submission-candidate-v42-qwen38max-image-full.xlsx",
  "--state", "outputs/table_competition_solution/state-v42-qwen38max-image-full",
  "--concurrency", "1",
  "--max-attempts", "8",
  "--max-completion-tokens", "8192",
  "--model-image", "qwen3.8-max-0902",
  "--model-pdf", "qwen3.8-max-0902",
  "--include-source", "image",
  "--base", "outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx",
  "--enable-thinking",
];

if (process.stdin.isTTY && typeof process.stdin.setRawMode === "function") process.stdin.setRawMode(true);
process.stdin.resume();
console.log("READY_FOR_API_KEY");
const apiKey = await new Promise((resolve, reject) => {
  let buffer = "";
  const onData = (chunk) => {
    for (const character of String(chunk)) {
      if (character === "\r" || character === "\n") {
        process.stdin.off("data", onData);
        if (process.stdin.isTTY && typeof process.stdin.setRawMode === "function") process.stdin.setRawMode(false);
        process.stdin.pause();
        resolve(buffer);
        return;
      }
      if (character === "\u0003") {
        process.stdin.off("data", onData);
        reject(new Error("输入已取消"));
        return;
      }
      buffer += character;
    }
  };
  process.stdin.on("data", onData);
});

if (!String(apiKey).startsWith(expectedKeyPrefix) || String(apiKey).length < 80) {
  console.error("API_KEY_REJECTED");
  process.exit(2);
}

const env = { ...process.env };
env.DASHSCOPE_API_KEY = String(apiKey).trim();
env.ALIYUN_WORKSPACE_ID = workspaceId;

const stdoutLog = fs.createWriteStream("work/v42-stdin-run.stdout.log", { flags: "w" });
const stderrLog = fs.createWriteStream("work/v42-stdin-run.stderr.log", { flags: "w" });
const child = spawn(process.execPath, args, {
  cwd: process.cwd(),
  env,
  windowsHide: true,
  stdio: ["ignore", "pipe", "pipe"],
});

child.stdout.on("data", (chunk) => {
  process.stdout.write(chunk);
  stdoutLog.write(chunk);
});
child.stderr.on("data", (chunk) => {
  process.stderr.write(chunk);
  stderrLog.write(chunk);
});

const exitCode = await new Promise((resolve) => child.once("close", resolve));
stdoutLog.end();
stderrLog.end();
console.log(`V42_CHILD_EXIT ${exitCode}`);
process.exitCode = Number(exitCode) || 0;
