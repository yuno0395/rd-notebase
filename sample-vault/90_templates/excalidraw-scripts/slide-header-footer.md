/*
Slide header/footer (Excalidraw Automate script, prototype)

Treats each frame of a drawing note (.excalidraw.md) as one slide and rebuilds a header and footer per frame.

  Header: slide name (frame name)                           #F02
  Footer: noteID#F02  title | status, keys | updated date | 2 / 5

- Frames without a frame ID (customData.kvFrame = F01, F02 ...) get the next free number. Once assigned it never changes (it is the unit for embeds ![[...#F02]])
- Page order follows position (top row first, left to right). Reorder by moving frames
- Header/footer elements made last time (customData.kvHF) are deleted and rebuilt. Hand-drawn elements are not touched
- Header/footer elements belong to the frame (frameId) and are locked, so they move with the frame
- "Add slide": adds an A-series landscape frame (1:1.414) at the right end, then rebuilds

Location: set Excalidraw's "Script folder" to 90_templates/excalidraw-scripts.
It then appears in the command palette as "Excalidraw: (Script) slide-header-footer".
*/

const W = 800, H = 566;          // A-series ratio (docs: vault design 9.2). Same as tools/draw.py
const GAP = 100;                 // gap between added frames
const PAD = 16;                  // padding inside the frame
const HEAD_H = 40, FOOT_H = 28;  // header/footer band height
const INK = "#1e1e1e", SUB = "#868e96", LINE = "#ced4da";

ea.setView("active");
if (!ea.targetView) { new Notice("Open an Excalidraw drawing first"); return; }

const file = ea.targetView.file;
const fm = app.metadataCache.getFileCache(file)?.frontmatter ?? {};
const noteId = fm.id ?? "(no id)";
const title = fm.title ?? file.basename.replace(/\.excalidraw$/, "");
const statusLabel = { draft: "Draft", review: "In review", approved: "Approved" }[fm.status] ?? (fm.status || "");
const access = Array.isArray(fm.access) && fm.access.length ? fm.access.join(" / ") : "Owner only";
const updated = fm.updated ? String(fm.updated) : window.moment(file.stat.mtime).format("YYYY-MM-DD");

const action = await utils.suggester(
  ["Rebuild headers and footers", "Add a slide (A landscape) and rebuild"],
  ["refresh", "add"],
  "Slides (frames)"
);
if (!action) return;

const kvNo = (f) => parseInt(String(f.customData?.kvFrame ?? "").replace(/^F/, ""), 10) || 0;
const all = () => ea.getViewElements();
let frames = all().filter((e) => e.type === "frame" && !e.isDeleted);

// 1) Add a slide
if (action === "add") {
  const right = frames.reduce((m, f) => Math.max(m, f.x + f.width), -GAP);
  const top = frames.length ? Math.min(...frames.map((f) => f.y)) : 0;
  ea.clear();
  const no = frames.reduce((m, f) => Math.max(m, kvNo(f)), 0) + 1;
  const id = ea.addFrame(right + GAP, top, W, H, `Slide ${no}`);
  ea.addAppendUpdateCustomData(id, { kvFrame: `F${String(no).padStart(2, "0")}` });
  await ea.addElementsToView(false, false, true);
  frames = all().filter((e) => e.type === "frame" && !e.isDeleted);
}
if (!frames.length) { new Notice("No frames. Use \"Add a slide\" to create one"); return; }

// 2) Number frames that have no frame ID (existing numbers never change)
ea.clear();
let next = frames.reduce((m, f) => Math.max(m, kvNo(f)), 0);
const order = (a, b) => (Math.abs(a.y - b.y) > Math.min(a.height, b.height) / 2 ? a.y - b.y : a.x - b.x);
const unnumbered = frames.filter((f) => !kvNo(f)).sort(order);
if (unnumbered.length) {
  ea.copyViewElementsToEAforEditing(unnumbered);
  for (const f of unnumbered) {
    next += 1;
    ea.addAppendUpdateCustomData(f.id, { kvFrame: `F${String(next).padStart(2, "0")}` });
  }
  await ea.addElementsToView(false, false);
  ea.clear();
  frames = all().filter((e) => e.type === "frame" && !e.isDeleted);
}

// 3) Delete the previous header/footer
const old = all().filter((e) => e.customData?.kvHF);
if (old.length) ea.deleteViewElements(old);

// 4) Build header/footer per frame (page order = position order)
frames.sort(order);
const N = frames.length;
ea.clear();
const put = (frame, ids, kvFrame) => {
  for (const id of ids) {
    const el = ea.getElement(id);
    el.frameId = frame.id;
    el.locked = true;
    ea.addAppendUpdateCustomData(id, { kvHF: kvFrame });
  }
};
const textAt = (x, y, s, size, color, align = "left") => {
  ea.style.fontSize = size; ea.style.strokeColor = color; ea.style.fontFamily = 2;
  const w = ea.measureText(s).width;
  return ea.addText(align === "right" ? x - w : align === "center" ? x - w / 2 : x, y, s);
};
frames.forEach((f, i) => {
  const kv = f.customData?.kvFrame;
  const x0 = f.x + PAD, x1 = f.x + f.width - PAD;
  const yH = f.y + PAD / 2, yF = f.y + f.height - FOOT_H + 6;
  ea.style.strokeWidth = 1; ea.style.roughness = 0; ea.style.strokeStyle = "solid";
  const ids = [];
  // header
  ids.push(textAt(x0, yH + 4, f.name || "(untitled slide)", 20, INK));
  ids.push(textAt(x1, yH + 10, `#${kv}`, 12, SUB, "right"));
  ea.style.strokeColor = LINE;
  ids.push(ea.addLine([[x0, f.y + HEAD_H], [x1, f.y + HEAD_H]]));
  // footer
  ea.style.strokeColor = LINE;
  ids.push(ea.addLine([[x0, f.y + f.height - FOOT_H], [x1, f.y + f.height - FOOT_H]]));
  ids.push(textAt(x0, yF, `${noteId}#${kv}  ${title}`, 11, SUB));
  ids.push(textAt((x0 + x1) / 2 + 60, yF, `${statusLabel} | ${access} | Updated ${updated}`, 11, SUB, "center"));
  ids.push(textAt(x1, yF, `${i + 1} / ${N}`, 11, SUB, "right"));
  put(f, ids, kv);
});
await ea.addElementsToView(false, true, true);
new Notice(`Headers and footers added to ${N} slides`);
