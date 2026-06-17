#!/usr/bin/env node
const fs = require("fs");
const { PNG } = require("pngjs");
const pixelmatch = require("pixelmatch").default;

const [oldPath, newPath] = process.argv.slice(2);

if (!oldPath || !newPath) {
  console.error(JSON.stringify({ error: "Usage: pixelmatch_diff.js <old.png> <new.png>" }));
  process.exit(1);
}

function loadPng(path) {
  return PNG.sync.read(fs.readFileSync(path));
}

function toCanvas(img, width, height) {
  const canvas = new PNG({ width, height });
  PNG.bitblt(img, canvas, 0, 0, img.width, img.height, 0, 0);
  return canvas;
}

try {
  const img1 = loadPng(oldPath);
  const img2 = loadPng(newPath);
  const width = Math.max(img1.width, img2.width);
  const height = Math.max(img1.height, img2.height);
  const a = toCanvas(img1, width, height);
  const b = toCanvas(img2, width, height);

  const diffPixels = pixelmatch(a.data, b.data, null, width, height, { threshold: 0.1 });
  const totalPixels = width * height;
  const score = totalPixels === 0 ? 0 : diffPixels / totalPixels;

  console.log(
    JSON.stringify({
      score,
      diff_pixels: diffPixels,
      total_pixels: totalPixels,
      method: "pixelmatch",
    })
  );
} catch (error) {
  console.error(JSON.stringify({ error: error.message }));
  process.exit(1);
}
