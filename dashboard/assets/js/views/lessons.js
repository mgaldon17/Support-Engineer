// View: Lecciones — live lesson memory: counts and the pending-review queue with
// Approve (resolve) / Reject (delete) actions.

import { escapeHtml } from '../dom.js';

function lessonCard(l) {
  const tag = l.pending_review
    ? '<span class="chip" style="background:rgba(217,119,6,.22);color:#fbbf24">PENDIENTE</span>'
    : '<span class="chip" style="background:rgba(5,150,105,.22);color:#6ee7b7">OK</span>';
  const actions = l.pending_review ? `
    <div class="flex gap-2 mt-3">
      <button class="btn-xs btn-ok flex-1" data-resolve="${escapeHtml(l.id)}">✓ Validar</button>
      <button class="btn-xs btn-bad flex-1" data-reject="${escapeHtml(l.id)}">✕ Rechazar</button>
    </div>` : '';
  return `
    <div class="row block ${l.pending_review ? 'ring-1 ring-amber-600/40' : ''}">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <div class="text-sm font-medium truncate">${escapeHtml(l.title)}</div>
          <div class="text-[11px] text-slate-500 mt-0.5">${escapeHtml(l.origin)} · ↺${l.reuse} · ✕${l.failure_count}</div>
        </div>
        ${tag}
      </div>
      <p class="text-xs text-slate-400 mt-2 line-clamp-3 whitespace-pre-wrap">${escapeHtml((l.content || '').slice(0, 280))}</p>
      ${actions}
    </div>`;
}

export default {
  id: 'lessons',
  label: 'Lecciones',
  icon: '📚',
  badge: (state) => state.lessons.pending_count || '',

  render({ state }) {
    const L = state.lessons;
    const err = L.ok ? '' : `
      <div class="row block" style="background:rgba(120,53,15,.35);border-color:rgba(180,83,9,.4)">
        <p class="text-sm text-amber-200">⚠ No se pudo leer la memoria: ${escapeHtml(L.error)}</p>
        <p class="text-xs text-amber-300/80 mt-1">¿Está Qdrant arrancado? <code>docker compose up -d</code></p>
      </div>`;
    const items = L.items.length
      ? L.items.map(lessonCard).join('')
      : '<p class="text-xs text-slate-500">Sin lecciones en la base de datos.</p>';

    return `
    <div class="space-y-6">
      <div class="grid grid-cols-3 gap-4">
        <div class="stat"><div class="num text-indigo-300">${L.total}</div><div class="cap">Total en BD</div></div>
        <div class="stat"><div class="num text-amber-400">${L.pending_count}</div><div class="cap">Por revisar</div></div>
        <div class="stat"><div class="num text-emerald-400">${L.approved_count}</div><div class="cap">Aprobadas</div></div>
      </div>
      ${err}
      <section class="card">
        <h2 class="text-lg font-semibold mb-4">📚 Lecciones de memoria</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">${items}</div>
      </section>
    </div>`;
  },

  mount(root, { actions }) {
    root.querySelectorAll('[data-resolve]').forEach((b) =>
      b.addEventListener('click', () => actions.lesson('resolve', b.dataset.resolve)));
    root.querySelectorAll('[data-reject]').forEach((b) =>
      b.addEventListener('click', () => actions.lesson('delete', b.dataset.reject)));
  },
};
