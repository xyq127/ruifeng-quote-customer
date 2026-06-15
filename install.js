#!/usr/bin/env node
/**
 * ruifeng-data-cleaning install script
 *
 * Copies the skill to both Claude Code (~/.claude/skills/) and Hermes (~/.hermes/skills/).
 * Overwrites existing files to ensure sync from the single source of truth.
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = os.homedir();
const TARGETS = [
  path.join(HOME, '.claude', 'skills', 'ruifeng-data-cleaning'),
  path.join(HOME, '.hermes', 'skills', 'ruifeng-data-cleaning'),
];

const SOURCE = __dirname;

// Directories to sync
const DIRS = ['references', 'scripts', 'modules'];
const PLATFORM_CLI_DIR = 'cli-platform-service';

function copyDir(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// Remove stale files that no longer exist in source
function cleanDir(dest, src) {
  if (!fs.existsSync(dest)) return;
  const entries = fs.readdirSync(dest, { withFileTypes: true });
  for (const entry of entries) {
    const destPath = path.join(dest, entry.name);
    const srcPath = path.join(src, entry.name);
    if (!fs.existsSync(srcPath)) {
      if (entry.isDirectory()) {
        fs.rmSync(destPath, { recursive: true });
      } else {
        fs.unlinkSync(destPath);
      }
    }
  }
}

for (const target of TARGETS) {
  console.log(`Installing to ${target}...`);

  // Ensure target directory exists
  fs.mkdirSync(target, { recursive: true });

  // Copy SKILL.md
  fs.copyFileSync(path.join(SOURCE, 'SKILL.md'), path.join(target, 'SKILL.md'));

  // Copy subdirectories
  for (const dir of DIRS) {
    const srcDir = path.join(SOURCE, dir);
    const destDir = path.join(target, dir);
    if (fs.existsSync(srcDir)) {
      copyDir(srcDir, destDir);
      cleanDir(destDir, srcDir);
    }
  }

  console.log(`  Done: ${target}`);
}

// ── Python 环境检测 ────────────────────────────────────
const { execSync } = require('child_process');

function detectPython() {
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      execSync(`${cmd} --version`, { stdio: 'pipe' });
      return cmd;
    } catch { /* try next */ }
  }
  return null;
}

const pythonCmd = detectPython();
if (!pythonCmd) {
  console.error('错误: 未找到 Python 3.10+。请先安装 Python: https://www.python.org/downloads/');
  process.exit(1);
}
console.log(`检测到 Python: ${pythonCmd}`);

// ── 安装 Python CLI ───────────────────────────────────
const pipDir = path.join(SOURCE, PLATFORM_CLI_DIR);
console.log(`Installing Python CLI from ${pipDir}...`);

// 平台感知参数: Linux 系统 Python 需要 --break-system-packages
const isLinux = process.platform === 'linux';
const breakFlag = isLinux ? ' --break-system-packages' : '';

try {
  execSync(`${pythonCmd} -m pip install -e "${pipDir}"[data-clean]${breakFlag}`, {
    cwd: SOURCE,
    stdio: 'inherit',
    env: { ...process.env, PIP_REQUIRE_VIRTUALENV: 'false' },
  });
  console.log('  Python CLI installed.');
  console.log('  注意: 首次使用前请运行 "playwright install chromium" 安装浏览器内核');
} catch (err) {
  console.error(`  Warning: Python CLI install failed: ${err.message}`);
  console.error(`  You can install manually: ${pythonCmd} -m pip install -e "./cli-platform-service[data-clean]"${breakFlag}`);
}

console.log('ruifeng-data-cleaning installed successfully.');
