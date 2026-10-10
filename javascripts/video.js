/* Recordings marked `data-autoplay` (ENG-78's home page demo, the Gallery's
 * *The app at work*) play on their own while they are on screen, unless the
 * reader has asked the system for reduced motion, and pause once scrolled
 * away, so a page of them never runs, or downloads, all at once. Each is muted
 * and has controls, so it can always be started or paused by hand.
 * `document$` is Material's page stream: instant navigation swaps the content
 * without reloading this, so the observer is pointed at the new page's videos.
 */
(() => {
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const onScreen = new IntersectionObserver(
    (entries) => {
      for (const { target, isIntersecting } of entries) {
        if (isIntersecting && !reduced()) target.play().catch(() => {});
        else if (!target.paused) target.pause();
      }
    },
    { threshold: 0.4 },
  );
  const watch = () => {
    onScreen.disconnect();
    for (const video of document.querySelectorAll("video[data-autoplay]")) {
      onScreen.observe(video);
    }
  };
  if (typeof document$ !== "undefined") document$.subscribe(watch);
  else document.addEventListener("DOMContentLoaded", watch);
})();
