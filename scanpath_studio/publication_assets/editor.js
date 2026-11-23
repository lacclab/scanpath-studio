let libraryOpen = false,
  tool = "",
  format = "png",
  cropping = false,
  playing = false;
let startingDraft = null,
  openedFile = false;
let target,
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
  n.append(...children.filter(Boolean));
  return n;
};
function section(title, ...children) {
  const n = node("section");
  if (title) n.append(node("h2", title));
  n.append(...children.filter(Boolean));
  target.append(n);
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
function storage(stores, mode, action) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      const gallery = db.createObjectStore("gallery", { keyPath: "name" });
      if (!db.objectStoreNames.contains("figures")) {
        db.createObjectStore("figures");
        return;
      }
      // Read old records one at a time. Opening the gallery then needs only
      // the small thumbnails, even when its figures contain long replays.
      const cursor = req.transaction.objectStore("figures").openCursor();
      cursor.onsuccess = () => {
        const row = cursor.result;
        if (!row) return;
        const { thumbnail, revision } = row.value;
        gallery.put({ name: row.key, thumbnail, revision: revision || 1 });
        row.continue();
      };
    };
    req.onerror = () =>
      reject(
        Error(
          "Device storage is unavailable. Download a recipe to keep your figure."
        )
      );
    req.onsuccess = () => {
      const db = req.result,
        tx = db.transaction(stores, mode);
      let out;
      try {
        out = action(tx);
      } catch (e) {
        db.close();
        reject(e);
        return;
      }
      tx.oncomplete = () => {
        db.close();
        resolve(out?.result);
      };
      tx.onerror = () => {
        db.close();
        reject(tx.error);
      };
      tx.onabort = tx.onerror;
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
const draftKey = JSON.stringify([input.session, input.importId]);
function persist() {
  const drafts = draftStore();
  if (!drafts) return;
  drafts.delete(draftKey);
  drafts.set(draftKey, {
    starting: openedFile ? startingDraft : snapshot(),
    opened: openedFile ? snapshot() : null,
  });
  if (drafts.size > 4) drafts.delete(drafts.keys().next().value);
}
function openFigure(item) {
  doc = clone(check(item));
  active = 0;
  tool = "";
  cropping = false;
  libraryOpen = !doc.panels.length;
  cache.clear();
}
function openSaved(item) {
  check(item);
  if (!openedFile) startingDraft = snapshot();
  openFigure(item);
  openedFile = true;
  return update();
}
function returnToStart() {
  openFigure(startingDraft ?? input.project);
  openedFile = false;
  startingDraft = null;
  return update();
}
function update() {
  playing = false;
  persist();
  return redraw();
}
function redraw(panels = doc.panels) {
  const rev = ++revision;
  const render = async () => {
    if (rev !== revision) return;
    try {
      if (!doc.panels.length) {
        libraryOpen = true;
        paintControls();
        return;
      }
      const art = await artwork(panels);
      if (rev !== revision) return;
      cells = art.positions;
      currentSheet = art;
      $("sheet").replaceChildren(art.root);
      $("sheet").style.maxWidth =
        Math.max(100, Math.round((480 * art.W) / art.H)) + "px";
      $("issues").replaceChildren();
      for (const issue of art.issues.filter((issue) => !printIssue(issue))) {
        const n = node("div", issue);
        if (issue.startsWith("The caption"))
          n.append(
            button("Wrap caption", () => set("captionPlacement", "Wrap"))
          );
        if (
          issue.startsWith("Move the pinned label") &&
          doc.panels.length === 1
        )
          n.append(
            button("Fit label inside figure", () => {
              pNow().labels.forEach((label) => fitLabel(label, cells[0]));
              update();
            })
          );
        $("issues").append(n);
      }
      message("");
      paintControls();
    } catch (e) {
      message(e.message || String(e));
      currentSheet = null;
      cells = [];
      $("sheet").replaceChildren();
      $("issues").replaceChildren();
      paintControls();
    }
  };
  queued = queued.catch(() => {}).then(render);
  return queued;
}
const printIssue = (issue) =>
  issue.startsWith("Smallest") || issue.startsWith("The figure exceeds");
const formats = {
  png: "For slides and documents.",
  svg: "Editable vector artwork that stays sharp at any size.",
  pdf: "Vector artwork for manuscripts and print.",
  tiff: "A high-resolution image for journal submissions.",
};
function disclosure(name, render) {
  const summary = button(name, () => {
    tool = tool === name ? "" : name;
    cropping = false;
    playing = false;
    paintControls();
    [...$("controls").querySelectorAll("button.disclosure")]
      .find((b) => b.textContent === name)
      ?.focus();
  });
  summary.className = "disclosure";
  summary.setAttribute("aria-expanded", String(tool === name));
  target.append(summary);
  if (tool !== name) return;
  const body = node("div", null, "tool-body");
  target.append(body);
  target = body;
  render();
  target = $("controls");
}
function paintControls() {
  const controls = $("controls");
  const focus = controls.contains(document.activeElement)
    ? document.activeElement.getAttribute("aria-label")
    : null;
  controls.replaceChildren();
  target = controls;
  $("workspace").classList.toggle("library", libraryOpen);
  $("preview").hidden = libraryOpen;
  $("library").hidden = !doc.panels.length;
  $("library").textContent = libraryOpen ? "Back to figure" : "Save or open";
  $("heading").textContent = libraryOpen ? "Saved figures" : "Prepare figure";
  $("figure-name").textContent = libraryOpen ? "" : doc.name;
  $("sheet").classList.toggle("cropping", cropping);
  if (libraryOpen) {
    savedControls();
    return;
  }
  section(
    "Download figure",
    choice(
      "File format",
      Object.keys(formats).map((k) => [k, k.toUpperCase()]),
      format,
      (v) => {
        format = v;
        paintControls();
      }
    ),
    note(formats[format]),
    button(
      format === "pdf" && !input.session
        ? "Print / save PDF"
        : "Download " + format.toUpperCase(),
      () => downloadArt(format),
      true
    )
  );
  const p = pNow(),
    s = sNow();
  if (doc.panels.length === 1) {
    disclosure("Crop", () => cropControls(p));
    if (artNow()?.events.length || p.labels.length)
      disclosure("Label events", () => eventControls(p));
    if (clock(s).length) disclosure("Replay clip", () => replayControls(p, s));
    if (
      s.figure.layout?.showlegend !== false &&
      s.figure.data.some(
        (t) => t.name && t.showlegend !== false && t.visible !== false
      )
    )
      disclosure("Legend", () => legendControls(p));
  } else {
    section(
      "",
      note(
        "This file contains a saved layout. Download it as shown, or open one of its figures as a separate copy."
      ),
      choice(
        "Figure to copy",
        doc.panels.map((q, i) => [i, q.title]),
        active,
        (v) => {
          active = Number(v);
        }
      ),
      button("Edit a copy", () => {
        const project = snapshot(),
          panel = pNow();
        openSaved({
          ...project,
          name: doc.name + " · " + (panel.title || letter(active)),
          panels: [panel],
          sources: [sNow()],
          caption: null,
          alt: null,
          headings: false,
          moviePanel: 0,
        });
      })
    );
  }
  disclosure("Caption and description", captionControls);
  disclosure("Print settings", printControls);
  if (focus)
    [...controls.querySelectorAll("[aria-label]")]
      .find((el) => el.getAttribute("aria-label") === focus)
      ?.focus({ preventScroll: true });
}
function captionControls() {
  section(
    "",
    entry("Caption", doc.caption ?? draft(), (v) => set("caption", v), {
      multi: true,
    }),
    choice(
      "Caption placement",
      [
        ["Manuscript", "Keep separate"],
        ["Wrap", "Include below figure"],
        ["Single line", "Include on one line"],
      ],
      doc.captionPlacement,
      (v) => set("captionPlacement", v)
    ),
    entry("Alternative text", doc.alt ?? draft(true), (v) => set("alt", v), {
      multi: true,
    }),
    button("Download text", () =>
      file(
        "txt",
        [
          doc.caption ?? draft(),
          "",
          doc.alt ?? draft(true),
          "",
          doc.citation.Comment,
        ].join("\n")
      )
    ),
    (doc.caption !== null || doc.alt !== null) &&
      button("Restore suggested text", () => {
        doc.caption = null;
        set("alt", null);
      })
  );
}
function printControls() {
  const art = currentSheet;
  section(
    "",
    choice(
      "Page preset",
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
    row(
      num("Minimum text (pt)", doc.minimum, 1, 72, (v) => set("minimum", v)),
      num("Resolution (dpi)", doc.dpi, 50, 1200, (v) =>
        set("dpi", Math.round(v))
      )
    ),
    choice(
      "Color",
      ["Color", "Grayscale"],
      doc.gray ? "Grayscale" : "Color",
      (v) => set("gray", v === "Grayscale")
    ),
    art &&
      note(
        fmt(doc.width) +
          " × " +
          fmt(art.H / PT) +
          " mm" +
          (Number.isFinite(art.min)
            ? " · Smallest text " + fmt(art.min) + " pt"
            : "")
      ),
    ...(art?.issues || []).filter(printIssue).map(note),
    input.batch &&
      button("Use this size for batch export", () =>
        window.parent.postMessage(
          {
            key: input.session,
            action: "batch",
            value: { width: doc.width, dpi: doc.dpi },
          },
          "*"
        )
      )
  );
}
function legendControls(p) {
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
      "",
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
function cropControls(p) {
  const a = artNow();
  section(
    "",
    cropping && note("Drag a rectangle on the figure to keep that area."),
    row(
      button(cropping ? "Cancel drawing" : "Draw crop", () => {
        cropping = !cropping;
        paintControls();
      }),
      p.crop &&
        button("Remove crop", () => {
          cropping = false;
          panelSet("crop", null);
        })
    ),
    input.plotId &&
      p.source === input.project.panels[0]?.source &&
      button("Use current plot zoom", useZoom),
    p.crop &&
      choice(
        "Show full figure inset",
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
}
function eventControls(p) {
  const a = artNow();
  const unique = new Map();
  (a?.events || []).forEach((e) => unique.set(e.axis + ":" + e.index, e));
  const events = [...unique.values()];
  const multipleReadings = new Set(events.map((q) => q.axis)).size > 1;
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
      "",
      choice(
        "Fixation",
        events.map((q, j) => [
          j,
          (q.detail || "Fixation " + q.index) +
            (multipleReadings ? " · " + q.axis : ""),
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
      next && e.spatial !== false &&
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
      note("Drag the label on the figure to move it."),
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
    button(
      input.session ? "Prepare MP4 and poster" : "Save clip settings for MP4",
      () => requestVideo()
    )
  );
}
async function previewClip() {
  if (playing) {
    playing = false;
    return redraw();
  }
  const p = pNow(),
    [times, start, end, speed] = clipValues(p, sNow());
  const playback = {};
  playing = playback;
  const t0 = performance.now();
  let i = start;
  while (playing === playback && i <= end) {
    await redraw(
      doc.panels.map((panel) => (panel === p ? { ...panel, frame: i } : panel))
    );
    const elapsed = (performance.now() - t0) * speed;
    do {
      i++;
    } while (i < end && times[i] - times[start] < elapsed);
    if (playing === playback && i <= end)
      await new Promise((ok) =>
        setTimeout(ok, Math.max(0, (times[i] - times[start] - elapsed) / speed))
      );
  }
  if (!playing || playing === playback) {
    playing = false;
    await redraw();
  }
}
async function saveNamed() {
  const atRevision = revision;
  const art = await artwork(),
    canvas = await canvasFor(
      art,
      Math.min((192 * 72) / art.W, (140 * 72) / art.H)
    );
  if (atRevision !== revision) return;
  const name = doc.name,
    project = { ...snapshot(), panels: clone(doc.panels) },
    thumbnail = canvas.toDataURL("image/png");
  await storage(["figures", "gallery"], "readwrite", (tx) => {
    const gallery = tx.objectStore("gallery");
    const previous = gallery.get(name);
    previous.onsuccess = () => {
      const revision = (previous.result?.revision || 0) + 1;
      gallery.put({ name, thumbnail, revision });
      tx.objectStore("figures").put({ project, revision }, name);
    };
  });
  paintControls();
  message("Saved " + name + " on this device.");
}
let libraryRevision = 0;
async function savedControls() {
  const generation = ++libraryRevision;
  if (doc.panels.length) {
    section(
      "Save this figure",
      entry("Figure name", doc.name, (v) =>
        set("name", v.trim() || "Untitled figure")
      ),
      button("Save on this device", saveNamed, true),
      button("Download editable file", () =>
        file("json", JSON.stringify(snapshot()))
      ),
      note("The editable file includes the plotted data and embedded images."),
      input.session &&
        button("Download offline editor", () =>
          window.parent.postMessage(
            { key: input.session, action: "html", value: snapshot() },
            "*"
          )
        ),
      doc.panels.length === 1 &&
        sNow().settings &&
        button("Download source settings", () =>
          file(
            "settings.json",
            JSON.stringify(sNow().settings)
          )
        )
    );
  }
  section(
    "Open a figure",
    button("Open figure file", () => $("upload").click()),
    openedFile &&
      input.project.panels.length &&
      button("Return to starting figure", returnToStart)
  );
  const list = node("section");
  list.append(node("h2", "Saved on this device"));
  target.append(list);
  try {
    const items = await storage("gallery", "readonly", (tx) =>
      tx.objectStore("gallery").getAll()
    );
    if (!libraryOpen || generation !== libraryRevision) return;
    if (!items.length)
      list.append(note("Figures you save on this device will appear here."));
    for (const item of items) {
      const b = button(item.name, async () => {
        const stored = await storage("figures", "readonly", (tx) =>
          tx.objectStore("figures").get(item.name)
        );
        if (stored) await openSaved(stored.project || stored);
      });
      if (item.thumbnail) {
        const img = node("img");
        img.src = item.thumbnail;
        img.alt = "";
        b.prepend(img);
      }
      list.append(b);
    }
  } catch (e) {
    if (libraryOpen && generation === libraryRevision)
      list.append(note(e.message));
  }
}
function file(ext, bytes) {
  // The link delivers bytes even when a browser opens it outside the editor.
  const blob = new Blob([bytes], { type: "application/octet-stream" }),
    url = URL.createObjectURL(blob),
    a = node("a");
  if (!url.startsWith("blob:")) throw Error("Could not create a download link.");
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
  if (!s || !clock(s).length) throw Error("Open a replay to export a clip.");
  return { p, s, range: clipValues(p, s) };
}
window.publicationClipDuration = () => {
  const {
    range: [t, a, b, s],
  } = movie();
  return (t[b] - t[a] + (t[b + 1] - t[b] || t[b] - t[b - 1] || 42)) / s;
};
let lastMovieFrame;
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
  // Several 24-fps output frames can fall within a single fixation. They
  // share the same pixels, including every stationary panel and annotation.
  if (
    lastMovieFrame?.panel === p &&
    lastMovieFrame.index === lo &&
    lastMovieFrame.revision === revision
  )
    return lastMovieFrame.png;
  const png = await publicationPoster();
  lastMovieFrame = { panel: p, index: lo, revision, png };
  return png;
};
async function moviePoster() {
  const art = await artwork(doc.panels, true),
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
    file("json", JSON.stringify(snapshot()));
    message(
      "Render this recipe with scanpath-studio publication RECIPE.json -o clip.mp4."
    );
  }
}
$("library").onclick = () => {
  libraryOpen = !libraryOpen;
  playing = false;
  cropping = false;
  message("");
  paintControls();
};
$("upload").onchange = async (e) => {
  try {
    const f = e.target.files[0];
    if (!f) return;
    await openSaved(JSON.parse(await f.text()));
  } catch (err) {
    message(err.message);
  }
  e.target.value = "";
};
let drag = null;
$("sheet").onpointerdown = (e) => {
  const el = e.target.closest("[data-label]"),
    root = currentSheet?.root;
  if (doc.panels.length !== 1 || !root || (!el && !cropping)) return;
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
      const stored = draftStore()?.get(draftKey);
      if (stored) {
        startingDraft = stored.starting;
        openedFile = Boolean(stored.opened);
        openFigure(stored.opened ?? stored.starting);
      }
      persist();
    } catch {
      /* Editing and file downloads also work without device storage. */
    }
  }
  await redraw();
})();
