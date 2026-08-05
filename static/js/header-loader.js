/**
 * header-loader.js
 * Fetches header.html, injects it into #site-header, sets the active nav
 * link for the current page, wires the mobile menu, and handles auth state.
 * Exposes window.signOut() globally for use by any page.
 */
(async function () {

  // ── 1. Fetch & inject ────────────────────────────────────────────────────
  const placeholder = document.getElementById('site-header');
  if (!placeholder) return;

  try {
    const res  = await fetch('/header.html');
    const html = await res.text();
    placeholder.outerHTML = html;
  } catch (e) {
    console.warn('header-loader: could not load header.html', e);
    return;
  }

  // ── 2. Active nav link ───────────────────────────────────────────────────
  const page = window.location.pathname.split('/').pop() || 'index.html';

  const activeKey = {
    'index.html':        'home',
    '':                  'home',
    'About.html':        'about',
    'rentals.html':      'rentals',
    'sales.html':        'sales',
    'cart.html':         'cart',
    'checkout.html':     'cart',
    'services.html':     'services',
    'photographers.html':'services',
    'videographers.html':'services',
    'designers.html':    'services',
    'developers.html':   'services',
    'organizers.html':   'services',
    'caterers.html':     'services',
    'profile.html':         'profile',
    'customer-profile.html':'profile',
    'signin.html':       'signin',
  }[page];

  const ACTIVE_DESKTOP = 'text-primary font-bold border-b-2 border-primary';
  const ACTIVE_MOBILE  = 'text-primary font-bold border-l-2 border-primary pl-3';

  if (activeKey) {
    document.querySelectorAll(`[data-nav-key="${activeKey}"]`).forEach((el, i) => {
      // first hit = desktop link, second = mobile link
      el.classList.add(...(i === 0 ? ACTIVE_DESKTOP : ACTIVE_MOBILE).split(' '));
    });
  }

  // ── 3. Mobile menu toggle ────────────────────────────────────────────────
  const mobileBtn  = document.getElementById('mobile-menu-btn');
  const mobileMenu = document.getElementById('mobile-menu');

  if (mobileBtn && mobileMenu) {
    mobileBtn.addEventListener('click', () => {
      const open = mobileMenu.classList.contains('opacity-100');
      if (open) {
        mobileMenu.classList.remove('opacity-100', 'visible', 'translate-y-0');
        mobileMenu.classList.add('opacity-0', 'invisible', 'translate-y-[-10px]');
        mobileBtn.textContent = 'menu';
      } else {
        mobileMenu.classList.remove('opacity-0', 'invisible', 'translate-y-[-10px]');
        mobileMenu.classList.add('opacity-100', 'visible', 'translate-y-0');
        mobileBtn.textContent = 'close';
      }
    });
  }

  // ── 4. Auth state ────────────────────────────────────────────────────────
  function showLoggedIn(user) {
    const roleLabel = user.role.charAt(0).toUpperCase() + user.role.slice(1);

    // Route profile links to the right page based on role
    const profileHref = user.role === 'admin'
      ? 'admindashboard.html'
      : user.role === 'professional'
        ? 'professional-profile.html'
        : 'customer-profile.html';

    // Desktop
    const userArea    = document.getElementById('desktop-user-area');
    const accountIcon = document.getElementById('desktop-account-icon');
    const signinLink  = document.getElementById('desktop-signin-link');
    if (userArea)    { userArea.style.display    = 'flex'; }
    if (accountIcon) { accountIcon.style.display = 'none'; }
    if (signinLink)  { signinLink.style.display  = 'none'; }
    const emailEl = document.getElementById('desktop-user-email');
    const roleEl  = document.getElementById('desktop-user-role');
    if (emailEl) emailEl.textContent = user.email.split('@')[0];
    if (roleEl)  roleEl.textContent  = roleLabel;

    // Point the desktop profile card link to the correct profile page
    if (userArea) {
      const desktopProfileLink = userArea.querySelector('a[href]');
      if (desktopProfileLink) desktopProfileLink.href = profileHref;
    }

    // Also update the logged-out account icon so it routes correctly after JS runs
    if (accountIcon) accountIcon.href = profileHref;

    // Give professional accounts a purple-tinted role pill
    if (user.role === 'professional' && roleEl) {
      roleEl.style.cssText +=
        ';background:rgba(188,19,254,0.15);color:#ebb2ff;border:1px solid rgba(188,19,254,0.3);border-radius:9999px;padding:2px 8px;';
    }

    // Mobile
    const mobileUserArea   = document.getElementById('mobile-user-area');
    const mobileSignoutArea = document.getElementById('mobile-signout-area');
    if (mobileUserArea)    { mobileUserArea.style.display    = 'flex'; }
    if (mobileSignoutArea) { mobileSignoutArea.style.display = 'none'; }
    const mobileEmail = document.getElementById('mobile-user-email');
    const mobileRole  = document.getElementById('mobile-user-role');
    if (mobileEmail) mobileEmail.textContent = user.email;
    if (mobileRole)  mobileRole.textContent  = roleLabel;

    // Point the mobile profile card link to the correct profile page
    if (mobileUserArea) {
      const mobileProfileLink = mobileUserArea.querySelector('a[href]');
      if (mobileProfileLink) mobileProfileLink.href = profileHref;
    }

    // Dispatch event so page scripts can react
    document.dispatchEvent(new CustomEvent('camcrew:auth', { detail: { user } }));
  }

  try {
    const res  = await fetch('/api/me');
    const data = await res.json();
    if (data.ok) showLoggedIn(data.user);
  } catch (_) { /* offline or network error — leave logged-out UI */ }

  // ── 5. Cart badge ────────────────────────────────────────────────────────
  function setCartBadge(count) {
    ['cart-badge', 'cart-badge-mobile'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      if (count > 0) {
        el.textContent = count > 99 ? '99+' : count;
        el.style.display = 'block';
      } else {
        el.style.display = 'none';
      }
    });
  }

  // Expose so cart.html and other pages can update the badge immediately
  window.updateCartBadge = setCartBadge;

  // Fetch cart count on every page load (only when logged in)
  try {
    const cartRes = await fetch('/api/cart');
    if (cartRes.ok) {
      const cartData = await cartRes.json();
      if (cartData.ok) setCartBadge(cartData.count);
    }
  } catch (_) { /* ignore */ }

  // ── 6. Global sign-out ───────────────────────────────────────────────────
  window.signOut = async function () {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = 'signin.html';
  };

})();
