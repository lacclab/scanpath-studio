const tabs = [
  "Proof & export",
  "Region & events",
  "Panel layout",
  "Replay",
  "Caption & save",
];
let tab = tabs[0],
  actual = false,
  cropping = false,
  playing = false,
  chosenSource = null,
  queued = Promise.resolve();
const node = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
const note = (text) => node("p", text, "note");
function message(t) {
  $("message").textContent = t;
}
function button(label, action, primary = false) {
  const n = node("button", label, primary ? "primary" : "");
  n.type = "button";
  n.onclick = async () => {
    try {
      await action();
    } catch (e) {
      message(e.message || String(e));
    }
  };
  return n;
}
function field(name, el) {
  el.setAttribute("aria-label", name);
  const l = node("label", name);
  l.append(el);
  return l;
}
function choice(name, items, value, change) {
  const el = node("select");
  for (const item of items) {
    const [v, label] = Array.isArray(item) ? item : [item, item];
    el.add(new Option(label, String(v)));
  }
  el.value = String(value);
  el.onchange = () => change(el.value);
  return field(name, el);
}
function entry(name, value, change, options = {}) {
  const el = node(options.multi ? "textarea" : "input");
  if (options.multi) el.rows = options.rows || 3;
  else el.type = options.num ? "number" : "text";
  if (options.num) {
    el.min = options.min;
    el.max = options.max;
    el.step = options.step || "any";
  }
  el.value = value ?? "";
  el.onchange = () => {
    if (!el.reportValidity()) return;
    change(options.num ? Number(el.value) : el.value);
  };
  return field(name, el);
}
const num = (name, v, min, max, change) =>
  entry(name, v, change, { num: true, min, max });
const row = (...children) => {
  const n = node("div", null, "row");
  n.append(...children);
  return n;
};
function section(title, ...children) {
  const n = node("section");
  n.append(node("h2", title), ...children.filter(Boolean));
  $("controls").append(n);
}
const pNow = () => doc.panels[active],
  sNow = () => byId(pNow()?.source),
  artNow = () => cells[active]?.art;
const set = (k, v) => {
    doc[k] = v;
    update();
  },
  panelSet = (k, v) => {
    pNow()[k] = v;
    update();
  };
const optPanels = () =>
  doc.panels.map((p, i) => [i, letter(i) + " · " + p.title]);
const panelChoice = () =>
  choice("Edit panel", optPanels(), active, (v) => {
    active = +v;
    update();
  });
function snapshot() {
  const { currentSource, comparison, ...project } = doc;
  return {
    ...project,
    sources: doc.sources.filter((s) =>
      doc.panels.some((p) => p.source === s.id)
    ),
  };
}
const dbName = "scanpath-studio-figures:" + location.pathname;
function storage(action, store = "figures") {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore("figures");
      req.result.createObjectStore("drafts");
    };
    req.onerror = () =>
      reject(
        Error(
          "Device storage is unavailable. Download a recipe to keep your figure."
        )
      );
    req.onsuccess = () => {
      const db = req.result,
        tx = db.transaction(store, "readwrite");
      let out;
      try {
        out = action(tx.objectStore(store));
      } catch (e) {
        db.close();
        reject(e);
        return;
      }
      tx.oncomplete = () => {
        db.close();
        resolve(out.result);
      };
      tx.onerror = () => {
        db.close();
        reject(tx.error);
      };
    };
  });
}
function draftStore() {
  if (!input.session || window === window.parent) return null;
  try {
    return (window.parent.__scanpathPublicationDrafts ??= new Map());
  } catch {
    return null;
  }
}
function persist() {
  draftStore()?.set(input.session, {
    importId: input.importId,
    project: snapshot(),
  });
}
function merged(item) {
  check(item);
  const sources = new Map(
    [...doc.sources, ...item.sources].map((s) => [s.id, s])
  );
  doc = { ...item, sources: [...sources.values()] };
  active = 0;
  chosenSource = null;
  cache.clear();
}
function update() {
  playing = false;
  persist();
  return redraw();
}
function redraw() {
  const rev = ++revision;
  const render = async () => {
    if (rev !== revision) return;
    try {
      const art = await artwork();
      if (rev !== revision) return;
      cells = art.positions;
      currentSheet = art;
      $("sheet").replaceChildren(art.root);
      $("sheet").style.width = actual
        ? fmt((doc.width * 96) / 25.4) + "px"
        : "min(100%, " +
          Math.max(80, Math.round((435 * art.W) / art.H)) +
          "px)";
      $("figure-name").textContent = doc.name;
      $("zoom").textContent = actual ? "Fit to window" : "100%";
      $("metrics").textContent =
        fmt(doc.width) +
        " × " +
        fmt(art.H / PT) +
        " mm" +
        (Number.isFinite(art.min)
          ? "   ·   Smallest lettering " + fmt(art.min) + " pt"
          : "");
      $("type-sizes").textContent = Object.entries(art.lettering)
        .map(([name, points]) => name + " " + fmt(points) + " pt")
        .join("   ·   ");
      $("issues").replaceChildren();
      for (const issue of art.issues) {
        const n = node("div", issue);
        if (issue.startsWith("The caption"))
          n.append(
            button("Wrap caption", () => set("captionPlacement", "Wrap")),
            button("Move to manuscript", () =>
              set("captionPlacement", "Manuscript")
            )
          );
        if (issue.startsWith("Move the pinned label"))
          n.append(
            button("Fit labels inside panels", () => {
              doc.panels.forEach((panel, i) =>
                panel.labels.forEach((label) => fitLabel(label, cells[i]))
              );
              update();
            })
          );
        if (issue.includes("legend"))
          n.append(
            button("Edit legend", () => {
              tab = "Panel layout";
              paintControls();
            })
          );
        if (issue.startsWith("Smallest")) {
          if (
            input.session &&
            input.project.comparison &&
            pNow()?.source === input.project.currentSource
          )
            n.append(
              button("Stack and crop readings", () =>
                window.parent.postMessage(
                  {
                    key: input.session,
                    action: "stack",
                    value: { id: pNow().source, index: active },
                  },
                  "*"
                )
              )
            );
          if (doc.panels.length > 1 && doc.layout !== "stack")
            n.append(button("Stack panels", () => set("layout", "stack")));
          n.append(
            button("Crop detail", () => {
              tab = "Region & events";
              cropping = true;
              paintControls();
            })
          );
        }
        $("issues").append(n);
      }
      message("");
      paintControls();
    } catch (e) {
      message(e.message || String(e));
      currentSheet = null;
      cells = [];
      $("sheet").replaceChildren();
      $("metrics").textContent = "";
      $("type-sizes").textContent = "";
      $("issues").replaceChildren();
      paintControls();
    }
  };
  queued = queued.catch(() => {}).then(render);
  return queued;
}
function paintControls() {
  $("controls").replaceChildren();
  const nav = document.querySelector("nav");
  nav.replaceChildren();
  for (const label of tabs) {
    const b = button(label, () => {
      playing = false;
      tab = label;
      cropping = false;
      paintControls();
    });
    b.setAttribute("aria-pressed", String(label === tab));
    nav.append(b);
  }
  $("sheet").classList.toggle("cropping", cropping);
  if (tab === "Saved figures") {
    savedControls();
    return;
  }
  const p = pNow(),
    s = sNow();
  if (!p || !s) {
    section("Sources", ...sourceControls());
    return;
  }
  if (tab === tabs[0]) {
    section(
      "Destination",
      choice(
        "Place figure in",
        [...Object.keys(presets), "Custom paper"],
        doc.destination,
        (v) => {
          doc.destination = v;
          if (presets[v]) doc.width = presets[v];
          doc.minimum = v.includes("slide") ? 18 : 6;
          doc.maxHeight = v.includes("slide") ? 190.5 : 230;
          update();
        }
      ),
      row(
        num("Width (mm)", doc.width, 10, 1000, (v) => {
          doc.destination = "Custom paper";
          set("width", v);
        }),
        num("Height limit (mm)", doc.maxHeight, 10, 2000, (v) =>
          set("maxHeight", v)
        )
      ),
      num("Minimum lettering (pt)", doc.minimum, 1, 72, (v) =>
        set("minimum", v)
      ),
      choice(
        "Palette",
        ["Color", "Grayscale"],
        doc.gray ? "Grayscale" : "Color",
        (v) => set("gray", v === "Grayscale")
      )
    );
    section(
      "Export",
      choice(
        "Caption placement",
        ["Manuscript", "Wrap", "Single line"],
        doc.captionPlacement,
        (v) => set("captionPlacement", v)
      ),
      num("Raster resolution (dpi)", doc.dpi, 50, 1200, (v) =>
        set("dpi", Math.round(v))
      ),
      row(
        ...["SVG", "PDF", "PNG", "TIFF"].map((f) =>
          button(f, () => downloadArt(f.toLowerCase()))
        )
      ),
      input.session &&
        button("Apply size to export bundle", () =>
          window.parent.postMessage(
            {
              key: input.session,
              action: "batch",
              value: { width: doc.width, dpi: doc.dpi },
            },
            "*"
          )
        ),
      note(
        "SVG and PDF keep vector artwork. PNG and TIFF record the selected print density."
      )
    );
  } else if (tab === tabs[1]) regionControls(p);
  else if (tab === tabs[2]) layoutControls(p);
  else if (tab === tabs[3]) replayControls(p, s);
  else {
    section(
      "Figure text",
      entry(
        "Manuscript caption",
        doc.caption ?? draft(),
        (v) => set("caption", v),
        { multi: true }
      ),
      entry("Alternative text", doc.alt ?? draft(true), (v) => set("alt", v), {
        multi: true,
      }),
      button("Regenerate from current panels", () => {
        doc.caption = null;
        set("alt", null);
      }),
      button("Download both as text", () =>
        file(
          "txt",
          [
            doc.caption ?? draft(),
            "",
            doc.alt ?? draft(true),
            "",
            doc.citation.Comment,
          ].join("\n"),
          "text/plain"
        )
      )
    );
    section(
      "Save figure",
      entry("Figure name", doc.name, (v) =>
        set("name", v.trim() || "Untitled figure")
      ),
      button("Save named figure on this device", saveNamed, true),
      button("Download figure recipe", () =>
        file("json", JSON.stringify(snapshot()), "application/json")
      ),
      input.session &&
        button("Download offline editor", () =>
          window.parent.postMessage(
            { key: input.session, action: "html", value: snapshot() },
            "*"
          )
        ),
      s.settings &&
        button("Download source settings", () =>
          file("settings.json", JSON.stringify(s.settings), "application/json")
        ),
      note(
        "Recipes include plotted data, tooltip fields and embedded stimulus images. Open the file to edit or reproduce the figure."
      )
    );
  }
}
function sourceControls() {
  const id = chosenSource || doc.sources.at(-1)?.id;
  const arr = [
    choice(
      "Available source",
      doc.sources.map((s) => [s.id, s.title]),
      id,
      (v) => {
        chosenSource = v;
        paintControls();
      }
    ),
  ];
  if (id)
    arr.push(
      button("Add as panel", () => {
        const s = byId(id);
        doc.panels.push({ source: id, title: s.title, labels: [] });
        active = doc.panels.length - 1;
        update();
      })
    );
  if (id && pNow() && id !== pNow().source) {
    arr.push(
      note(
        "Replace " +
          pNow().title +
          " with " +
          byId(id).title +
          ". This clears pins belonging to the previous reading."
      ),
      choice(
        "Edited caption and alternative text",
        ["Keep wording", "Regenerate on replacement"],
        pNow().regenerate ? "Regenerate on replacement" : "Keep wording",
        (v) => {
          pNow().regenerate = v === "Regenerate on replacement";
          persist();
        }
      )
    );
  }
  if (id && pNow() && id !== pNow().source)
    arr.push(
      button("Replace selected panel", () => {
        const s = byId(id),
          old = pNow(),
          a = sNow().figure.layout,
          b = s.figure.layout;
        // Geometry from another canvas must be chosen again. Event labels belong to the old reading.
        const same =
          a?.width === b?.width &&
          a?.height === b?.height &&
          JSON.stringify(a?.xaxis?.range) === JSON.stringify(b?.xaxis?.range) &&
          JSON.stringify(a?.yaxis?.range) === JSON.stringify(b?.yaxis?.range);
        if (old.regenerate) {
          doc.caption = null;
          doc.alt = null;
        }
        doc.panels[active] = {
          source: id,
          title: old.title === sNow().title ? s.title : old.title,
          labels: [],
          ...(same ? { crop: old.crop, overview: old.overview } : {}),
        };
        update();
      })
    );
  return arr;
}
function layoutControls(p) {
  section(
    "Layout",
    choice(
      "Arrangement",
      [
        ["row", "Row"],
        ["stack", "Stack"],
        ["grid", "2 × 2 grid"],
      ],
      doc.layout,
      (v) => set("layout", v)
    ),
    num("Panel gap (pt)", doc.gap, 0, 100, (v) => set("gap", v)),
    panelChoice(),
    entry("Panel heading", p.title, (v) => {
      doc.headings = true;
      panelSet("title", v);
    }),
    row(
      ...[-1, 1].map((d) => {
        const b = button(d === 1 ? "Move later" : "Move earlier", () => {
          const j = active + d;
          [doc.panels[active], doc.panels[j]] = [
            doc.panels[j],
            doc.panels[active],
          ];
          active = j;
          update();
        });
        b.disabled = !doc.panels[active + d];
        return b;
      })
    ),
    doc.panels.length > 1 &&
      button("Remove panel", () => {
        doc.panels.splice(active, 1);
        active = Math.min(active, doc.panels.length - 1);
        update();
      })
  );
  section("Panel source", ...sourceControls());
  const names = [
    ...new Set(
      sNow()
        .figure.data.filter(
          (t) => t.showlegend !== false && t.name && t.visible !== false
        )
        .map((t) => t.name)
    ),
  ];
  const sel = sNow().settings?.selection,
    ids = {};
  if (sel?.compare) {
    for (const t of sNow().figure.data) {
      const side = t.meta?.publication_reading;
      if ((side === "A" || side === "B") && t.name)
        ids[t.name] =
          side === "A" ? sel.participant_id : sel.compare.participant_id;
    }
  }
  if (names.length)
    section(
      "Legend",
      Object.keys(ids).length &&
        button("Use reader IDs", () =>
          panelSet("legendNames", { ...p.legendNames, ...ids })
        ),
      choice(
        "Arrangement",
        ["As drawn", "Stacked"],
        p.legendStack ? "Stacked" : "As drawn",
        (v) => panelSet("legendStack", v === "Stacked")
      ),
      ...names.map((n) =>
        entry(n, p.legendNames?.[n] ?? n, (v) =>
          panelSet("legendNames", { ...p.legendNames, [n]: v })
        )
      )
    );
  const tr = heatInfo(sNow());
  if (tr) {
    const info = tr.meta.publication_heatmap,
      h = doc.heat;
    const matched = !!h && h.measure === info.measure && h.norm === info.norm;
    const apply = (min, max, shared) => {
      if (min >= max) {
        message("The upper limit must exceed the lower limit.");
        return;
      }
      set("heat", {
        min,
        max,
        shared,
        opacity:
          (sNow().figure.layout?.shapes || []).find(
            (sh) => sh.name === info.tag
          )?.opacity ?? 1,
        scale: tr.marker.colorscale,
        measure: info.measure,
        norm: info.norm,
      });
    };
    section(
      "Heatmap scale",
      note(info.measure + " · " + info.norm),
      matched
        ? row(
            num("Lower limit", h.min, 0, 1e10, (v) =>
              apply(v, h.max, h.shared)
            ),
            num("Upper limit", h.max, 0.001, 1e10, (v) =>
              apply(h.min, v, h.shared)
            )
          )
        : button("Lock matching heatmap limits", () =>
            apply(...tr.meta.word_heatmap_range, true)
          ),
      matched &&
        choice(
          "Legends",
          ["One shared legend", "Per panel"],
          h.shared ? "One shared legend" : "Per panel",
          (v) => apply(h.min, h.max, v === "One shared legend")
        ),
      matched && button("Restore source scales", () => set("heat", null))
    );
  }
}
function fitLabel(label, cell) {
  if (!cell) return;
  const x = (label.x - cell.box[0]) * cell.k,
    y = (label.y - cell.box[1]) * cell.k;
  if (x < 0 || x > cell.w || y < 0 || y > cell.h) return;
  const size = label.size || (doc.destination?.includes("slide") ? 18 : 9);
  const inset = Math.min(cell.w / 2, textWidth(label.text, size) / 2 + 2);
  label.dx = clip(x + label.dx, inset, cell.w - inset) - x;
  label.dy =
    clip(y + label.dy, Math.min(size + 2, cell.h), Math.max(0, cell.h - 2)) - y;
}
function regionControls(p) {
  const a = artNow();
  section(
    "Export region",
    panelChoice(),
    row(
      button(cropping ? "Cancel drawing" : "Draw crop", () => {
        cropping = !cropping;
        paintControls();
      }),
      button("Show full source", () => {
        cropping = false;
        panelSet("crop", null);
      })
    ),
    input.plotId &&
      p.source === input.project.currentSource &&
      button("Use current plot zoom", useZoom),
    choice(
      "Screen overview",
      ["Off", "Include locator"],
      p.overview ? "Include locator" : "Off",
      (v) => panelSet("overview", v !== "Off")
    )
  );
  if (!a) return;
  if (a.words.length) {
    const opts = a.words.map((w, i) => [i, w.text + " (" + (i + 1) + ")"]),
      first = p.firstWord ?? 0,
      last = p.lastWord ?? first;
    section(
      "Word span",
      choice("First visible word", opts, first, (v) =>
        panelSet("firstWord", +v)
      ),
      choice("Last visible word", opts, last, (v) => panelSet("lastWord", +v)),
      button("Crop to word span", () => {
        if (last < first) {
          message("The last word must follow the first.");
          return;
        }
        const words = a.words.slice(first, last + 1);
        if (words.some((w) => w.axis !== words[0].axis)) {
          message("Choose words from the same comparison panel.");
          return;
        }
        const measured = words.filter((w) => w.bounds);
        if (measured.length !== words.length) {
          message("Some selected words are outside the rendered plot.");
          return;
        }
        const bounds = measured.reduce(
          (a, w) => [
            Math.min(a[0], w.bounds[0]),
            Math.min(a[1], w.bounds[1]),
            Math.max(a[2], w.bounds[2]),
            Math.max(a[3], w.bounds[3]),
          ],
          [Infinity, Infinity, -Infinity, -Infinity]
        );
        const [l, t, r, b] = bounds;
        let left = 12,
          right = 12;
        for (const neighbor of a.words) {
          if (!neighbor.bounds || neighbor.axis !== words[0].axis) continue;
          const [x0, y0, x1, y1] = neighbor.bounds;
          if (y1 <= t || y0 >= b) continue;
          if (x1 <= l) left = Math.min(left, (l - x1) / 2);
          if (x0 >= r) right = Math.min(right, (x0 - r) / 2);
        }
        panelSet("crop", [l - left, t - 16, r - l + left + right, b - t + 32]);
      })
    );
  }
  const unique = new Map();
  a.events.forEach((e) => unique.set(e.axis + ":" + e.index, e));
  const events = [...unique.values()];
  if (events.length) {
    const i = clip(p.event || 0, 0, events.length - 1),
      e = events[i],
      next = unique.get(e.axis + ":" + (e.index + 1)),
      pin = (q, text, segment) => {
        p.labels.push({
          x: q.x,
          y: q.y,
          dx: 0,
          dy: -9,
          text,
          reading: e.axis,
          events: segment ? [e.index, next.index] : [e.index],
          ...(segment ? { segment } : {}),
        });
        fitLabel(p.labels.at(-1), cells[active]);
        update();
      };
    section(
      "Events",
      choice(
        "Fixation",
        events.map((q, j) => [
          j,
          q.axis + " · " + (q.detail || "Fixation " + q.index),
        ]),
        i,
        (v) => panelSet("event", +v)
      ),
      Number.isFinite(e.onset) &&
        note(
          fmt(e.onset) +
            " ms from the first displayed fixation" +
            (e.recorded
              ? " (recorded onsets)."
              : " (estimated from displayed durations).")
        ),
      button("Pin fixation " + e.index, () => pin(e, "Fixation " + e.index)),
      Number.isFinite(e.onset) &&
        button("Pin onset time", () =>
          pin(e, fmt(e.onset) + " ms" + (e.recorded ? "" : " (estimated)"))
        ),
      next &&
        button("Pin saccade " + e.index + " → " + next.index, () =>
          pin(
            { x: (e.x + next.x) / 2, y: (e.y + next.y) / 2 },
            e.index + " → " + next.index,
            [e.x, e.y, next.x, next.y]
          )
        ),
      choice(
        "Surrounding events",
        ["Show", "Hide event traces"],
        p.isolate ? "Hide event traces" : "Show",
        (v) => panelSet("isolate", v !== "Show")
      )
    );
  }
  if (p.labels.length) {
    const j = clip(p.label || 0, 0, p.labels.length - 1),
      l = p.labels[j],
      edit = (key, val) => {
        l[key] = val;
        update();
      };
    section(
      "Pinned label",
      choice(
        "Edit label",
        p.labels.map((q, k) => [k, q.text]),
        j,
        (v) => panelSet("label", +v)
      ),
      entry("Label text", l.text, (v) => edit("text", v)),
      row(
        num("Horizontal offset (pt)", l.dx, -2000, 2000, (v) => edit("dx", v)),
        num("Vertical offset (pt)", l.dy, -2000, 2000, (v) => edit("dy", v))
      ),
      note("Drag the label on the proof to move its leader."),
      button("Remove this label", () => {
        p.labels.splice(j, 1);
        update();
      })
    );
  }
}
function useZoom() {
  for (const frame of window.parent.document.querySelectorAll("iframe")) {
    try {
      const d = frame.contentDocument,
        gd = d?.getElementById(input.plotId);
      if (!gd) continue;
      const viewport = d.getElementById(
        input.plotId.replace("truescale-", "fit-")
      );
      if (!viewport) continue;
      const a = artNow(),
        box = gd.getBoundingClientRect(),
        v = viewport.getBoundingClientRect(),
        x = Math.max(0, v.left - box.left),
        y = Math.max(0, v.top - box.top);
      const w = Math.min(box.right, v.right) - Math.max(box.left, v.left),
        h = Math.min(box.bottom, v.bottom) - Math.max(box.top, v.top);
      if (w <= 0 || h <= 0) continue;
      panelSet("crop", [
        (x * a.w) / box.width,
        (y * a.h) / box.height,
        (w * a.w) / box.width,
        (h * a.h) / box.height,
      ]);
      return;
    } catch {
      continue;
    }
  }
  message("Open the source scanpath in this view to capture its zoom.");
}
function clipValues(p, s) {
  const times = clock(s),
    last = times.length - 1;
  return [
    times,
    clip(p.start ?? 0, 0, last),
    clip(p.end ?? last, 0, last),
    p.speed || s.figure.layout?.meta?.scanpath_playback_speed || 1,
  ];
}
function replayControls(p, s) {
  const [times, start, end, speed] = clipValues(p, s);
  section(
    "Replay panel",
    panelChoice(),
    !times.length &&
      note(
        "Add a replay from Scanpath → Export to select a clip and its poster."
      )
  );
  if (!times.length) return;
  const range = (name, k, v) =>
    num(name, v + 1, 1, times.length, (n) => {
      n = Math.round(n) - 1;
      if ((k === "start" && n > end) || (k === "end" && n < start)) {
        message("Choose an interval in reading order.");
        return;
      }
      p[k] = n;
      p.frame = clip(p.frame || 0, p.start ?? 0, p.end ?? times.length - 1);
      update();
    });
  const estimated = s.figure.layout?.meta?.scanpath_fixation_steps?.some(
    (r) => r.recorded === false
  );
  section(
    "Clip interval",
    row(range("First frame", "start", start), range("Last frame", "end", end)),
    choice(
      "Playback speed",
      [...new Set([0.5, 1, 2, speed])]
        .sort((a, b) => a - b)
        .map((x) => [x, x + "×"]),
      speed,
      (v) => panelSet("speed", +v)
    ),
    note(
      fmt(times[start] / 1000) +
        "–" +
        fmt(times[end] / 1000) +
        " s from replay start" +
        (estimated ? " · estimated clock from fixation durations" : "")
    )
  );
  const slider = node("input");
  slider.type = "range";
  slider.min = start;
  slider.max = end;
  slider.value = clip(p.frame || 0, start, end);
  slider.onchange = () => panelSet("frame", +slider.value);
  section(
    "Poster frame",
    field(
      "Frame " +
        (+slider.value + 1) +
        " · " +
        fmt(times[+slider.value] / 1000) +
        " s",
      slider
    ),
    row(
      button(playing ? "Pause" : "Play clip", () => previewClip()),
      button("Save poster PNG", async () => file("png", await moviePoster()))
    ),
    button("Prepare MP4 and poster", () => requestVideo()),
    note(
      "The clip uses this panel’s interval. Other panels stay at their selected frames."
    )
  );
}
async function previewClip() {
  if (playing) {
    playing = false;
    return;
  }
  const p = pNow(),
    [times, start, end, speed] = clipValues(p, sNow());
  playing = true;
  const t0 = performance.now();
  const poster = p.frame;
  let i = start;
  while (playing && i <= end) {
    p.frame = i;
    await redraw();
    const elapsed = (performance.now() - t0) * speed;
    do {
      i++;
    } while (i < end && times[i] - times[start] < elapsed);
    if (i <= end)
      await new Promise((ok) =>
        setTimeout(ok, Math.max(0, (times[i] - times[start] - elapsed) / speed))
      );
  }
  playing = false;
  p.frame = poster;
  await redraw();
}
async function saveNamed() {
  const art = await artwork(),
    canvas = await canvasFor(
      art,
      Math.min((192 * 72) / art.W, (140 * 72) / art.H)
    );
  const previous = await storage((s) => s.get(doc.name)),
    revision = (previous?.revision || 0) + 1;
  const saved = {
    project: snapshot(),
    revision,
    thumbnail: canvas.toDataURL("image/png"),
  };
  await storage((s) => s.put(saved, doc.name));
  message("Saved " + doc.name + " · revision " + revision + ".");
}
async function savedControls() {
  section(
    "Restore figure",
    button("Open figure recipe", () => $("upload").click()),
    note(
      "A recipe contains the plotted data and works without the original dataset."
    )
  );
  const rev = revision;
  try {
    const items = await storage((s) => s.getAll());
    if (tab !== "Saved figures" || rev !== revision) return;
    section(
      "Saved on this device",
      ...items.map((item) => {
        const saved = item.project || item,
          b = button(saved.name, () => {
            merged(saved);
            tab = tabs[2];
            update();
          });
        if (item.thumbnail) {
          const thumb = node("img");
          thumb.src = item.thumbnail;
          thumb.alt = "";
          b.prepend(thumb);
        }
        b.append(
          note(
            saved.panels.length +
              " panel" +
              (saved.panels.length === 1 ? "" : "s") +
              " · " +
              fmt(saved.width) +
              " mm · Revision " +
              (item.revision || 1)
          )
        );
        return b;
      }),
      !items.length && note("Name and save a figure under Caption & save.")
    );
  } catch (e) {
    if (tab === "Saved figures") message(e.message);
  }
}
function file(ext, bytes, type) {
  const blob = bytes instanceof Blob ? bytes : new Blob([bytes], { type }),
    url = URL.createObjectURL(blob),
    a = node("a");
  a.href = url;
  a.download =
    (doc.name.replace(/[^\p{L}\p{N}._-]+/gu, "-").slice(0, 100) || "figure") +
    "." +
    ext;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
const xmlOf = (root) => new XMLSerializer().serializeToString(root);
async function canvasFor(art, dpi = doc.dpi) {
  const w = Math.max(1, Math.round((art.W * dpi) / 72)),
    h = Math.max(1, Math.round((art.H * dpi) / 72));
  if (w * h > 64000000 || w > 32767 || h > 32767)
    throw Error(
      "This raster exceeds the browser’s drawing budget. Lower the DPI or choose SVG."
    );
  const root = art.root.cloneNode(true);
  root.setAttribute("width", w);
  root.setAttribute("height", h);
  const image = new Image();
  image.src =
    "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xmlOf(root));
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const c = canvas.getContext("2d");
  c.fillStyle = "white";
  c.fillRect(0, 0, w, h);
  c.drawImage(image, 0, 0, w, h);
  return canvas;
}
const blob64 = (blob) =>
  new Promise((ok, fail) => {
    const r = new FileReader();
    r.onload = () => ok(r.result.split(",")[1]);
    r.onerror = fail;
    r.readAsDataURL(blob);
  });
async function bytes(art, f) {
  if (f === "svg")
    return new Blob([xmlOf(art.root)], { type: "image/svg+xml" });
  const canvas = await canvasFor(art);
  if (f === "tiff")
    return new Blob(
      [
        makeTiff(
          canvas
            .getContext("2d")
            .getImageData(0, 0, canvas.width, canvas.height).data,
          canvas.width,
          canvas.height,
          doc.dpi
        ),
      ],
      { type: "image/tiff" }
    );
  const png = await new Promise((ok) => canvas.toBlob(ok, "image/png"));
  return pngMetadata(
    new Uint8Array(await png.arrayBuffer()),
    doc.dpi,
    doc.citation
  );
}
window.publicationBytes = async (f) => blob64(await bytes(await artwork(), f));
window.publicationPrint = async () => {
  const art = await artwork(),
    old = $("print-sheet");
  old?.remove();
  const sheet = node("div");
  sheet.id = "print-sheet";
  sheet.append(art.root);
  const css = node("style");
  css.textContent =
    "@page{size:" +
    doc.width +
    "mm " +
    art.H / PT +
    "mm;margin:0}#print-sheet{display:none}@media print{body>*:not(#print-sheet){display:none!important}html,body{margin:0;padding:0}#print-sheet{display:block;line-height:0}#print-sheet svg{display:block}}";
  sheet.append(css);
  document.body.append(sheet);
};
async function downloadArt(f) {
  if (f === "pdf") {
    if (input.session) {
      window.parent.postMessage(
        { key: input.session, action: "pdf", value: snapshot() },
        "*"
      );
      message("Preparing the PDF. Its download appears below the editor.");
    } else {
      await publicationPrint();
      window.print();
    }
    return;
  }
  file(f, await bytes(await artwork(), f));
}
function movie() {
  const i =
      doc.moviePanel ??
      doc.panels.findIndex((p) => clock(byId(p.source)).length),
    p = doc.panels[i],
    s = byId(p?.source);
  if (!s || !clock(s).length) throw Error("Select a replay panel.");
  return { p, s, range: clipValues(p, s) };
}
window.publicationClipDuration = () => {
  const {
    range: [t, a, b, s],
  } = movie();
  return (t[b] - t[a] + (t[b + 1] - t[b] || t[b] - t[b - 1] || 42)) / s;
};
window.publicationMovieFrame = async (elapsed) => {
  const {
    p,
    range: [t, a, b, s],
  } = movie();
  let lo = a,
    hi = b;
  while (lo < hi) {
    const m = Math.ceil((lo + hi) / 2);
    if (t[m] <= t[a] + elapsed * s) lo = m;
    else hi = m - 1;
  }
  p.frame = lo;
  return publicationPoster();
};
async function moviePoster() {
  const art = await artwork(),
    dpi = Math.min(144, (1080 * 72) / art.H, (1920 * 72) / art.W);
  const image = await canvasFor(art, dpi),
    canvas = document.createElement("canvas");
  canvas.width = image.width + (image.width % 2);
  canvas.height = image.height + (image.height % 2);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0);
  const blob = await new Promise((ok) => canvas.toBlob(ok, "image/png"));
  return pngMetadata(
    new Uint8Array(await blob.arrayBuffer()),
    dpi,
    doc.citation
  );
}
window.publicationPoster = async () => blob64(await moviePoster());
function requestVideo() {
  doc.moviePanel = active;
  persist();
  if (window.parent !== window && input.session) {
    window.parent.postMessage(
      { key: input.session, action: "video", value: snapshot() },
      "*"
    );
    message(
      "Preparing the clip and poster. The download appears below the editor."
    );
  } else {
    file("json", JSON.stringify(snapshot()), "application/json");
    message(
      "Render this recipe with scanpath-studio publication RECIPE.json -o clip.mp4."
    );
  }
}
$("library").onclick = () => {
  tab = "Saved figures";
  playing = false;
  paintControls();
};
$("zoom").onclick = () => {
  actual = !actual;
  redraw();
};
$("upload").onchange = async (e) => {
  try {
    const f = e.target.files[0];
    if (!f) return;
    merged(JSON.parse(await f.text()));
    tab = tabs[2];
    await update();
  } catch (err) {
    message(err.message);
  }
  e.target.value = "";
};
let drag = null;
$("sheet").onpointerdown = (e) => {
  const el = e.target.closest("[data-label]"),
    root = currentSheet?.root;
  if (!root || (!el && !cropping)) return;
  const xy = () =>
      new DOMPoint(e.clientX, e.clientY).matrixTransform(
        root.getScreenCTM().inverse()
      ),
    start = xy(),
    cell = cells[active];
  if (
    !el &&
    (!cell ||
      start.x < cell.x ||
      start.x > cell.x + cell.w ||
      start.y < cell.y ||
      start.y > cell.y + cell.h)
  )
    return;
  drag = { start, root, el, cell };
  if (!el) {
    drag.rect = svg("rect", {
      fill: "#117588",
      "fill-opacity": 0.15,
      stroke: "#117588",
      "pointer-events": "none",
    });
    root.append(drag.rect);
  }
  e.preventDefault();
  $("sheet").setPointerCapture(e.pointerId);
};
$("sheet").onpointermove = (e) => {
  if (!drag) return;
  const { root, start, el, rect } = drag,
    p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      root.getScreenCTM().inverse()
    );
  if (el)
    el.setAttribute(
      "transform",
      "translate(" + (p.x - start.x) + " " + (p.y - start.y) + ")"
    );
  else
    for (const [k, v] of Object.entries({
      x: Math.min(start.x, p.x),
      y: Math.min(start.y, p.y),
      width: Math.abs(p.x - start.x),
      height: Math.abs(p.y - start.y),
    }))
      rect.setAttribute(k, v);
};
$("sheet").onpointerup = (e) => {
  if (!drag) return;
  const { root, start, el, cell } = drag,
    p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      root.getScreenCTM().inverse()
    );
  drag = null;
  if (el) {
    const [i, j] = el.dataset.label.split(",").map(Number),
      l = doc.panels[i].labels[j];
    l.dx += p.x - start.x;
    l.dy += p.y - start.y;
    active = i;
  } else {
    const toX = (v) => cell.box[0] + clip(v - cell.x, 0, cell.w) / cell.k,
      toY = (v) => cell.box[1] + clip(v - cell.y, 0, cell.h) / cell.k;
    const box = [
      toX(Math.min(p.x, start.x)),
      toY(Math.min(p.y, start.y)),
      Math.abs(toX(p.x) - toX(start.x)),
      Math.abs(toY(p.y) - toY(start.y)),
    ];
    if (box[2] > 1 && box[3] > 1) pNow().crop = box;
    cropping = false;
  }
  update();
};
$("sheet").onpointercancel = () => {
  drag = null;
  redraw();
};
if (input.session && window.parent !== window)
  new ResizeObserver(() =>
    window.parent.postMessage(
      {
        key: input.session,
        height: document.querySelector("main").offsetHeight + 5,
      },
      "*"
    )
  ).observe(document.querySelector("main"));
window.publicationReady = (async () => {
  if (input.session) {
    try {
      const stored = draftStore()?.get(input.session);
      if (stored && stored.importId === input.importId)
        merged(clone(stored.project));
      const change = input.replacement,
        p = doc.panels[change?.index];
      if (change && p?.source === change.id && byId(change.new)) {
        p.source = change.new;
        p.crop = null;
        p.overview = false;
        p.labels = [];
        active = change.index;
      }
      persist();
    } catch {
      /* Editing and file downloads also work without device storage. */
    }
  }
  await redraw();
})();
