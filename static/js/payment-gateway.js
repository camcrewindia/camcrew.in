/* ═══════════════════════════════════════════════════════════════════
   CamCrew Studio — Interactive Escrow Payment Gateway Modal
   Supports UPI (GPay/PhonePe/Paytm), Cards, NetBanking & Razorpay
   ═══════════════════════════════════════════════════════════════════ */

(function() {
  function injectPaymentModalHTML() {
    if (document.getElementById('cc-payment-modal')) return;

    const modalHTML = `
    <div id="cc-payment-modal" style="display:none;position:fixed;inset:0;z-index:9999;background:rgba(4,10,11,0.85);backdrop-filter:blur(10px);align-items:center;justify-content:center;padding:1rem;">
      <div class="cc-payment-card" style="background:#0e1217;border:1px solid rgba(0,219,233,0.25);border-radius:1.5rem;padding:2rem;width:100%;max-width:480px;box-shadow:0 32px 80px rgba(0,0,0,0.8);position:relative;color:#dce4e5;font-family:'Plus Jakarta Sans',sans-serif;">
        
        <button type="button" onclick="window.closeCamCrewPaymentGateway()" style="position:absolute;top:1rem;right:1rem;background:none;border:none;color:#849495;font-size:1.2rem;cursor:pointer;line-height:1;">✕</button>

        <!-- Header -->
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;">
          <div style="width:2.5rem;height:2.5rem;border-radius:0.75rem;background:rgba(0,219,233,0.12);border:1px solid rgba(0,219,233,0.3);display:flex;align-items:center;justify-content:center;color:#00dbe9;">
            <span class="material-symbols-outlined" style="font-size:1.4rem;">lock</span>
          </div>
          <div>
            <h3 id="cc-pay-title" style="font-size:1.1rem;font-weight:900;color:#f0f6f7;margin:0;">CamCrew Escrow Checkout</h3>
            <p id="cc-pay-subtitle" style="font-size:0.75rem;color:#849495;margin:0.1rem 0 0 0;">100% Buyer Protection &amp; Escrow Guarantee</p>
          </div>
        </div>

        <!-- Amount Box -->
        <div style="background:rgba(0,219,233,0.06);border:1px solid rgba(0,219,233,0.2);border-radius:0.85rem;padding:0.85rem 1.1rem;display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;">
          <div>
            <span style="font-size:0.7rem;font-weight:800;letter-spacing:0.08em;color:#00dbe9;text-transform:uppercase;display:block;">Total Payable Amount</span>
            <span style="font-size:0.72rem;color:#849495;">Funds locked in Escrow</span>
          </div>
          <span id="cc-pay-amount" style="font-size:1.4rem;font-weight:900;color:#00dbe9;">₹0</span>
        </div>

        <!-- Payment Tabs -->
        <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:0.35rem;background:#14181f;border:1px solid rgba(255,255,255,0.08);border-radius:0.75rem;padding:0.3rem;margin-bottom:1.25rem;">
          <button type="button" class="cc-pay-tab active" data-tab="upi" onclick="window.switchCcPayTab('upi')" style="padding:0.5rem 0.2rem;border:none;border-radius:0.5rem;font-size:0.72rem;font-weight:800;cursor:pointer;background:rgba(0,219,233,0.2);color:#00dbe9;">📱 UPI</button>
          <button type="button" class="cc-pay-tab" data-tab="card" onclick="window.switchCcPayTab('card')" style="padding:0.5rem 0.2rem;border:none;border-radius:0.5rem;font-size:0.72rem;font-weight:800;cursor:pointer;background:transparent;color:#849495;">💳 Card</button>
          <button type="button" class="cc-pay-tab" data-tab="netbanking" onclick="window.switchCcPayTab('netbanking')" style="padding:0.5rem 0.2rem;border:none;border-radius:0.5rem;font-size:0.72rem;font-weight:800;cursor:pointer;background:transparent;color:#849495;">🏦 NetBank</button>
          <button type="button" class="cc-pay-tab" data-tab="razorpay" onclick="window.switchCcPayTab('razorpay')" style="padding:0.5rem 0.2rem;border:none;border-radius:0.5rem;font-size:0.72rem;font-weight:800;cursor:pointer;background:transparent;color:#849495;">⚡ Razorpay</button>
        </div>

        <!-- Tab 1: UPI -->
        <div id="cc-pay-panel-upi" class="cc-pay-panel" style="display:block;">
          <label style="font-size:0.72rem;font-weight:700;color:#849495;text-transform:uppercase;letter-spacing:0.06em;display:block;margin-bottom:0.4rem;">Select UPI Application or Enter VPA</label>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:0.85rem;">
            <button type="button" onclick="selectUpiApp('gpay')" id="upi-btn-gpay" style="padding:0.6rem;border-radius:0.6rem;background:rgba(255,255,255,0.04);border:1px solid rgba(0,219,233,0.3);color:#dce4e5;font-weight:700;font-size:0.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:0.35rem;">
              🔵 Google Pay
            </button>
            <button type="button" onclick="selectUpiApp('phonepe')" id="upi-btn-phonepe" style="padding:0.6rem;border-radius:0.6rem;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);color:#dce4e5;font-weight:700;font-size:0.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:0.35rem;">
              🟣 PhonePe
            </button>
            <button type="button" onclick="selectUpiApp('paytm')" id="upi-btn-paytm" style="padding:0.6rem;border-radius:0.6rem;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);color:#dce4e5;font-weight:700;font-size:0.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:0.35rem;">
              🔷 Paytm UPI
            </button>
            <button type="button" onclick="selectUpiApp('bhim')" id="upi-btn-bhim" style="padding:0.6rem;border-radius:0.6rem;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);color:#dce4e5;font-weight:700;font-size:0.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:0.35rem;">
              🇮🇳 BHIM UPI
            </button>
          </div>
          <div>
            <label style="font-size:0.7rem;color:#849495;display:block;margin-bottom:0.25rem;">UPI ID / VPA</label>
            <input type="text" id="cc-upi-id" value="customer@okaxis" placeholder="username@upi / mobile@ybl" style="width:100%;background:#14181f;border:1px solid rgba(255,255,255,0.1);border-radius:0.65rem;padding:0.65rem 0.85rem;color:#dce4e5;font-size:0.85rem;outline:none;">
          </div>
        </div>

        <!-- Tab 2: Card -->
        <div id="cc-pay-panel-card" class="cc-pay-panel" style="display:none;">
          <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <div>
              <label style="font-size:0.7rem;color:#849495;display:block;margin-bottom:0.25rem;">Card Number</label>
              <input type="text" id="cc-card-no" placeholder="4532 •••• •••• 8910" style="width:100%;background:#14181f;border:1px solid rgba(255,255,255,0.1);border-radius:0.65rem;padding:0.65rem 0.85rem;color:#dce4e5;font-size:0.85rem;outline:none;">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;">
              <div>
                <label style="font-size:0.7rem;color:#849495;display:block;margin-bottom:0.25rem;">Expiry (MM/YY)</label>
                <input type="text" id="cc-card-exp" placeholder="12/28" style="width:100%;background:#14181f;border:1px solid rgba(255,255,255,0.1);border-radius:0.65rem;padding:0.65rem 0.85rem;color:#dce4e5;font-size:0.85rem;outline:none;">
              </div>
              <div>
                <label style="font-size:0.7rem;color:#849495;display:block;margin-bottom:0.25rem;">CVV / CVC</label>
                <input type="password" id="cc-card-cvv" placeholder="•••" maxlength="4" style="width:100%;background:#14181f;border:1px solid rgba(255,255,255,0.1);border-radius:0.65rem;padding:0.65rem 0.85rem;color:#dce4e5;font-size:0.85rem;outline:none;">
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 3: NetBanking -->
        <div id="cc-pay-panel-netbanking" class="cc-pay-panel" style="display:none;">
          <label style="font-size:0.72rem;font-weight:700;color:#849495;text-transform:uppercase;letter-spacing:0.06em;display:block;margin-bottom:0.4rem;">Select Bank</label>
          <select id="cc-netbank-select" style="width:100%;background:#14181f;border:1px solid rgba(255,255,255,0.1);border-radius:0.65rem;padding:0.65rem 0.85rem;color:#dce4e5;font-size:0.85rem;outline:none;">
            <option value="HDFC Bank">HDFC Bank</option>
            <option value="ICICI Bank">ICICI Bank</option>
            <option value="State Bank of India">State Bank of India (SBI)</option>
            <option value="Axis Bank">Axis Bank</option>
            <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
          </select>
        </div>

        <!-- Tab 4: Razorpay Fast Checkout -->
        <div id="cc-pay-panel-razorpay" class="cc-pay-panel" style="display:none;">
          <div style="background:rgba(0,219,233,0.05);border:1px solid rgba(0,219,233,0.2);border-radius:0.75rem;padding:1rem;text-align:center;">
            <span class="material-symbols-outlined" style="font-size:2rem;color:#00dbe9;margin-bottom:0.25rem;">bolt</span>
            <p style="font-size:0.85rem;font-weight:800;color:#f0f6f7;margin:0;">Razorpay Express Escrow</p>
            <p style="font-size:0.75rem;color:#849495;margin-top:0.3rem;">Instant 1-Click Payment Authorization with 100% Escrow Protection Guarantee.</p>
          </div>
        </div>

        <!-- Error Msg -->
        <div id="cc-pay-err" style="display:none;color:#ffb4ab;font-size:0.78rem;font-weight:600;margin-top:0.85rem;text-align:center;"></div>

        <!-- Action Button -->
        <button type="button" id="cc-pay-submit-btn" onclick="window.submitCamCrewPayment()" style="width:100%;margin-top:1.25rem;padding:0.85rem;border-radius:0.75rem;border:none;background:#00dbe9;color:#001f22;font-weight:900;font-size:0.92rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:0.4rem;transition:all 0.2s;">
          <span class="material-symbols-outlined" style="font-size:1.1rem;">lock</span>
          <span id="cc-pay-submit-txt">Pay &amp; Lock Escrow</span>
        </button>

        <p style="font-size:0.68rem;color:#556669;text-align:center;margin-top:0.85rem;margin-bottom:0;">
          🔒 Encrypted 256-Bit TLS · Escrow Protected by CamCrew Studio
        </p>
      </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
  }

  let activeMethod = 'upi';
  let currentOptions = null;

  window.switchCcPayTab = function(tabName) {
    activeMethod = tabName;
    const isLight = document.documentElement.classList.contains('light') || document.documentElement.getAttribute('data-theme') === 'light';
    document.querySelectorAll('.cc-pay-tab').forEach(b => {
      const isAct = b.dataset.tab === tabName;
      if (isLight) {
        b.style.background = isAct ? 'rgba(14, 90, 111, 0.15)' : 'transparent';
        b.style.color = isAct ? '#0e5a6f' : '#475569';
      } else {
        b.style.background = isAct ? 'rgba(0, 219, 233, 0.2)' : 'transparent';
        b.style.color = isAct ? '#00dbe9' : '#849495';
      }
    });
    document.querySelectorAll('.cc-pay-panel').forEach(p => p.style.display = 'none');
    const target = document.getElementById('cc-pay-panel-' + tabName);
    if (target) target.style.display = 'block';
  };

  window.selectUpiApp = function(appName) {
    const upiIds = {
      gpay: 'customer@okaxis',
      phonepe: 'customer@ybl',
      paytm: 'customer@paytm',
      bhim: 'customer@upi'
    };
    const inp = document.getElementById('cc-upi-id');
    if (inp) inp.value = upiIds[appName] || 'customer@upi';
    const isLight = document.documentElement.classList.contains('light') || document.documentElement.getAttribute('data-theme') === 'light';
    document.querySelectorAll('[id^="upi-btn-"]').forEach(btn => {
      btn.style.borderColor = isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
    });
    const sel = document.getElementById('upi-btn-' + appName);
    if (sel) sel.style.borderColor = isLight ? '#0e5a6f' : '#00dbe9';
  };

  window.openCamCrewPaymentGateway = function(opts) {
    injectPaymentModalHTML();
    currentOptions = opts || {};
    const amount = Number(opts.amount || 0);

    const isLight = document.documentElement.classList.contains('light') || document.documentElement.getAttribute('data-theme') === 'light';

    document.getElementById('cc-pay-title').textContent = opts.title || 'CamCrew Escrow Checkout';
    document.getElementById('cc-pay-subtitle').textContent = opts.subtitle || '100% Buyer Protection & Escrow Guarantee';
    document.getElementById('cc-pay-amount').textContent = `₹${amount.toLocaleString('en-IN')}`;
    document.getElementById('cc-pay-err').style.display = 'none';
    
    const btn = document.getElementById('cc-pay-submit-btn');
    btn.disabled = false;

    // Style submit button based on theme
    if (isLight) {
      btn.style.background = '#0e5a6f';
      btn.style.color = '#ffffff';
    } else {
      btn.style.background = '#00dbe9';
      btn.style.color = '#001f22';
    }

    document.getElementById('cc-pay-submit-txt').textContent = `Pay ₹${amount.toLocaleString('en-IN')} & Lock Escrow`;

    // Sync tab styles
    window.switchCcPayTab(activeMethod);

    // Sync default unselected/selected UPI borders
    document.querySelectorAll('[id^="upi-btn-"]').forEach(button => {
      button.style.borderColor = isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
    });
    // Set active one
    const activeUpiBtn = document.getElementById('upi-btn-gpay');
    if (activeUpiBtn) {
      activeUpiBtn.style.borderColor = isLight ? '#0e5a6f' : '#00dbe9';
    }

    const modal = document.getElementById('cc-payment-modal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  };

  window.closeCamCrewPaymentGateway = function() {
    const modal = document.getElementById('cc-payment-modal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  };

  function loadRazorpayScript() {
    return new Promise((resolve) => {
      if (window.Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.head.appendChild(script);
    });
  }

  window.submitCamCrewPayment = async function() {
    const btn = document.getElementById('cc-pay-submit-btn');
    const txt = document.getElementById('cc-pay-submit-txt');
    const err = document.getElementById('cc-pay-err');

    btn.disabled = true;
    err.style.display = 'none';
    txt.innerHTML = `<span class="material-symbols-outlined" style="animation:spin 0.8s linear infinite;font-size:1rem;">progress_activity</span> Opening Gateway…`;

    const loaded = await loadRazorpayScript();
    if (!loaded) {
      err.textContent = 'Failed to load Razorpay library. Check your internet connection.';
      err.style.display = 'block';
      btn.disabled = false;
      txt.textContent = `Pay ₹${Number(currentOptions.amount||0).toLocaleString('en-IN')} & Lock Escrow`;
      return;
    }

    try {
      // 1. Create Razorpay Order on Backend
      const orderRes = await fetch('/api/payments/create-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: currentOptions.amount,
          booking_id: currentOptions.booking_id || null
        })
      });
      const orderData = await orderRes.json();
      
      // Fallback: If Razorpay credentials are not configured, use mock checkout
      if (!orderData.ok) {
        if (orderData.error && orderData.error.includes("not configured")) {
          console.warn("Razorpay credentials not found, falling back to mock payment...");
          let payDetails = {};
          if (activeMethod === 'upi') {
            payDetails.vpa = document.getElementById('cc-upi-id')?.value.trim() || 'customer@upi';
          } else if (activeMethod === 'card') {
            payDetails.card_no = document.getElementById('cc-card-no')?.value.trim() || '4532••••8910';
          } else if (activeMethod === 'netbanking') {
            payDetails.bank = document.getElementById('cc-netbank-select')?.value || 'HDFC Bank';
          }
          const mockRes = await fetch('/api/payments/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              amount: currentOptions.amount,
              payment_method: activeMethod,
              payment_details: payDetails,
              booking_id: currentOptions.booking_id || null
            })
          });
          const mockData = await mockRes.json();
          if (!mockData.ok) throw new Error(mockData.error || 'Payment authorization failed.');
          
          window.closeCamCrewPaymentGateway();
          if (currentOptions && typeof currentOptions.onSuccess === 'function') {
            currentOptions.onSuccess(mockData);
          }
          return;
        }
        throw new Error(orderData.error || 'Failed to initialize payment.');
      }

      // 2. Configure Razorpay Options
      const options = {
        "key": orderData.key_id,
        "amount": orderData.amount * 100, // in paise
        "currency": "INR",
        "name": "Camcrew Studio",
        "description": currentOptions.title || "CamCrew Escrow Checkout",
        "order_id": orderData.order_id,
        "handler": async function (response) {
          txt.innerHTML = `<span class="material-symbols-outlined" style="animation:spin 0.8s linear infinite;font-size:1rem;">progress_activity</span> Securing Funds…`;
          try {
            const verifyRes = await fetch('/api/payments/verify-payment', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_signature: response.razorpay_signature,
                booking_id: currentOptions.booking_id || null,
                professional_id: currentOptions.professional_id || null,
                amount: currentOptions.amount
              })
            });
            const verifyData = await verifyRes.json();
            if (!verifyData.ok) throw new Error(verifyData.error || 'Signature verification failed.');

            window.closeCamCrewPaymentGateway();
            if (currentOptions && typeof currentOptions.onSuccess === 'function') {
              currentOptions.onSuccess(verifyData);
            }
          } catch (e) {
            err.textContent = e.message;
            err.style.display = 'block';
            btn.disabled = false;
            txt.textContent = `Retry Payment`;
          }
        },
        "prefill": {
          "name": "",
          "email": ""
        },
        "theme": {
          "color": "#00dbe9"
        },
        "modal": {
          "ondismiss": function() {
            btn.disabled = false;
            txt.textContent = `Pay ₹${Number(currentOptions.amount||0).toLocaleString('en-IN')} & Lock Escrow`;
          }
        }
      };

      const rzp = new Razorpay(options);
      rzp.open();

    } catch (e) {
      err.textContent = e.message;
      err.style.display = 'block';
      btn.disabled = false;
      txt.textContent = `Pay ₹${Number(currentOptions.amount||0).toLocaleString('en-IN')} & Lock Escrow`;
    }
  };
})();
