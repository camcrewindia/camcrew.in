/**
 * footer-loader.js
 * Fetches footer.html and injects it into #site-footer.
 * Mirrors the pattern used by header-loader.js.
 */
(async function () {
  const placeholder = document.getElementById('site-footer');
  if (!placeholder) return;

  try {
    const res  = await fetch('/footer.html');
    const html = await res.text();
    placeholder.outerHTML = html;
  } catch (e) {
    console.warn('footer-loader: could not load footer.html', e);
  }
})();
