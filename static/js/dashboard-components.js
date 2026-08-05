/**
 * dashboard-components.js
 * Shared loader + interactive behaviors for all admin dashboard pages.
 * Loads sidebar (dashboard-sidebar.html) and footer (dashboard-footer.html),
 * sets the active nav item, and wires up page-specific interactions.
 */

(function () {
  'use strict';

  /* ─────────────────────────────────────────────
     1. SIDEBAR & FOOTER LOADER
  ───────────────────────────────────────────── */
  function loadFragment(url, containerId, cb) {
    const container = document.getElementById(containerId);
    if (!container) return;
    fetch(url)
      .then(r => r.text())
      .then(html => {
        container.innerHTML = html;
        if (cb) cb();
      })
      .catch(err => console.warn('Could not load ' + url, err));
  }

  function setActiveNav() {
    const page = window.location.pathname.split('/').pop() || 'admindashboard.html';
    document.querySelectorAll('[data-nav]').forEach(link => {
      const key = link.getAttribute('data-nav');
      const active = (
        (key === 'dashboard'      && page === 'admindashboard.html') ||
        (key === 'inventory'      && page === 'inventory.html') ||
        (key === 'orders'         && page === 'orders.html') ||
        (key === 'verification'   && page === 'verificationrequest.html') ||
        (key === 'subscriptions'  && page === 'subscriptionmanagement.html')
      );
      if (active) {
        link.classList.remove('text-on-surface-variant', 'hover:text-on-surface', 'hover:bg-white/5');
        link.classList.add('text-primary-container', 'bg-primary-container/10', 'font-semibold');
      }
    });
  }

  function initSidebar() {
    setActiveNav();
    // Mobile sidebar open/close (functions referenced by onclick in HTML)
    window.openSidebar = function () {
      const sidebar = document.getElementById('sidebar');
      const overlay = document.getElementById('sidebar-overlay');
      if (sidebar)  sidebar.classList.remove('-translate-x-full');
      if (overlay)  overlay.classList.remove('hidden');
    };
    window.closeSidebar = function () {
      const sidebar = document.getElementById('sidebar');
      const overlay = document.getElementById('sidebar-overlay');
      if (sidebar)  sidebar.classList.add('-translate-x-full');
      if (overlay)  overlay.classList.add('hidden');
    };
    window.adminSignOut = async function () {
      showToast('Signing out…', 'info');
      try {
        const res = await fetch('/api/logout', {
          method: 'POST',
          credentials: 'include'
        });
        if (res.ok || res.status === 401 || res.status === 403) {
          window.location.href = 'adminlogin.html';
        } else {
          showToast('Logout failed. Please try again.', 'error');
        }
      } catch (err) {
        showToast('Network error. Please check your connection.', 'error');
      }
    };
  }

  /* ─────────────────────────────────────────────
     2. TOAST NOTIFICATION
  ───────────────────────────────────────────── */
  function showToast(msg, type) {
    type = type || 'success';
    let toast = document.getElementById('dc-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'dc-toast';
      toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);z-index:9999;padding:12px 24px;border-radius:12px;font-size:13px;font-weight:700;letter-spacing:.05em;transition:transform .35s cubic-bezier(.34,1.56,.64,1),opacity .35s;opacity:0;pointer-events:none;border:1px solid;max-width:90vw;text-align:center;backdrop-filter:blur(20px);';
      document.body.appendChild(toast);
    }
    const colors = {
      success : { bg:'rgba(0,240,255,0.12)',  border:'rgba(0,240,255,0.35)',  text:'#00f0ff' },
      error   : { bg:'rgba(255,180,171,0.12)',border:'rgba(255,180,171,0.35)',text:'#ffb4ab' },
      info    : { bg:'rgba(235,178,255,0.12)',border:'rgba(235,178,255,0.35)',text:'#ebb2ff' },
      warn    : { bg:'rgba(251,191,36,0.12)', border:'rgba(251,191,36,0.35)', text:'#fbbf24' },
    };
    const c = colors[type] || colors.success;
    toast.style.background = c.bg;
    toast.style.borderColor = c.border;
    toast.style.color = c.text;
    toast.textContent = msg;
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(-50%) translateY(0)';
    });
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(-50%) translateY(80px)';
    }, 3000);
  }
  window.showToast = showToast; // expose globally

  /* ─────────────────────────────────────────────
     3. MODAL HELPER
  ───────────────────────────────────────────── */
  function createModal(id, html) {
    let modal = document.getElementById(id);
    if (!modal) {
      modal = document.createElement('div');
      modal.id = id;
      modal.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4';
      modal.style.cssText = 'display:none;';
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="document.getElementById('${id}').style.display='none'"></div>
      <div class="relative glass-panel rounded-2xl max-w-lg w-full p-8 z-10 shadow-2xl" style="background:rgba(22,22,24,0.97);border:1px solid rgba(255,255,255,0.15);">
        ${html}
      </div>`;
    modal.style.display = 'flex';
  }

  /* ─────────────────────────────────────────────
     4. PAGE: ADMIN DASHBOARD
  ───────────────────────────────────────────── */
  function initDashboard() {
    // Commerce Hub tab switching
    const tabBtns = document.querySelectorAll('[data-tab-btn]');
    const tabPanels = document.querySelectorAll('[data-tab-panel]');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-tab-btn');
        tabBtns.forEach(b => {
          b.classList.remove('text-primary', 'border-b-2', 'border-primary-container');
          b.classList.add('text-on-surface-variant');
        });
        btn.classList.add('text-primary', 'border-b-2', 'border-primary-container');
        btn.classList.remove('text-on-surface-variant');
        tabPanels.forEach(p => {
          p.style.display = p.getAttribute('data-tab-panel') === target ? '' : 'none';
        });
      });
    });

    // Approve / Deny in verification queue
    document.querySelectorAll('[data-action="approve"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const card = btn.closest('[data-studio-card]');
        const name = card ? card.getAttribute('data-studio-card') : 'Studio';
        card && (card.style.transition = 'opacity .4s', card.style.opacity = '0', setTimeout(() => card.remove(), 400));
        showToast(`✓ ${name} approved successfully`, 'success');
        updatePendingBadge(-1);
      });
    });
    document.querySelectorAll('[data-action="deny"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const card = btn.closest('[data-studio-card]');
        const name = card ? card.getAttribute('data-studio-card') : 'Studio';
        card && (card.style.transition = 'opacity .4s', card.style.opacity = '0', setTimeout(() => card.remove(), 400));
        showToast(`${name} request denied`, 'error');
        updatePendingBadge(-1);
      });
    });

    function updatePendingBadge(delta) {
      const badge = document.querySelector('[data-pending-badge]');
      if (badge) {
        const n = Math.max(0, (parseInt(badge.textContent) || 0) + delta);
        badge.textContent = n + ' PENDING';
      }
    }

    // Refresh button
    const refreshBtn = document.querySelector('[data-action="refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        refreshBtn.querySelector('span').style.animation = 'spin 1s linear';
        setTimeout(() => refreshBtn.querySelector('span').style.animation = '', 1000);
        showToast('Metrics refreshed', 'info');
      });
    }

    // "VIEW ALL PENDING REQUESTS" button
    document.querySelectorAll('[data-link="verificationrequest"]').forEach(el => {
      el.addEventListener('click', () => { window.location.href = 'verificationrequest.html'; });
      el.style.cursor = 'pointer';
    });

    // "VIEW REVENUE REPORT" button
    document.querySelectorAll('[data-link="subscriptionmanagement"]').forEach(el => {
      el.addEventListener('click', () => { window.location.href = 'subscriptionmanagement.html'; });
      el.style.cursor = 'pointer';
    });
  }

  /* ─────────────────────────────────────────────
     5. PAGE: VERIFICATION REQUEST
  ───────────────────────────────────────────── */
  function initVerification() {
    let pendingCount = parseInt(document.querySelector('[data-pending-count]')?.textContent) || 24;

    function removeRow(row, name, type) {
      row.style.transition = 'opacity .4s, background .4s';
      row.style.opacity = '0';
      row.style.background = type === 'approve' ? 'rgba(0,240,255,0.06)' : 'rgba(255,180,171,0.06)';
      setTimeout(() => {
        row.remove();
        pendingCount = Math.max(0, pendingCount - 1);
        const countEl = document.querySelector('[data-pending-count]');
        if (countEl) countEl.textContent = pendingCount;
        const showingEl = document.querySelector('[data-showing-count]');
        if (showingEl) {
          const showing = document.querySelectorAll('tbody tr').length;
          showingEl.textContent = `1-${showing} of ${pendingCount} pending requests`;
        }
      }, 400);
    }

    document.querySelectorAll('[data-verify-approve]').forEach(btn => {
      btn.addEventListener('click', () => {
        const row = btn.closest('tr');
        const name = row.querySelector('[data-studio-name]')?.textContent || 'Studio';
        removeRow(row, name, 'approve');
        showToast(`✓ ${name} approved & access granted`, 'success');
      });
    });

    document.querySelectorAll('[data-verify-reject]').forEach(btn => {
      btn.addEventListener('click', () => {
        const row = btn.closest('tr');
        const name = row.querySelector('[data-studio-name]')?.textContent || 'Studio';
        createModal('verify-reject-modal', `
          <h3 class="text-lg font-bold text-on-surface mb-2">Reject Application</h3>
          <p class="text-on-surface-variant text-sm mb-6">Reject <strong class="text-error">${name}</strong>? This action will deny their partnership request.</p>
          <div class="flex gap-3 justify-end">
            <button onclick="document.getElementById('verify-reject-modal').style.display='none'" class="px-4 py-2 rounded-lg border border-glass-stroke text-on-surface-variant hover:text-on-surface transition-colors text-sm font-bold">Cancel</button>
            <button id="confirm-reject-btn" class="px-4 py-2 rounded-lg bg-error/20 text-error border border-error/30 hover:bg-error/30 transition-colors text-sm font-bold">Reject Application</button>
          </div>`);
        document.getElementById('confirm-reject-btn').onclick = () => {
          document.getElementById('verify-reject-modal').style.display = 'none';
          removeRow(row, name, 'reject');
          showToast(`${name} application rejected`, 'error');
        };
      });
    });

    // View Profile — show detail panel
    document.querySelectorAll('[data-view-profile]').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const row = link.closest('tr');
        const name = row.querySelector('[data-studio-name]')?.textContent || 'Studio';
        const rep  = row.querySelector('[data-rep-name]')?.textContent || '—';
        const loc  = row.querySelector('[data-location]')?.textContent || '—';
        createModal('profile-modal', `
          <div class="flex items-center gap-4 mb-6">
            <div class="w-14 h-14 rounded-xl bg-primary-container/10 border border-primary-container/30 flex items-center justify-center text-primary-container font-bold text-xl">${name.charAt(0)}</div>
            <div><h3 class="text-xl font-bold text-on-surface">${name}</h3><p class="text-on-surface-variant text-sm">${rep}</p></div>
          </div>
          <div class="space-y-3 text-sm mb-6">
            <div class="flex justify-between border-b border-glass-stroke pb-2"><span class="text-on-surface-variant">Location</span><span class="text-on-surface font-medium">${loc}</span></div>
            <div class="flex justify-between border-b border-glass-stroke pb-2"><span class="text-on-surface-variant">Status</span><span class="text-amber-400 font-bold">Pending Review</span></div>
            <div class="flex justify-between"><span class="text-on-surface-variant">Documents</span><span class="text-primary-container font-bold cursor-pointer hover:underline">View Portfolio</span></div>
          </div>
          <button onclick="document.getElementById('profile-modal').style.display='none'" class="w-full py-2.5 rounded-xl border border-glass-stroke text-on-surface-variant hover:text-primary-container hover:border-primary-container/50 transition-all text-sm font-bold">Close</button>`);
      });
    });

    // Pagination
    document.querySelectorAll('[data-page-btn]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-page-btn]').forEach(b => {
          b.classList.remove('bg-primary-container', 'text-obsidian-base');
          b.classList.add('border', 'border-glass-stroke', 'text-on-surface-variant');
        });
        btn.classList.add('bg-primary-container', 'text-obsidian-base');
        btn.classList.remove('border', 'border-glass-stroke', 'text-on-surface-variant');
        showToast(`Page ${btn.textContent}`, 'info');
      });
    });
  }

  /* ─────────────────────────────────────────────
     6. PAGE: SUBSCRIPTION MANAGEMENT
  ───────────────────────────────────────────── */
  function initSubscriptions() {
    // Tier filter
    const tierFilter = document.querySelector('[data-tier-filter]');
    if (tierFilter) {
      tierFilter.addEventListener('change', () => {
        const val = tierFilter.value.toLowerCase();
        document.querySelectorAll('[data-sub-row]').forEach(row => {
          const tier = (row.getAttribute('data-sub-tier') || '').toLowerCase();
          row.style.display = (!val || val === 'all tiers' || tier.includes(val)) ? '' : 'none';
        });
        showToast(`Filtered: ${tierFilter.value}`, 'info');
      });
    }

    // Actions dropdown (more_vert)
    document.querySelectorAll('[data-sub-menu]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const row   = btn.closest('tr') || btn.closest('[data-sub-row]');
        const name  = row?.querySelector('[data-sub-name]')?.textContent || 'Subscriber';
        const tier  = row?.getAttribute('data-sub-tier') || 'Subscription';
        createModal('sub-action-modal', `
          <h3 class="text-lg font-bold text-on-surface mb-1">${name}</h3>
          <p class="text-on-surface-variant text-xs mb-6 uppercase tracking-widest">${tier}</p>
          <div class="space-y-2">
            <button onclick="document.getElementById('sub-action-modal').style.display='none';showToast('${name} subscription renewed','success')" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-primary-container/10 text-on-surface hover:text-primary-container transition-all text-sm font-bold text-left">
              <span class="material-symbols-outlined text-[18px]">autorenew</span> Renew Subscription
            </button>
            <button onclick="document.getElementById('sub-action-modal').style.display='none';showToast('Upgrade options sent to ${name}','info')" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-secondary/10 text-on-surface hover:text-secondary transition-all text-sm font-bold text-left">
              <span class="material-symbols-outlined text-[18px]">upgrade</span> Change Tier
            </button>
            <button onclick="document.getElementById('sub-action-modal').style.display='none';showToast('Invoice sent to ${name}','info')" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/5 text-on-surface transition-all text-sm font-bold text-left">
              <span class="material-symbols-outlined text-[18px]">receipt</span> Send Invoice
            </button>
            <button onclick="document.getElementById('sub-action-modal').style.display='none';showToast('${name} subscription cancelled','error')" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-error/10 text-error transition-all text-sm font-bold text-left">
              <span class="material-symbols-outlined text-[18px]">cancel</span> Cancel Subscription
            </button>
          </div>
          <button onclick="document.getElementById('sub-action-modal').style.display='none'" class="mt-4 w-full py-2 rounded-xl border border-glass-stroke text-on-surface-variant text-sm hover:text-on-surface transition-colors">Close</button>`);
      });
    });

    // FAB — Add new subscription
    const fab = document.querySelector('[data-fab="new-subscription"]');
    if (fab) {
      fab.addEventListener('click', () => {
        createModal('new-sub-modal', `
          <h3 class="text-lg font-bold text-on-surface mb-6">New Subscription</h3>
          <div class="space-y-4">
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">Studio / User Name</label>
              <input type="text" placeholder="e.g. Neon Pulse Studios" class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface"></div>
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">Email</label>
              <input type="email" placeholder="billing@studio.com" class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface"></div>
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">Tier</label>
              <select class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface">
                <option>Professional</option><option>Elite</option><option>Studio Enterprise</option>
              </select></div>
          </div>
          <div class="flex gap-3 mt-6 justify-end">
            <button onclick="document.getElementById('new-sub-modal').style.display='none'" class="px-4 py-2 rounded-lg border border-glass-stroke text-on-surface-variant hover:text-on-surface transition-colors text-sm font-bold">Cancel</button>
            <button onclick="document.getElementById('new-sub-modal').style.display='none';showToast('New subscription created','success')" class="px-4 py-2 rounded-lg bg-primary-container/20 text-primary-container border border-primary-container/30 hover:bg-primary-container/30 transition-colors text-sm font-bold">Create</button>
          </div>`);
      });
    }

    // Export CSV
    const exportBtn = document.querySelector('[data-action="export-csv"]');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => showToast('CSV export started…', 'info'));
    }

    // Pagination
    document.querySelectorAll('[data-sub-page]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-sub-page]').forEach(b => {
          b.classList.remove('bg-primary-container/10', 'text-primary-container', 'border-primary-container/30');
          b.classList.add('bg-glass-stroke/10', 'border-glass-stroke');
        });
        btn.classList.add('bg-primary-container/10', 'text-primary-container', 'border-primary-container/30');
        btn.classList.remove('bg-glass-stroke/10', 'border-glass-stroke');
        showToast(`Page ${btn.textContent}`, 'info');
      });
    });
  }

  /* ─────────────────────────────────────────────
     7. PAGE: ORDERS
  ───────────────────────────────────────────── */
  function initOrders() {
    // Status filter
    const statusFilter = document.querySelector('[data-status-filter]');
    if (statusFilter) {
      statusFilter.addEventListener('change', () => {
        const val = statusFilter.value.toLowerCase();
        document.querySelectorAll('[data-order-row]').forEach(row => {
          const status = (row.getAttribute('data-order-status') || '').toLowerCase();
          row.style.display = (!val || val === 'all statuses' || status === val) ? '' : 'none';
        });
        showToast(`Filtered: ${statusFilter.value}`, 'info');
      });
    }

    // Date range filter
    const dateFilter = document.querySelector('[data-date-filter]');
    if (dateFilter) {
      dateFilter.addEventListener('change', () => showToast(`Date range: ${dateFilter.value}`, 'info'));
    }

    // View Details
    document.querySelectorAll('[data-order-details]').forEach(btn => {
      btn.addEventListener('click', () => {
        const row   = btn.closest('tr') || btn.closest('[data-order-row]');
        const oid   = row?.querySelector('[data-order-id]')?.textContent || '—';
        const cust  = row?.querySelector('[data-customer-name]')?.textContent?.trim() || '—';
        const date  = row?.querySelector('[data-order-date]')?.textContent || '—';
        const amt   = row?.querySelector('[data-order-amount]')?.textContent || '—';
        const stat  = row?.querySelector('[data-order-status-label]')?.textContent?.trim() || '—';
        createModal('order-detail-modal', `
          <div class="flex items-center justify-between mb-6">
            <div><h3 class="text-xl font-bold text-on-surface">${oid}</h3><p class="text-on-surface-variant text-xs mt-0.5">${date}</p></div>
            <span class="px-3 py-1 rounded-full text-[10px] font-bold bg-primary-container/10 text-primary-container border border-primary-container/20">${stat}</span>
          </div>
          <div class="space-y-3 text-sm mb-6">
            <div class="flex justify-between border-b border-glass-stroke pb-2"><span class="text-on-surface-variant">Customer</span><span class="text-on-surface font-bold">${cust}</span></div>
            <div class="flex justify-between border-b border-glass-stroke pb-2"><span class="text-on-surface-variant">Amount</span><span class="text-primary-container font-bold">${amt}</span></div>
            <div class="flex justify-between border-b border-glass-stroke pb-2"><span class="text-on-surface-variant">Payment</span><span class="text-emerald-400 font-bold">Cleared</span></div>
            <div class="flex justify-between"><span class="text-on-surface-variant">Shipping</span><span class="text-on-surface font-medium">Standard Express — 3-5 days</span></div>
          </div>
          <div class="flex gap-3">
            <button onclick="showToast('Invoice sent','success');document.getElementById('order-detail-modal').style.display='none'" class="flex-1 py-2.5 rounded-xl bg-primary-container/20 text-primary-container border border-primary-container/30 hover:bg-primary-container/30 transition-all text-sm font-bold">Send Invoice</button>
            <button onclick="document.getElementById('order-detail-modal').style.display='none'" class="flex-1 py-2.5 rounded-xl border border-glass-stroke text-on-surface-variant hover:text-on-surface transition-all text-sm font-bold">Close</button>
          </div>`);
      });
    });

    // Export
    const exportBtn = document.querySelector('[data-action="export"]');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => showToast('Exporting order data…', 'info'));
    }

    // Pagination
    document.querySelectorAll('[data-order-page]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-order-page]').forEach(b => {
          b.classList.remove('bg-primary-container', 'text-obsidian-base');
          b.classList.add('bg-glass-stroke/10', 'text-on-surface-variant');
        });
        btn.classList.add('bg-primary-container', 'text-obsidian-base');
        btn.classList.remove('bg-glass-stroke/10', 'text-on-surface-variant');
        showToast(`Page ${btn.textContent}`, 'info');
      });
    });
  }

  /* ─────────────────────────────────────────────
     8. PAGE: INVENTORY
  ───────────────────────────────────────────── */
  function initInventory() {
    // Category + status filter
    const catFilter    = document.querySelector('[data-cat-filter]');
    const statusFilter = document.querySelector('[data-inv-status-filter]');

    function applyFilters() {
      const cat    = (catFilter?.value || '').toLowerCase();
      const status = (statusFilter?.value || '').toLowerCase();
      document.querySelectorAll('[data-inv-row]').forEach(row => {
        const rowCat    = (row.getAttribute('data-inv-cat') || '').toLowerCase();
        const rowStatus = (row.getAttribute('data-inv-status') || '').toLowerCase();
        const matchCat    = !cat    || cat    === 'all categories'  || rowCat.includes(cat);
        const matchStatus = !status || status === 'status: any'     || rowStatus.includes(status.replace('status: ', ''));
        row.style.display = (matchCat && matchStatus) ? '' : 'none';
      });
    }
    if (catFilter)    catFilter.addEventListener('change',    () => { applyFilters(); showToast(`Category: ${catFilter.value}`, 'info'); });
    if (statusFilter) statusFilter.addEventListener('change', () => { applyFilters(); showToast(`Status: ${statusFilter.value}`, 'info'); });

    // Search
    const searchInput = document.querySelector('[data-inv-search]');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        const q = searchInput.value.toLowerCase();
        document.querySelectorAll('[data-inv-row]').forEach(row => {
          const text = row.textContent.toLowerCase();
          row.style.display = text.includes(q) ? '' : 'none';
        });
      });
    }

    // Edit
    document.querySelectorAll('[data-inv-edit]').forEach(btn => {
      btn.addEventListener('click', () => {
        const row  = btn.closest('tr') || btn.closest('[data-inv-row]');
        const name = row?.querySelector('[data-inv-name]')?.textContent?.trim() || 'Item';
        const sku  = row?.querySelector('[data-inv-sku]')?.textContent?.trim() || '';
        const price= row?.querySelector('[data-inv-price]')?.textContent?.trim() || '';
        createModal('inv-edit-modal', `
          <h3 class="text-lg font-bold text-on-surface mb-6">Edit Item</h3>
          <div class="space-y-4">
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">Item Name</label>
              <input type="text" value="${name}" id="edit-name" class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface"></div>
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">SKU</label>
              <input type="text" value="${sku}" class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface font-mono"></div>
            <div><label class="text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">Unit Price</label>
              <input type="text" value="${price}" class="w-full bg-obsidian-base/60 border border-glass-stroke rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-container text-on-surface"></div>
          </div>
          <div class="flex gap-3 mt-6 justify-end">
            <button onclick="document.getElementById('inv-edit-modal').style.display='none'" class="px-4 py-2 rounded-lg border border-glass-stroke text-on-surface-variant hover:text-on-surface transition-colors text-sm font-bold">Cancel</button>
            <button onclick="document.getElementById('inv-edit-modal').style.display='none';showToast('Item updated','success')" class="px-4 py-2 rounded-lg bg-primary-container/20 text-primary-container border border-primary-container/30 hover:bg-primary-container/30 transition-colors text-sm font-bold">Save Changes</button>
          </div>`);
      });
    });

    // Delete
    document.querySelectorAll('[data-inv-delete]').forEach(btn => {
      btn.addEventListener('click', () => {
        const row  = btn.closest('tr') || btn.closest('[data-inv-row]');
        const name = row?.querySelector('[data-inv-name]')?.textContent?.trim() || 'Item';
        createModal('inv-delete-modal', `
          <h3 class="text-lg font-bold text-on-surface mb-2">Delete Item</h3>
          <p class="text-on-surface-variant text-sm mb-6">Permanently delete <strong class="text-error">${name}</strong> from inventory? This cannot be undone.</p>
          <div class="flex gap-3 justify-end">
            <button onclick="document.getElementById('inv-delete-modal').style.display='none'" class="px-4 py-2 rounded-lg border border-glass-stroke text-on-surface-variant hover:text-on-surface transition-colors text-sm font-bold">Cancel</button>
            <button id="confirm-delete-btn" class="px-4 py-2 rounded-lg bg-error/20 text-error border border-error/30 hover:bg-error/30 transition-colors text-sm font-bold">Delete Item</button>
          </div>`);
        document.getElementById('confirm-delete-btn').onclick = () => {
          document.getElementById('inv-delete-modal').style.display = 'none';
          row.style.transition = 'opacity .4s'; row.style.opacity = '0';
          setTimeout(() => row.remove(), 400);
          showToast(`${name} removed from inventory`, 'error');
        };
      });
    });

    // Add New Item — handled by inventory.html's own neumorphism modal

    // FAB also triggers add
    const fab = document.querySelector('[data-fab="add-item"]');
    if (fab) fab.addEventListener('click', () => document.querySelector('[data-action="add-item"]')?.click());
  }

  /* ─────────────────────────────────────────────
     9. INIT — detect page & run
  ───────────────────────────────────────────── */
  function init() {
    const page = window.location.pathname.split('/').pop() || 'admindashboard.html';

    // Load sidebar, then init nav + page logic
    loadFragment('dashboard-sidebar.html', 'sidebar-container', () => {
      initSidebar();
    });

    // Load footer
    loadFragment('dashboard-footer.html', 'footer-container');

    // Page-specific init (can run immediately, before sidebar loads)
    if (page === 'admindashboard.html' || page === '')    initDashboard();
    if (page === 'verificationrequest.html')               initVerification();
    if (page === 'subscriptionmanagement.html')            initSubscriptions();
    if (page === 'orders.html')                            initOrders();
    if (page === 'inventory.html')                         initInventory();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
