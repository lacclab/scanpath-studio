/* All controls: each section's picture of its menu (`a.sps-ctl`, written just
 * under the section's title) becomes a small "Show image" button beside that
 * title. A click opens the picture over the page, under the button, the way a
 * hover card would; a second click, a click elsewhere or Escape closes it, and
 * the picture itself links to the full-size file. Without JavaScript the
 * pictures simply stay under their titles. `document$` is Material's page
 * stream, so this runs again after instant navigation.
 */
(() => {
  let open = null;
  const close = () => {
    if (!open) return;
    open.pop.remove();
    open.btn.setAttribute("aria-expanded", "false");
    open = null;
  };
  const show = (btn, link) => {
    const pop = document.createElement("div");
    pop.className = "sps-shot-pop";
    pop.append(link.cloneNode(true));
    const img = pop.querySelector("img");
    img.loading = "eager";
    pop.querySelector("a").className = "";
    document.body.append(pop);
    const place = () => {
      const r = btn.getBoundingClientRect();
      const w = pop.offsetWidth;
      const left = Math.max(8, Math.min(r.left, innerWidth - w - 8));
      pop.style.left = `${left + scrollX}px`;
      pop.style.top = `${r.bottom + scrollY + 6}px`;
    };
    place();
    img.addEventListener("load", place);
    btn.setAttribute("aria-expanded", "true");
    open = { btn, pop };
  };
  const setup = () => {
    close();
    for (const link of document.querySelectorAll(".md-typeset a.sps-ctl")) {
      const holder = link.parentElement.tagName === "P" ? link.parentElement : link;
      const heading = holder.previousElementSibling;
      if (!heading || !/^H[1-6]$/.test(heading.tagName)) continue;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sps-shot-btn";
      btn.textContent = "Show image";
      btn.setAttribute("aria-expanded", "false");
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        const same = open && open.btn === btn;
        close();
        if (!same) show(btn, link);
      });
      const anchor = heading.querySelector(".headerlink");
      heading.insertBefore(btn, anchor);
      holder.hidden = true;
    }
  };
  document.addEventListener("click", (event) => {
    if (open && !open.pop.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  if (typeof document$ !== "undefined") document$.subscribe(setup);
  else document.addEventListener("DOMContentLoaded", setup);
})();
