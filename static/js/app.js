/* ── Sidebar toggle ─────────────────────────────────────────────────────── */
const sidebar     = document.getElementById('sidebar');
const mainWrapper = document.getElementById('main-wrapper');
const toggleBtn   = document.getElementById('sidebar-toggle');
const overlay     = document.getElementById('sidebar-overlay');

const COLLAPSED_KEY = 'sidebar_collapsed';
const isMobile = () => window.innerWidth <= 768;

/* Restore desktop collapsed state on load */
if (!isMobile() && localStorage.getItem(COLLAPSED_KEY) === '1') {
  sidebar?.classList.add('collapsed');
  mainWrapper?.classList.add('expanded');
}

function closeMobileSidebar() {
  sidebar?.classList.remove('mobile-open');
  overlay?.classList.remove('active');
}

if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    if (isMobile()) {
      const isOpen = sidebar.classList.toggle('mobile-open');
      overlay?.classList.toggle('active', isOpen);
    } else {
      sidebar.classList.toggle('collapsed');
      mainWrapper.classList.toggle('expanded');
      localStorage.setItem(COLLAPSED_KEY, sidebar.classList.contains('collapsed') ? '1' : '0');
    }
  });
}

/* Close sidebar when tapping backdrop */
overlay?.addEventListener('click', closeMobileSidebar);

/* Close sidebar on resize back to desktop */
window.addEventListener('resize', () => {
  if (!isMobile()) closeMobileSidebar();
});

/* ── Auto-dismiss flash messages ────────────────────────────────────────── */
document.querySelectorAll('.alert.alert-success').forEach(el => {
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
    if (bsAlert) bsAlert.close();
  }, 4000);
});

/* ── Offer calculator ───────────────────────────────────────────────────── */
function calcOffer() {
  const get = id => parseFloat(document.getElementById(id)?.value || 0) || 0;
  const labor = get('labor_cost');
  const mats  = get('materials_cost');
  const equip = get('equipment_cost');
  const sub   = get('subcontractor_cost');
  const ohPct = get('overhead_pct');
  const prPct = get('profit_pct');
  const vatPct= get('vat_pct');

  const direct   = labor + mats + equip + sub;
  const overhead = direct * ohPct / 100;
  const profit   = (direct + overhead) * prPct / 100;
  const net      = direct + overhead + profit;
  const vat      = net * vatPct / 100;
  const gross    = net + vat;

  const fmt = v => v.toLocaleString('el-GR', {minimumFractionDigits:2, maximumFractionDigits:2});
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = fmt(v) + ' €'; };

  set('calc_direct', direct);
  set('calc_overhead', overhead);
  set('calc_profit', profit);
  set('calc_net', net);
  set('calc_vat', vat);
  set('calc_gross', gross);

  const grossEl = document.getElementById('offer_total_gross');
  if (grossEl) grossEl.textContent = fmt(gross) + ' €';
}

document.querySelectorAll('.offer-input').forEach(el => {
  el.addEventListener('input', calcOffer);
});
if (document.querySelector('.offer-input')) calcOffer();

/* ── Invoice VAT calculator ─────────────────────────────────────────────── */
function calcInvoice() {
  const net    = parseFloat(document.getElementById('amount_net')?.value || 0) || 0;
  const vatR   = parseFloat(document.getElementById('vat_rate')?.value || 24) || 24;
  const vat    = net * vatR / 100;
  const total  = net + vat;
  const fmt    = v => v.toLocaleString('el-GR', {minimumFractionDigits:2}) + ' €';
  const s = id => { const el = document.getElementById(id); if (el) el.textContent = fmt(el.name ? 0 : (id==='vat_display'?vat:total)); };
  const vd = document.getElementById('vat_display');
  const td = document.getElementById('total_display');
  if (vd) vd.textContent = fmt(vat);
  if (td) td.textContent = fmt(total);
}
['amount_net','vat_rate'].forEach(id => {
  document.getElementById(id)?.addEventListener('input', calcInvoice);
});
calcInvoice();

/* ── File upload preview ─────────────────────────────────────────────────── */
const fileInput = document.getElementById('invoice_image');
const preview   = document.getElementById('image_preview');
if (fileInput && preview) {
  fileInput.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      preview.closest('.preview-wrap')?.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
  });
}

/* ── Drag-and-drop upload zone ──────────────────────────────────────────── */
const zone = document.querySelector('.upload-zone');
if (zone) {
  ['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, e => {
    e.preventDefault(); zone.classList.add('drag-over');
  }));
  ['dragleave','drop'].forEach(ev => zone.addEventListener(ev, e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (ev === 'drop' && fileInput) {
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event('change'));
    }
  }));
  zone.addEventListener('click', () => fileInput?.click());
}

/* ── Confirm dangerous actions ───────────────────────────────────────────── */
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', function (e) {
    if (!confirm(this.dataset.confirm || 'Είστε σίγουρος;')) e.preventDefault();
  });
});

/* ── Tooltips init ──────────────────────────────────────────────────────── */
document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el =>
  bootstrap.Tooltip.getOrCreateInstance(el)
);

/* ── Dashboard charts helper ─────────────────────────────────────────────── */
function buildLineChart(canvasId, labels, incomeData, expenseData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Έσοδα', data: incomeData, borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,.1)',
          tension: .4, fill: true, pointRadius: 3 },
        { label: 'Έξοδα', data: expenseData, borderColor: '#dc2626', backgroundColor: 'rgba(220,38,38,.08)',
          tension: .4, fill: true, pointRadius: 3 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { color: '#aaa' } } },
      scales: {
        y: { ticks: { callback: v => v.toLocaleString('el-GR') + '€', color: '#888' }, grid: { color: 'rgba(255,255,255,.08)' } },
        x: { ticks: { color: '#888' }, grid: { display: false } }
      }
    }
  });
}

function buildDoughnutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { font: { size: 12 }, color: '#aaa' } } },
      cutout: '65%'
    }
  });
}

function buildBarChart(canvasId, labels, data, label, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label, data, backgroundColor: color, borderRadius: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,.08)' } }, x: { ticks: { color: '#888' }, grid: { display: false } } }
    }
  });
}

/* ── PWA Service Worker registration ────────────────────────────────────── */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(reg => console.log('SW registered', reg.scope))
      .catch(err => console.warn('SW failed', err));
  });
}
