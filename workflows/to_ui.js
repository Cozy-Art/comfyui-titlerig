// Turn workflows/api/*.json into drag-and-drop UI workflows (example_workflows/*.json) using the real ComfyUI frontend,
// so widget order and links are exactly what ComfyUI itself saves.
// Needs a running ComfyUI with TitleRig installed and Playwright (Node). Run: node workflows/to_ui.js [server_url]
// --verify: also load each saved UI file back, let the frontend build the prompt, queue it and wait for success.
// Only the model-free workflows (RUNNABLE) are ever queued; AI and bonus (API, paid) workflows are only converted.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const HERE = __dirname;
const RUNNABLE = ["titlerig_rig_only", "titlerig_audio_react", "titlerig_cutout"];
// UI files ComfyUI should offer as templates go to ../example_workflows (it serves templates from the first of
// example_workflows / example / examples / workflow / workflows it finds, so they must not sit in workflows/).
// The paid API bonus workflows stay in workflows/bonus, out of the Templates menu.
const DIRS = [["api", path.join("..", "example_workflows")], [path.join("api", "bonus"), "bonus"]];
const args = process.argv.slice(2);
const VERIFY = args.includes("--verify");
const URL = args.find((a) => !a.startsWith("--")) || "http://127.0.0.1:8188";

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  await page.goto(URL);
  await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape"); // close the templates dialog the frontend opens on first run
  const done = [];
  for (const [src, dst] of DIRS) {
    fs.mkdirSync(path.join(HERE, dst), { recursive: true });
    const files = fs.readdirSync(path.join(HERE, src)).filter((f) => f.endsWith(".json")).sort();
    for (const f of files) {
      const name = f.replace(/\.json$/, "");
      const api = JSON.parse(fs.readFileSync(path.join(HERE, src, f), "utf8"));
      const wf = await page.evaluate(async ([api, name]) => {
        await window.app.loadApiJson(api, name);
        const g = window.app.graph;
        const unknown = g._nodes.filter((n) => !window.LiteGraph.registered_node_types[n.type]).map((n) => n.type);
        window.app.graph.setDirtyCanvas(true, true);
        return { wf: g.serialize(), unknown };
      }, [api, name]);
      fs.writeFileSync(path.join(HERE, dst, `${name}.json`), JSON.stringify(wf.wf, null, 2));
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
      await page.mouse.click(900, 600);
      await page.keyboard.press(".");
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(HERE, "..", "examples", "out", `${name}_graph.png`) });
      console.log(`wrote workflows/${dst === "." ? "" : dst + "/"}${name}.json (${wf.wf.nodes.length} nodes, ${wf.wf.links.length} links)` +
        (wf.unknown.length ? ` UNKNOWN NODES: ${wf.unknown.join(", ")}` : ""));
      done.push([dst, name]);
    }
  }
  if (VERIFY) {
    for (const [dst, name] of done) {
      if (!RUNNABLE.includes(name)) continue;  // never queue AI (needs models) or bonus (paid API) workflows
      const wf = JSON.parse(fs.readFileSync(path.join(HERE, dst, `${name}.json`), "utf8"));
      const res = await page.evaluate(async ([wf, name]) => {
        await window.app.loadGraphData(wf, true, true, name);
        const { output } = await window.app.graphToPrompt();
        const r = await fetch("/prompt", { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ prompt: output }) });
        return { status: r.status, body: await r.json() };
      }, [wf, name]);
      if (res.status !== 200) { console.log(`VERIFY ${name}: rejected ${JSON.stringify(res.body).slice(0, 800)}`); process.exitCode = 1; continue; }
      const id = res.body.prompt_id;
      let h = {};
      for (let i = 0; i < 900 && !h[id]; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        h = await (await fetch(`${URL}/history/${id}`)).json();
      }
      const st = h[id] ? h[id].status.status_str : "timeout";
      console.log(`VERIFY ${name}: UI file -> frontend prompt -> ${st}`);
      if (st !== "success") process.exitCode = 1;
    }
  }
  await browser.close();
})();
