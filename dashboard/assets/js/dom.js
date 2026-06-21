// Presentation utilities — small, pure DOM/string helpers shared by every view.
// No app state, no HTTP: just rendering primitives.

export const h = (sel) => document.querySelector(sel);
export const hAll = (sel) => [...document.querySelectorAll(sel)];

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

let toastTimer;
export function toast(message, ok = true) {
  const el = h('#toast');
  el.textContent = message;
  el.className = `toast show ${ok ? 'ok' : 'bad'}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 2400);
}

// A reusable toggle switch bound to a change handler. Returns an HTML string;
// wiring is done by [data-toggle] delegation in each view's mount().
export function switchHtml(checked, dataAttrs = {}) {
  const attrs = Object.entries(dataAttrs).map(([k, v]) => `data-${k}="${escapeHtml(v)}"`).join(' ');
  return `<label class="switch"><input type="checkbox" ${checked ? 'checked' : ''} ${attrs}/>
    <span class="track"></span><span class="knob"></span></label>`;
}

// Build a labelled text/number input bound by data-field (read back via readFields()).
export function fieldHtml(label, key, value, type = 'text') {
  return `<div><label class="label">${label}</label>
    <input type="${type}" data-field="${key}" class="field" value="${escapeHtml(value)}"/></div>`;
}

// Collect every [data-field] input inside a root into a {key: value} object.
export function readFields(root) {
  const out = {};
  root.querySelectorAll('[data-field]').forEach((el) => { out[el.dataset.field] = el.value; });
  return out;
}
