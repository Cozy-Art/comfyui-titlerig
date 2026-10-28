// Turn workflows/api/*.json into drag-and-drop UI workflows (workflows/*.json) using the real ComfyUI frontend,
// so widget order and links are exactly what ComfyUI itself saves.
// Needs a running ComfyUI with TitleRig installed and Playwright (Node). Run: node workflows/to_ui.js [server_url]
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const HERE = __dirname;
const URL = process.argv[2] || "http://127.0.0.1:8188";

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1800, height: 1100 } });
  await page.goto(URL);
  await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
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
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(HERE, "..", "examples", "out", `${name}_graph.png`) });
    console.log(`wrote workflows/${name}.json (${wf.wf.nodes.length} nodes, ${wf.wf.links.length} links)` +
      (wf.unknown.length ? ` UNKNOWN NODES: ${wf.unknown.join(", ")}` : ""));
  }
  await browser.close();
})();
