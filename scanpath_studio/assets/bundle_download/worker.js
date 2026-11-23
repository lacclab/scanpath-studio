// Serve one ordinary ZIP download from bounded, sequential requests to Streamlit.
self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== "GET") return;
  const scope = new URL(self.registration.scope);
  const match = /^([A-Za-z0-9_-]+)\/(scanpath_export_\d{8}_\d{6}\.zip)$/.exec(
    url.pathname.slice(scope.pathname.length)
  );
  if (!match || !url.pathname.startsWith(scope.pathname)) return;
  const [, folder, filename] = match;
  const size = Number(url.searchParams.get("size"));
  const partSize = Number(url.searchParams.get("part"));
  if (!Number.isSafeInteger(size) || !Number.isSafeInteger(partSize) || size <= 0 || partSize <= 0) {
    event.respondWith(new Response("Invalid download size", { status: 400 }));
    return;
  }

  let written = 0;
  const abort = new AbortController();
  const stream = new ReadableStream({
    async pull(controller) {
      const index = Math.floor(written / partSize);
      const response = await fetch(new URL(folder + "/" + index + ".part", scope), {
        cache: "no-store", signal: abort.signal
      });
      if (!response.ok) throw new Error("The export is no longer available.");
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.length !== Math.min(partSize, size - written)) throw new Error("Incomplete ZIP part");
      written += bytes.length;
      controller.enqueue(bytes);
      if (written === size) controller.close();
    },
    cancel() { abort.abort(); }
  });
  event.respondWith(new Response(stream, { headers: {
    "Content-Type": "application/zip",
    "Content-Length": String(size),
    "Content-Disposition": 'attachment; filename="' + filename + '"',
    "Cache-Control": "no-store"
  }}));
});
