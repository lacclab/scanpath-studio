// All geometry inside the assembled SVG is in PostScript points. A panel crop
// stays in its source SVG's coordinates, including the original plot margins.
const input = JSON.parse(document.getElementById("project-data").textContent);
const NS = "http://www.w3.org/2000/svg",
  XL = "http://www.w3.org/1999/xlink";
const PT = 72 / 25.4,
  presets = {
    "Paper column": 85,
    "Full-width paper": 170,
    "Full slide": 338.6666667,
    "Half slide": 169.3333333,
  };
const $ = (id) => document.getElementById(id);
const clone = structuredClone;
const svg = (tag, attrs = {}, label = null) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (label !== null) n.textContent = label;
  return n;
};
const finite = (x, lo, hi) => Number.isFinite(x) && x >= lo && x <= hi;
const clip = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const fmt = (x) => Number(x.toFixed(2)).toString();
const ptText = (x, y, t, size, attrs = {}) =>
  svg(
    "text",
    {
      x,
      y,
      "font-family": "Arial, sans-serif",
      "font-size": size,
      fill: "#263846",
      ...attrs,
    },
    t
  );
const plain = (s) =>
  String(s ?? "")
    .replace(/<br\s*\/?\s*>/gi, " ")
    .replace(/<[^>]*>/g, "");
const ctx = document.createElement("canvas").getContext("2d");
function textWidth(text, size) {
  ctx.font = size + "px Arial";
  return ctx.measureText(text).width;
}
function lines(text, w, size) {
  const out = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/).filter(Boolean)) {
      const next = line ? line + " " + word : word;
      if (line && textWidth(next, size) > w) {
        out.push(line);
        line = word;
      } else line = next;
      if (textWidth(line, size) > w) {
        let piece = "";
        for (const ch of line) {
          if (piece && textWidth(piece + ch, size) > w) {
            out.push(piece);
            piece = "";
          }
          piece += ch;
        }
        line = piece;
      }
    }
    out.push(line);
  }
  return out;
}
function check(doc) {
  if (
    doc?.schema !== "scanpath-studio/publication/1" ||
    !Array.isArray(doc.sources) ||
    !Array.isArray(doc.panels)
  )
    throw Error("Choose a Scanpath Studio publication recipe.");
  if (
    doc.heat &&
    (!Number.isFinite(doc.heat.min) ||
      !Number.isFinite(doc.heat.max) ||
      doc.heat.min < 0 ||
      doc.heat.max <= doc.heat.min ||
      !Array.isArray(doc.heat.scale) ||
      doc.heat.scale.length < 2)
  )
    throw Error("The saved heatmap scale has invalid limits or colors.");
  if (
    !finite(doc.width, 10, 1000) ||
    !finite(doc.dpi, 50, 1200) ||
    !finite(doc.minimum, 1, 72) ||
    !finite(doc.maxHeight, 10, 2000) ||
    !finite(doc.gap, 0, 100) ||
    !["row", "stack", "grid"].includes(doc.layout)
  )
    throw Error("Check the dimensions, resolution and panel layout.");
  const ids = new Set();
  for (const source of doc.sources) {
    if (
      typeof source.id !== "string" ||
      ids.has(source.id) ||
      !Array.isArray(source.figure?.data)
    )
      throw Error("Invalid or duplicate panel source.");
    ids.add(source.id);
  }
  for (const p of doc.panels) {
    if (
      !ids.has(p.source) ||
      !Array.isArray(p.labels) ||
      (p.crop && !validBox(p.crop))
    )
      throw Error("The recipe has an invalid panel or crop.");
    for (const l of p.labels)
      if (
        ![l.x, l.y, l.dx, l.dy].every(Number.isFinite) ||
        typeof l.text !== "string"
      )
        throw Error("A pinned label has invalid coordinates.");
  }
  return doc;
}
const validBox = (b) =>
  Array.isArray(b) &&
  b.length === 4 &&
  b.every(Number.isFinite) &&
  b[2] > 0 &&
  b[3] > 0;
const byId = (id) => doc.sources.find((s) => s.id === id);
let doc = check(input.project),
  active = 0,
  currentSheet = null,
  cells = [],
  warnings = [],
  revision = 0;
const cache = new Map();
function clock(source) {
  return source?.figure.layout?.meta?.scanpath_frame_times_ms || [];
}
function printable(source, p) {
  const f = source.figure,
    lo = clone(f.layout || {}),
    times = clock(source);
  const data = clone(f.data);
  if (f.frames?.length) {
    const index = clip(Math.trunc(p.frame || 0), 0, f.frames.length - 1);
    const frame = lo.meta?._scanpath_terminal_frame
      ? frameAtTime(
          f.frames[0],
          lo.meta.scanpath_fixation_steps,
          times[clip(p.frame || 0, 0, times.length - 1)] || 0,
          "poster"
        )
      : f.frames[index];
    for (const [i, change] of frame.data.entries()) {
      const k = frame.traces?.[i] ?? i;
      data[k] = {
        ...data[k],
        ...clone(change),
        marker: { ...data[k].marker, ...change.marker },
      };
    }
    const trim = source.transport || 0;
    lo.height = Math.max(10, (lo.height || 600) - trim);
    lo.margin = { ...lo.margin, t: Math.max(0, (lo.margin?.t || 0) - trim) };
    lo.updatemenus = [];
    lo.sliders = [];
  }
  if (p.legendNames)
    for (const tr of data)
      if (Object.hasOwn(p.legendNames, tr.name))
        tr.name = p.legendNames[tr.name];
  if (p.legendStack)
    lo.legend = {
      ...lo.legend,
      orientation: "v",
      x: 1,
      xanchor: "right",
      y: 1,
      yanchor: "top",
    };
  const hidden = lo.meta?.publication_hidden_heatmap;
  if (hidden && doc.heat) {
    data.push(clone(hidden));
  }
  const heat = data.find((t) => t.meta?.publication_heatmap);
  if (
    doc.heat &&
    heatInfo(source) &&
    heat?.meta.publication_heatmap.measure === doc.heat.measure &&
    heat.meta.publication_heatmap.norm === doc.heat.norm
  ) {
    const spec = heat.meta.publication_heatmap,
      scale = doc.heat.scale,
      transform = (x) => (spec.norm === "Log" ? Math.log1p(x) : x);
    const low = transform(doc.heat.min),
      high = transform(doc.heat.max);
    const shapes = (lo.shapes || []).filter((sh) => sh.name === spec.tag);
    if (shapes.length === spec.values.length) {
      for (const [i, sh] of shapes.entries()) {
        sh.fillcolor = sampleColor(
          scale,
          clip((transform(spec.values[i]) - low) / (high - low), 0, 1)
        );
        if (doc.heat.opacity != null) sh.opacity = doc.heat.opacity;
      }
      const raw = [
        doc.heat.min,
        (doc.heat.min + doc.heat.max) / 2,
        doc.heat.max,
      ];
      heat.marker = {
        ...heat.marker,
        cmin: low,
        cmax: high,
        colorscale: scale,
        showscale: !doc.heat.shared,
        colorbar: {
          ...heat.marker.colorbar,
          title: { text: spec.measure },
          tickvals: raw.map(transform),
          ticktext: raw.map(fmt),
        },
      };
    }
  }
  for (let i = 0; i < data.length; i++) data[i].uid = "pub" + i;
  return {
    data,
    layout: {
      ...lo,
      width: Math.round(lo.width || 900),
      height: Math.round(lo.height || 520),
      autosize: false,
    },
  };
}
function sampleColor(scale, x) {
  const index = scale.findIndex((v) => v[0] >= x),
    b = scale[index < 0 ? scale.length - 1 : index],
    a = scale[Math.max(0, (index < 0 ? scale.length - 1 : index) - 1)];
  function rgb(css) {
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    return ctx.getImageData(0, 0, 1, 1).data;
  }
  const c = rgb(a[1]),
    d = rgb(b[1]),
    f = b[0] > a[0] ? (x - a[0]) / (b[0] - a[0]) : 0;
  return (
    "rgb(" +
    [0, 1, 2].map((i) => Math.round(c[i] + (d[i] - c[i]) * f)).join(",") +
    ")"
  );
}
function heatInfo(s) {
  if (!s) return null;
  const bars = s.figure.data.filter((t) => t.meta?.publication_heatmap),
    bar = bars[0] || s.figure.layout?.meta?.publication_hidden_heatmap;
  if (!bar || bars.length > 1) return null;
  const info = bar.meta.publication_heatmap;
  return (s.figure.layout?.shapes || []).filter((sh) => sh.name === info.tag)
    .length === info.values.length
    ? bar
    : null;
}
function cropBox(p, art) {
  const [x, y, w, h] = p.crop || [0, 0, art.w, art.h];
  const l = clip(x, 0, art.w - 1),
    t = clip(y, 0, art.h - 1);
  return [
    l,
    t,
    Math.max(1, Math.min(w, art.w - l)),
    Math.max(1, Math.min(h, art.h - t)),
  ];
}
async function capture(source, p) {
  const key = JSON.stringify([
    source.id,
    p.frame,
    p.legendStack,
    p.legendNames,
    doc.heat,
  ]);
  if (cache.has(key)) return cache.get(key);
  const { data, layout } = printable(source, p),
    gd = document.createElement("div");
  $("drawing").append(gd);
  try {
    await Plotly.newPlot(gd, data, layout, {
      staticPlot: true,
      displayModeBar: false,
      responsive: false,
    });
    const uri = await Plotly.toImage(gd, {
      format: "svg",
      width: layout.width,
      height: layout.height,
    });
    const xml = uri.includes(";base64,")
      ? atob(uri.split(",")[1])
      : decodeURIComponent(uri.slice(uri.indexOf(",") + 1));
    const root = new DOMParser().parseFromString(
      xml,
      "image/svg+xml"
    ).documentElement;
    if (root.localName !== "svg")
      throw Error("The figure renderer did not return SVG.");
    // Only Plotly-generated artwork enters the proof DOM. Imported figure text
    // is rendered by Plotly first. Remove links from the static illustration.
    root
      .querySelectorAll("script,foreignObject,style,iframe")
      .forEach((e) => e.remove());
    root.querySelectorAll("*").forEach((e) => {
      for (const attr of [...e.attributes]) {
        if (
          attr.name.toLowerCase().startsWith("on") ||
          (attr.localName === "href" &&
            !attr.value.startsWith("#") &&
            !/^data:image\/(png|jpeg|webp|gif);base64,/i.test(attr.value))
        )
          e.removeAttributeNode(attr);
      }
    });
    const words = [],
      events = [],
      texts = [],
      wordTraces = new Map();
    for (const [i, tr] of gd._fullData.entries()) {
      if (tr.visible === false || tr.visible === "legendonly") continue;
      const xa = gd._fullLayout[(tr.xaxis || "x").replace("x", "xaxis")],
        ya = gd._fullLayout[(tr.yaxis || "y").replace("y", "yaxis")];
      if (!xa || !ya) continue;
      const group = root.querySelector(".tracepub" + i);
      for (const pt of gd.calcdata[i] || []) {
        const j = pt.i;
        if (
          !Number.isInteger(j) ||
          !Number.isFinite(pt.x) ||
          !Number.isFinite(pt.y)
        )
          continue;
        const x = xa._offset + xa.c2p(pt.x),
          y = ya._offset + ya.c2p(pt.y);
        if (!Number.isFinite(x + y)) continue;
        if (tr.name === "words") {
          const name = plain(tr.text?.[j]);
          if (name) {
            const word = { x, y, text: name, axis: tr.xaxis + tr.yaxis };
            words.push(word);
            if (!wordTraces.has(i)) wordTraces.set(i, []);
            wordTraces.get(i).push(word);
          }
        } else if (
          source.kind !== "chart" &&
          (tr.meta?.publication_order || tr.mode?.includes("markers"))
        ) {
          const detail = plain(tr.customdata?.[j]),
            match = detail.match(/\bFixation\s+(\d+)\b/i);
          const order =
            tr.meta?.publication_order?.[j] ??
            match?.[1] ??
            (/^\d+$/.test(tr.text?.[j]) ? tr.text[j] : null);
          const onset = tr.meta?.publication_onset?.[j];
          if (order != null)
            events.push({
              x,
              y,
              index: Number(order),
              onset,
              recorded: tr.meta?.publication_recorded_clock,
              axis: [
                tr.xaxis + tr.yaxis,
                tr.meta?.publication_reading || tr.legendgroup,
              ]
                .filter(Boolean)
                .join(" · "),
              detail,
            });
        }
      }
      if (
        group &&
        tr.name !== "words" &&
        source.kind !== "chart" &&
        (tr.meta?.publication_order ||
          tr.mode?.includes("markers") ||
          tr.name === "Fixation index") &&
        tr.name !== "Raw gaze"
      )
        group.setAttribute("data-events", "1");
      if (
        group &&
        source.kind !== "chart" &&
        (tr.mode === "lines" ||
          /saccade|fixation sequence/i.test(tr.name || ""))
      )
        group.setAttribute("data-sequence", "1");
    }
    // getBBox uses the actual rendered typeface, including legend and axis text.
    const measure = document.importNode(root, true);
    $("drawing").append(measure);
    try {
      const matrix = measure.getCTM().inverse(),
        wordByNode = new Map();
      for (const [trace, rows] of wordTraces) {
        const wordNodes = measure.querySelectorAll(
          ".tracepub" + trace + " .textpoint text"
        );
        wordNodes.forEach((n, index) => {
          if (rows[index]) wordByNode.set(n, rows[index]);
        });
      }
      for (const t of measure.querySelectorAll("text")) {
        if (!t.textContent.trim()) continue;
        const b = t.getBBox(),
          m = matrix.multiply(t.getCTM()),
          pt = new DOMPoint(
            b.x + b.width / 2,
            b.y + b.height / 2
          ).matrixTransform(m);
        const word = wordByNode.get(t);
        if (word) {
          const corners = [
            [b.x, b.y],
            [b.x + b.width, b.y],
            [b.x, b.y + b.height],
            [b.x + b.width, b.y + b.height],
          ].map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
          word.bounds = [
            Math.min(...corners.map((q) => q.x)),
            Math.min(...corners.map((q) => q.y)),
            Math.max(...corners.map((q) => q.x)),
            Math.max(...corners.map((q) => q.y)),
          ];
        }
        if (b.width && b.height)
          texts.push({
            x: pt.x,
            y: pt.y,
            w: b.width * Math.hypot(m.a, m.b),
            h: b.height * Math.hypot(m.c, m.d),
            size:
              parseFloat(getComputedStyle(t).fontSize) * Math.hypot(m.a, m.b),
            word: !!word,
            legend: !!t.closest(".legend,.legend2,.legend3"),
            annotation: !!t.closest(".annotation"),
            event: !!t.closest("[data-events]"),
          });
      }
    } finally {
      measure.remove();
    }
    const a = { root, w: layout.width, h: layout.height, words, events, texts };
    if (cache.size >= 12) cache.delete(cache.keys().next().value);
    cache.set(key, a);
    return a;
  } finally {
    Plotly.purge(gd);
    gd.remove();
  }
}
function scoped(art, id, isolate) {
  const root = art.root.cloneNode(true),
    ids = new Map();
  if (isolate)
    root
      .querySelectorAll("[data-events],[data-sequence]")
      .forEach((n) => n.remove());
  for (const n of root.querySelectorAll("[id]")) {
    ids.set(n.id, id + n.id);
    n.id = id + n.id;
  }
  for (const n of root.querySelectorAll("*"))
    for (const a of [...n.attributes]) {
      let v = a.value.replace(/url\(#([^)]+)\)/g, (m, k) =>
        ids.has(k) ? "url(#" + ids.get(k) + ")" : m
      );
      if (a.localName === "href" && v.startsWith("#") && ids.has(v.slice(1)))
        v = "#" + ids.get(v.slice(1));
      if (v !== a.value) n.setAttributeNS(a.namespaceURI, a.name, v);
    }
  return root;
}
function draft(alt = false) {
  const result = doc.panels
    .map((p, i) => {
      const s = byId(p.source),
        layout = s.figure.layout || {},
        info = heatInfo(s)?.meta.publication_heatmap;
      let desc = s.description || s.title;
      if (alt && p.title && p.title !== desc) desc = p.title + ". " + desc;
      if (s.kind === "chart") {
        const axes = [layout.xaxis, layout.yaxis]
          .map((a) => plain(a?.title?.text))
          .filter(Boolean);
        if (axes.length) desc += ". Axes: " + axes.join(" and ");
      }
      if (info) {
        const range =
          doc.heat?.measure === info.measure && doc.heat.norm === info.norm
            ? [doc.heat.min, doc.heat.max]
            : heatInfo(s).meta.word_heatmap_range;
        desc +=
          ". " +
          info.measure +
          " (" +
          range.map(fmt).join("–") +
          ", " +
          info.norm.toLowerCase() +
          " scale)";
      }
      const ls = p.labels.map((l) => l.text).join(", ");
      return (
        (doc.panels.length > 1 ? letter(i) + ". " : "") +
        desc +
        (p.crop ? " (detail)" : "") +
        (ls ? ". " + ls : "") +
        (clock(s).length
          ? " · " + fmt((clock(s)[p.frame || 0] || 0) / 1000) + " s"
          : "")
      );
    })
    .join(alt ? " " : "\n");
  const refs = [
    ...new Set(doc.panels.flatMap((p) => byId(p.source).references || [])),
  ];
  return result + (!alt && refs.length ? "\n" + refs.join(" ") : "");
}
const letter = (i) => String.fromCharCode(65 + i);
function build(arts) {
  const W = doc.width * PT,
    slide = ["Full slide", "Half slide"].includes(doc.destination),
    gap = doc.gap,
    cols =
      doc.layout === "row"
        ? arts.length
        : doc.layout === "grid"
        ? Math.min(2, arts.length)
        : 1;
  const pad = Math.min(10, W * 0.025),
    cw = (W - 2 * pad - gap * (cols - 1)) / cols,
    size = slide ? 18 : 9,
    bodyW = W - pad * 2;
  if (cw < 10)
    throw Error("Increase the figure width or reduce the gap between panels.");
  const caption = doc.caption ?? draft(),
    cl =
      doc.captionPlacement === "Wrap"
        ? lines(caption, bodyW, size)
        : doc.captionPlacement === "Single line"
        ? [caption.replaceAll("\n", " ")]
        : [];
  const disclosure = [
    ...new Set(
      doc.panels.flatMap((p) =>
        (byId(p.source).figure.layout?.annotations || [])
          .filter((a) => a.name === "illustration_label")
          .map((a) => plain(a.text))
      )
    ),
  ].join(" · ");
  const credit = disclosure ? lines(disclosure, bodyW, size) : [];
  const hasHeat =
    doc.heat?.shared &&
    doc.panels.some(
      (p) =>
        heatInfo(byId(p.source))?.meta.publication_heatmap.measure ===
          doc.heat.measure &&
        heatInfo(byId(p.source))?.meta.publication_heatmap.norm ===
          doc.heat.norm
    );
  const footer =
    (cl.length + credit.length) * size * 1.32 + (hasHeat ? size * 4 : 0);
  const parts = arts.map((a, i) => {
    const panel = doc.panels[i],
      box = cropBox(panel, a),
      over = panel.overview && panel.crop;
    const headings =
      doc.panels.length > 1 || doc.headings
        ? lines(
            (doc.panels.length > 1 ? letter(i) + "  " : "") + panel.title,
            cw,
            size
          )
        : [];
    return {
      box,
      over,
      headings,
      heading: headings.length * size * 1.3,
      natural: (cw * box[3]) / box[2] + (over ? size * 6 : 0),
    };
  });
  const rows = Math.ceil(arts.length / cols),
    rh = [],
    hh = [];
  for (let r = 0; r < rows; r++) {
    const row = parts.slice(r * cols, (r + 1) * cols);
    rh.push(Math.max(...row.map((p) => p.natural)));
    hh.push(Math.max(...row.map((p) => p.heading)));
  }
  const H = slide
    ? 190.5 * PT
    : pad * 2 +
      footer +
      rh.reduce((a, b) => a + b, 0) +
      hh.reduce((a, b) => a + b, 0) +
      gap * (rows - 1);
  const room =
    (H - 2 * pad - footer - hh.reduce((a, b) => a + b, 0) - gap * (rows - 1)) /
    rows;
  if (slide && room < 10)
    throw Error(
      "The caption and headings leave too little room for the artwork. Shorten them or keep the caption separate."
    );
  if (!finite(H, 1, 20000))
    throw Error("Choose a wider crop or reduce the figure width.");
  const root = svg("svg", {
    xmlns: NS,
    width: doc.width + "mm",
    height: fmt(H / PT) + "mm",
    viewBox: "0 0 " + W + " " + H,
    role: "img",
  });
  root.append(
    svg("title", {}, doc.name),
    svg("desc", {}, doc.alt ?? draft(true)),
    svg("metadata", {}, JSON.stringify(doc.citation)),
    svg("rect", { width: W, height: H, fill: "white" })
  );
  let y = pad,
    min = Infinity,
    issues = [],
    positions = [],
    lettering = {};
  if (doc.gray) {
    const defs = svg("defs"),
      filter = svg("filter", { id: "publication-gray" });
    filter.append(svg("feColorMatrix", { type: "saturate", values: "0" }));
    defs.append(filter);
    root.append(defs);
  }
  for (let r = 0; r < rows; r++) {
    const height = slide ? room : rh[r];
    for (let col = 0; col < cols; col++) {
      const i = r * cols + col;
      if (i >= arts.length) break;
      const art = arts[i],
        p = doc.panels[i],
        { box, over, headings } = parts[i],
        x = pad + col * (cw + gap);
      const oh = over ? Math.min(size * 6, height * 0.28) : 0,
        k = Math.min(cw / box[2], (height - oh) / box[3]),
        w = box[2] * k,
        h = box[3] * k,
        ox = x + (cw - w) / 2,
        oy = y + hh[r] + oh + (height - oh - h) / 2;
      if (headings.length) {
        min = Math.min(min, size);
        headings.forEach((t, j) =>
          root.append(
            ptText(x, y + (j + 1) * size * 1.22, t, size, {
              "font-weight": "bold",
            })
          )
        );
      }
      if (over) {
        const z = Math.min(cw / art.w, (oh * 0.93) / art.h),
          xx = x + (cw - art.w * z) / 2,
          yy = y + hh[r];
        const ov = scoped(art, "ov" + i + "-", false);
        setBox(ov, xx, yy, art.w * z, art.h * z, [0, 0, art.w, art.h]);
        root.append(
          ov,
          svg("rect", {
            x: xx + box[0] * z,
            y: yy + box[1] * z,
            width: box[2] * z,
            height: box[3] * z,
            fill: "none",
            stroke: "#087481",
            "stroke-width": 1,
          })
        );
      }
      const cropped = svg("svg");
      setBox(cropped, ox, oy, w, h, box);
      const artRoot = scoped(art, "p" + i + "-", p.isolate);
      artRoot.setAttribute("width", art.w);
      artRoot.setAttribute("height", art.h);
      cropped.append(artRoot);
      root.append(cropped);
      for (const t of art.texts) {
        if (p.isolate && t.event) continue;
        const visible =
          t.x >= box[0] &&
          t.x <= box[0] + box[2] &&
          t.y >= box[1] &&
          t.y <= box[1] + box[3];
        if (visible && t.size > 0) {
          const size = t.size * k;
          min = Math.min(min, size);
          const category = t.word
            ? "Words"
            : t.event
            ? "Fixation labels"
            : t.legend
            ? "Legend"
            : null;
          if (category)
            lettering[category] = Math.min(
              lettering[category] ?? Infinity,
              size
            );
        }
        if (
          (t.legend || t.annotation) &&
          t.x + t.w / 2 > box[0] &&
          t.x - t.w / 2 < box[0] + box[2] &&
          t.y + t.h / 2 > box[1] &&
          t.y - t.h / 2 < box[1] + box[3] &&
          (t.x - t.w / 2 < box[0] - 1 ||
            t.x + t.w / 2 > box[0] + box[2] + 1 ||
            t.y - t.h / 2 < box[1] - 1 ||
            t.y + t.h / 2 > box[1] + box[3] + 1)
        )
          issues.push(
            "A " +
              (t.legend ? "legend" : "figure annotation") +
              (doc.panels.length === 1
                ? " is clipped at the figure edge."
                : " is clipped in panel " + letter(i) + ".")
          );
      }
      const map = (a, b) => [ox + (a - box[0]) * k, oy + (b - box[1]) * k];
      for (const [j, l] of p.labels.entries()) {
        if (
          l.x < box[0] ||
          l.y < box[1] ||
          l.x > box[0] + box[2] ||
          l.y > box[1] + box[3]
        )
          continue;
        const [ex, ey] = map(l.x, l.y),
          lx = ex + l.dx,
          ly = ey + l.dy,
          fs = l.size || size;
        if (l.segment) {
          const [a, b, c, d] = l.segment,
            [ax, ay] = map(a, b),
            [bx, by] = map(c, d);
          cropped.append(
            svg("line", {
              x1: a,
              y1: b,
              x2: c,
              y2: d,
              stroke: "#086571",
              "stroke-width": 1 / k,
            })
          );
          const angle = Math.atan2(by - ay, bx - ax);
          cropped.append(
            svg("path", {
              d: "M 0 0 L -5 -2 L -5 2 Z",
              fill: "#086571",
              transform:
                "translate(" +
                c +
                " " +
                d +
                ") rotate(" +
                (angle * 180) / Math.PI +
                ") scale(" +
                1 / k +
                ")",
            })
          );
        }
        root.append(
          svg("line", {
            x1: ex,
            y1: ey,
            x2: lx,
            y2: ly - fs * 0.25,
            stroke: "#456372",
            "stroke-width": 0.6,
          }),
          svg("circle", { cx: ex, cy: ey, r: 1.9, fill: "#086571" })
        );
        const text = ptText(lx, ly, l.text, fs, {
          "text-anchor": "middle",
          stroke: "white",
          "stroke-width": 2.5,
          "paint-order": "stroke",
          class: "label-handle",
          "data-label": i + "," + j,
        });
        root.append(text);
        if (
          lx - textWidth(l.text, fs) / 2 < x ||
          lx + textWidth(l.text, fs) / 2 > x + cw ||
          ly - fs < y ||
          ly > oy + h
        )
          issues.push(
            doc.panels.length === 1
              ? "Move the pinned label inside the figure."
              : "Move the pinned label inside panel " + letter(i) + "."
          );
        min = Math.min(min, fs);
      }
      positions[i] = { x: ox, y: oy, w, h, k, box, art };
    }
    y += hh[r] + height + gap;
  }
  y -= gap;
  if (hasHeat) {
    const s = doc.heat,
      x = pad,
      barW = bodyW * 0.48;
    root.append(
      ptText(
        x,
        y + size,
        s.measure + (s.norm === "Log" ? " (log scale)" : ""),
        size
      )
    );
    for (let j = 0; j < 48; j++)
      root.append(
        svg("rect", {
          x: x + (barW * j) / 48,
          y: y + size * 1.4,
          width: barW / 48 + 0.05,
          height: size * 0.65,
          fill: sampleColor(s.scale, j / 47),
          opacity: s.opacity ?? 1,
        })
      );
    root.append(
      ptText(x, y + size * 3.2, fmt(s.min), size),
      ptText(x + barW, y + size * 3.2, fmt(s.max), size, {
        "text-anchor": "end",
      })
    );
    y += size * 4;
  }
  for (const line of [...credit, ...cl]) {
    y += size * 1.32;
    root.append(ptText(pad, y - size * 0.12, line, size));
    min = Math.min(min, size);
    if (textWidth(line, size) > bodyW + 0.1)
      issues.push("The caption extends past the figure edge.");
  }
  if (Number.isFinite(min) && min < doc.minimum - 0.01)
    issues.push(
      "Smallest lettering is " +
        fmt(min) +
        " pt. Your minimum is " +
        doc.minimum +
        " pt."
    );
  if (H / PT > doc.maxHeight + 0.1)
    issues.push(
      "The figure exceeds the height limit by " +
        fmt(H / PT - doc.maxHeight) +
        " mm."
    );
  if (doc.gray) {
    const group = svg("g", { filter: "url(#publication-gray)" });
    for (const n of [...root.children])
      if (!["metadata", "defs", "title", "desc"].includes(n.localName))
        group.append(n);
    root.append(group);
  }
  return {
    root,
    W,
    H,
    positions,
    min,
    lettering,
    issues: [...new Set(issues)],
  };
}
function setBox(n, x, y, w, h, box) {
  for (const [key, value] of Object.entries({
    x,
    y,
    width: w,
    height: h,
    viewBox: box.join(" "),
    overflow: "hidden",
  }))
    n.setAttribute(key, value);
}
async function artwork() {
  if (!doc.panels.length) throw Error("Open a saved figure to export it.");
  const arts = [];
  for (const p of doc.panels) arts.push(await capture(byId(p.source), p));
  return build(arts);
}
