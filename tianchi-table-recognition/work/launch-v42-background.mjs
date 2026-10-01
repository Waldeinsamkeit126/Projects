import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const cwd = process.cwd();
const args = [
  "outputs/table_competition_solution/run.mjs",
  "--tests", "work/competition_data/multimodal_table_recognition/tests.xlsx",
  "--template", "work/competition_data/multimodal_table_recognition/submit-template.xlsx",
  "--media", "work/competition_data/multimodal_table_recognition/files",
  "--output", "outputs/table_competition_solution/submission-candidate-v42-qwen38max-image-full.xlsx",
  "--state", "outputs/table_competition_solution/state-v42-qwen38max-image-full",
  "--concurrency", "1",
  "--max-attempts", "8",
  "--model-image", "qwen3.8-max-0902",
  "--model-pdf", "qwen3.8-max-0902",
  "--include-source", "image",
  "--base", "outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx",
  "--enable-thinking",
];

const env = { ...process.env };
const pathValue = process.env.Path ?? process.env.PATH;
delete env.PATH;
delete env.Path;
if (pathValue) env.Path = pathValue;

const stdoutPath = path.join(cwd, "work", "v42-background-retry.stdout.log");
const stderrPath = path.join(cwd, "work", "v42-background-retry.stderr.log");
const stdout = fs.openSync(stdoutPath, "w");
const stderr = fs.openSync(stderrPath, "w");
const child = spawn(process.execPath, args, {
  cwd,
  env,
  detached: true,
  windowsHide: true,
  stdio: ["ignore", stdout, stderr],
});
child.unref();
fs.closeSync(stdout);
fs.closeSync(stderr);
console.log(`V42_RETRY_BACKGROUND_PID ${child.pid}`);
