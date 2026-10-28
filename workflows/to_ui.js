// Turn workflows/api/*.json into drag-and-drop UI workflows (workflows/*.json) using the real ComfyUI frontend,
// so widget order and links are exactly what ComfyUI itself saves.
// Needs a running ComfyUI with TitleRig installed and Playwright (Node). Run: node workflows/to_ui.js [server_url]
// --verify: also load each saved UI file back, let the frontend build the prompt, queue it and wait for success.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const HERE = __dirname;
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
  const files = fs.readdirSync(path.join(HERE, "api")).filter((f) => f.endsWith(".json")).sort();
  for (const f of files) {
    const name = f.replace(/\.json$/, "");
    const api = JSON.parse(fs.readFileSync(path.join(HERE, "api", f), "utf8"));
    const wf = await page.evaluate(async ([api, name]) => {
      await window.app.loadApiJson(api, name);
      const g = window.app.graph;
      const unknown = g._nodes.filter((n) => !window.LiteGraph.registered_node_types[n.type]).map((n) => n.type);
      if (window.app.canvas && window.app.canvas.ds) window.app.canvas.ds.offset = [40, 40];
      window.app.graph.setDirtyCanvas(true, true);
      return { wf: g.serialize(), unknown };
    }, [api, name]);
    fs.writeFileSync(path.join(HERE, `${name}.json`), JSON.stringify(wf.wf, null, 2));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    await page.mouse.click(900, 600);
    await page.keyboard.press(".");  // fit view to the whole graph
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(HERE, "..", "examples", "out", `${name}_graph.png`) });
    console.log(`wrote workflows/${name}.json (${wf.wf.nodes.length} nodes, ${wf.wf.links.length} links)` +
      (wf.unknown.length ? ` UNKNOWN NODES: ${wf.unknown.join(", ")}` : ""));
  }
  if (VERIFY) {
    for (const f of files) {
      const name = f.replace(/\.json$/, "");
      const wf = JSON.parse(fs.readFileSync(path.join(HERE, `${name}.json`), "utf8"));
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
