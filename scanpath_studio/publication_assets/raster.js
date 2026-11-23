// PNG physical dimensions and citation chunks are recorded without resampling.
function pngMetadata(raw, dpi, metadata) {
  const enc = new TextEncoder(),
    parts = [raw.slice(0, 33)];
  function chunk(name, body) {
    const data = new Uint8Array(body.length + 12),
      view = new DataView(data.buffer);
    view.setUint32(0, body.length);
    data.set(enc.encode(name), 4);
    data.set(body, 8);
    let crc = -1;
    for (const b of data.subarray(4, -4)) {
      crc ^= b;
      for (let i = 0; i < 8; i++)
        crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
    view.setUint32(data.length - 4, (crc ^ -1) >>> 0);
    parts.push(data);
  }
  const size = new Uint8Array(9),
    v = new DataView(size.buffer),
    ppm = Math.round(dpi / 0.0254);
  v.setUint32(0, ppm);
  v.setUint32(4, ppm);
  size[8] = 1;
  chunk("pHYs", size);
  for (const [key, value] of Object.entries(metadata || {}))
    chunk("iTXt", enc.encode(key + "\0\0\0\0\0" + value));
  const source = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
  for (let i = 33; i + 12 <= raw.length; ) {
    const n = source.getUint32(i) + 12;
    if (String.fromCharCode(...raw.subarray(i + 4, i + 8)) !== "pHYs")
      parts.push(raw.subarray(i, i + n));
    i += n;
  }
  return new Blob(parts, { type: "image/png" });
}
// Baseline little-endian RGB TIFF, one uncompressed strip.
function makeTiff(rgba, w, h, dpi) {
  const desc = new TextEncoder().encode(JSON.stringify(doc.citation) + "\0"),
    tags = 14,
    base = 8 + 2 + 12 * tags + 4,
    bits = base,
    xres = bits + 6,
    yres = xres + 8,
    description = yres + 8,
    pixels = description + desc.length + (desc.length % 2),
    len = w * h * 3;
  const out = new Uint8Array(pixels + len),
    v = new DataView(out.buffer),
    u16 = (p, x) => v.setUint16(p, x, true),
    u32 = (p, x) => v.setUint32(p, x, true);
  out.set([73, 73]);
  u16(2, 42);
  u32(4, 8);
  u16(8, tags);
  let off = 10;
  for (const [id, type, count, value] of [
    [256, 4, 1, w],
    [257, 4, 1, h],
    [258, 3, 3, bits],
    [259, 3, 1, 1],
    [262, 3, 1, 2],
    [270, 2, desc.length, description],
    [273, 4, 1, pixels],
    [277, 3, 1, 3],
    [278, 4, 1, h],
    [279, 4, 1, len],
    [282, 5, 1, xres],
    [283, 5, 1, yres],
    [284, 3, 1, 1],
    [296, 3, 1, 2],
  ]) {
    u16(off, id);
    u16(off + 2, type);
    u32(off + 4, count);
    if (type === 3 && count === 1) u16(off + 8, value);
    else u32(off + 8, value);
    off += 12;
  }
  [0, 2, 4].forEach((i) => u16(bits + i, 8));
  [xres, yres].forEach((i) => {
    u32(i, dpi);
    u32(i + 4, 1);
  });
  out.set(desc, description);
  for (let i = 0, j = pixels; i < rgba.length; i += 4) {
    out[j++] = rgba[i];
    out[j++] = rgba[i + 1];
    out[j++] = rgba[i + 2];
  }
  return out;
}
