/* Figures on the docs pages (ENG-78).
 *
 * `docs_support.embed` writes each figure's Plotly JSON into the page. This
 * draws it the way the app does (`tabs._render_true_scale_chart`): at the
 * figure's exact pixel size, then scaled uniformly to the column with a CSS
 * transform, so the word labels keep the size they were fitted to — a Plotly
 * re-layout would leave the fonts and markers at their pixel sizes instead.
 *
 * Plotly is fetched only when a figure scrolls near the viewport, from the
 * site's own copy (`mkdocs_hooks.on_post_build`), never from a CDN. Material's
 * instant navigation swaps pages without reloading this script, so `init` runs
 * on its `document$` stream rather than once on load.
 */
(() => {
  const PLOTLY_SRC = new URL("plotly.min.js", document.currentScript.src).href;
  let plotly = null;

  const loadPlotly = () => {
    if (window.Plotly) return Promise.resolve(window.Plotly);
    plotly ??= new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = PLOTLY_SRC;
      tag.onload = () => resolve(window.Plotly);
      tag.onerror = () => reject(new Error(`could not load ${PLOTLY_SRC}`));
      document.head.appendChild(tag);
    });
    return plotly;
  };

  const fit = (host) => {
    const stage = host.querySelector(".sps-plot-stage");
    const width = Number(host.dataset.width);
    const height = Number(host.dataset.height);
    const scale = Math.min(1, host.clientWidth / width);
    stage.style.transform = `scale(${scale})`;
    host.style.height = `${height * scale}px`;
  };

  const draw = async (host) => {
    const source = host.querySelector('script[type="application/json"]');
    const spec = JSON.parse(source.textContent);
    const stage = document.createElement("div");
    stage.className = "sps-plot-stage";
    stage.style.width = `${host.dataset.width}px`;
    stage.style.height = `${host.dataset.height}px`;
    host.appendChild(stage);
    const Plotly = await loadPlotly();
    await Plotly.newPlot(stage, spec);
    fit(host);
    new ResizeObserver(() => fit(host)).observe(host);
    host.dataset.state = "ready";
  };

  const init = () => {
    const hosts = document.querySelectorAll(".sps-plot:not([data-state])");
    if (!hosts.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          observer.unobserve(entry.target);
          draw(entry.target).catch((error) => {
            entry.target.dataset.state = "error";
            console.error(error);
          });
        }
      },
      { rootMargin: "400px 0px" },
    );
    for (const host of hosts) {
      host.dataset.state = "pending";
      observer.observe(host);
    }
  };

  if (typeof document$ !== "undefined") document$.subscribe(init);
  else if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
