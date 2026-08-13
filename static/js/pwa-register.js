/**
 * pwa-register.js
 * Registers the Service Worker and manages native app installation prompts.
 */
(function() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js')
        .then((reg) => {
          console.log('[PWA] Service Worker registered successfully with scope:', reg.scope);
        })
        .catch((err) => {
          console.warn('[PWA] Service Worker registration failed:', err);
        });
    });
  }

  // PWA Install Prompt Logic
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent standard minibar
    e.preventDefault();
    deferredPrompt = e;
    console.log('[PWA] beforeinstallprompt event captured');

    // Display install banner if element exists
    const installBanner = document.getElementById('pwa-install-banner');
    if (installBanner) {
      installBanner.style.display = 'flex';
    }
  });

  window.promptPwaInstall = function() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt');
      } else {
        console.log('[PWA] User dismissed the install prompt');
      }
      deferredPrompt = null;
      const installBanner = document.getElementById('pwa-install-banner');
      if (installBanner) installBanner.style.display = 'none';
    });
  };
})();
