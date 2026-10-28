// End-to-end check of the canvas preview against a running ComfyUI (Node + Playwright).
// Run: node tests/e2e/preview_check.js [server_url] [screenshot_dir]
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const URL = process.argv[2] || "http://127.0.0.1:8188";
const OUT = process.argv[3] || path.join(__dirname, "..", "..", "examples", "out");
const WF = path.join(__dirname, "..", "..", "example_workflows", "titlerig_rig_only.json");

function fail(msg) { console.error("FAIL:", msg); process.exit(1); }

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(URL);
  await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");
  const wf = JSON.parse(fs.readFileSync(WF, "utf8"));
  await page.evaluate(async (wf) => { await window.app.loadGraphData(wf, true, true, "titlerig_rig_only"); }, wf);

  // the Render node gets a preview widget with a rendered image
  const firstSrc = await page.waitForFunction(() => {
    const img = document.querySelector(".tr-preview img");
    return img && img.naturalWidth > 0 ? img.src : null;
  }, null, { timeout: 60000 }).then((h) => h.jsonValue()).catch(() => fail("no preview image appeared"));
  console.log("preview widgets:", await page.locator(".tr-preview").count());

  // changing the Text node's word re-renders the preview without queueing the workflow
  await page.evaluate(() => {
    const t = window.app.graph._nodes.find((n) => n.comfyClass === "TitleRigText");
    t.widgets.find((w) => w.name === "text").value = "LIVE!";
    window.app.graph.setDirtyCanvas(true, true);
  });
  await page.waitForFunction((s) => {
    const img = document.querySelector(".tr-preview img");
    return img && img.src !== s && img.naturalWidth > 0;
  }, firstSrc, { timeout: 30000 }).catch(() => fail("preview did not update after a widget change"));
  console.log("updated after widget change: ok");

  // depth pass + guides chips
  const stage = page.locator(".tr-preview").first();
  await stage.getByRole("button", { name: "Depth" }).click();
  await stage.getByRole("button", { name: "Guides" }).click();
  await page.waitForTimeout(2500);
  const pressed = await stage.locator('button[aria-pressed="true"]').allTextContents();
  if (!pressed.includes("Depth") || !pressed.includes("Guides")) fail("chips did not toggle: " + pressed);
  await stage.getByRole("button", { name: "Beauty" }).click();
  await page.waitForTimeout(2500);

  // Render Animation: the scrubber learns the clip length and moving it shows another frame
  const anim = page.locator(".tr-preview").filter({ has: page.locator('input[type="range"]') }).first();
  await page.waitForFunction(() => {
    const r = document.querySelector('.tr-preview input[type="range"]');
    return r && +r.max > 1;
  }, null, { timeout: 60000 }).catch(() => fail("scrubber never learned the frame count"));
  const before = await anim.locator("img").getAttribute("src");
  await anim.locator('input[type="range"]').evaluate((r) => { r.value = String(Math.floor(+r.max / 3)); r.dispatchEvent(new Event("input")); });
  await page.waitForFunction((s) => {
    const r = document.querySelector('.tr-preview input[type="range"]');
    const img = r.closest(".tr-preview").querySelector("img");
    return img.src !== s;
  }, before, { timeout: 30000 }).catch(() => fail("scrubbing did not change the frame"));
  console.log("scrubber:", await anim.locator(".tr-time span").textContent());

  // frame the Render node and screenshot dark, then light palette
  await page.evaluate(() => {
    const n = window.app.graph._nodes.find((n) => n.comfyClass === "TitleRigRender");
    const c = window.app.canvas;
    c.ds.scale = 1.1;
    c.ds.offset = [-n.pos[0] + 600, -n.pos[1] + 80];
    c.setDirty(true, true);
  });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, "preview_dark.png") });
  await page.evaluate(async () => {
    const s = window.app.extensionManager?.setting;
    if (s?.set) await s.set("Comfy.ColorPalette", "light");
    else window.app.ui.settings.setSettingValue("Comfy.ColorPalette", "light");
  });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(OUT, "preview_light.png") });
  await page.evaluate(async () => {
    const s = window.app.extensionManager?.setting;
    if (s?.set) await s.set("Comfy.ColorPalette", "dark");
  });
  console.log("PASS");
  await browser.close();
})();
