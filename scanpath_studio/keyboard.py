"""Keyboard shortcuts for the Scanpath page and its same-origin figure."""

from __future__ import annotations

from .loading import PLOT_DRAWN_EVENT, PLOT_STAGE_SELECTOR

# Install in the page so rerenders can replace buttons and figures while the
# shortcuts still operate the current reading. Keys in a figure's document
# don't bubble to the page.
SCANPATH_SHORTCUTS = """<script>
(function () {
  function install() {
    const stage = '__STAGE__';
    const steps = '.st-key-single_prev_trial, .st-key-single_next_trial, ' +
      '.st-key-single_compare_prev, .st-key-single_compare_next';
    const overlays = '[role="dialog"], [role="listbox"], [role="menu"], ' +
      '[data-testid="stPopoverBody"], .st-key-tour_card';

    function onKey(event) {
      const {key, target} = event;
      if (!['ArrowLeft', 'ArrowRight', ' '].includes(key) || event.defaultPrevented ||
          event.isComposing || event.altKey || event.ctrlKey || event.metaKey ||
          (key === ' ' && event.shiftKey) || !target.matches) return;
      // Leave keys to the focused widget, including Space on the step buttons.
      const background = target.matches('body, html, main, [data-testid="stMain"], ' +
        '[data-testid="stApp"], [data-testid="stAppViewContainer"], .js-plotly-plot');
      if (!background && (key === ' ' || !target.closest(steps))) return;
      if (target.isContentEditable || !target.ownerDocument.getSelection()?.isCollapsed) return;
      if ([...document.querySelectorAll(overlays)].some(el => el.checkVisibility())) return;

      if (key === ' ') {
        const frame = document.querySelector(stage + ' iframe[tabindex="0"]');
        const bar = frame?.contentDocument?.querySelector('[data-sps-transport]');
        if (!bar) return;
        event.preventDefault();
        if (!event.repeat) bar.dispatchEvent(new Event('sps-toggle-replay'));
      } else {
        const direction = key === 'ArrowLeft' ? 'prev' : 'next';
        const name = event.shiftKey ? 'single_compare_' + direction : 'single_' + direction + '_trial';
        const button = document.querySelector('.st-key-' + name + ' button');
        if (!button || button.disabled || !button.checkVisibility()) return;
        event.preventDefault();
        if (!event.repeat) button.click();
      }
    }

    function listenToFigure(frame) {
      if (frame?.closest(stage)) frame.contentDocument?.addEventListener('keydown', onKey);
    }
    document.addEventListener('keydown', onKey);
    window.addEventListener('__DRAWN__', event => listenToFigure(event.detail));
    listenToFigure(document.querySelector(stage + ' iframe[tabindex="0"]'));
  }
  const doc = window.parent.document;
  if (doc.getElementById('sps-scanpath-shortcuts')) return;
  const script = doc.createElement('script');
  script.id = 'sps-scanpath-shortcuts';
  script.textContent = '(' + install.toString() + ')()';
  doc.head.appendChild(script);
})();
</script>""".replace("__STAGE__", PLOT_STAGE_SELECTOR).replace(
    "__DRAWN__", PLOT_DRAWN_EVENT
)
