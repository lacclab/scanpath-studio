/* The home page recording (ENG-78) plays on its own unless the reader has asked
 * the system for reduced motion. It is muted and has controls, so it can always
 * be started or paused by hand. `document$` is Material's page stream: instant
 * navigation back to the home page swaps the content without reloading this.
 */
(() => {
  const play = () => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    for (const video of document.querySelectorAll("video[data-autoplay]")) {
      video.play().catch(() => {});
    }
  };
  if (typeof document$ !== "undefined") document$.subscribe(play);
  else document.addEventListener("DOMContentLoaded", play);
})();
