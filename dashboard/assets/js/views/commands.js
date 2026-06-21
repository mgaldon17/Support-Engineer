// View: Comandos — manage the blocked patterns (built-in + custom) and the allowed
// list, and move commands either way. Single responsibility: command-policy editing.

import { switchHtml, escapeHtml } from '../dom.js';

function blockedRow(p) {
  const sourceChip = p.source === 'custom'
    ? '<span class="chip" style="background:rgba(217,70,239,.18);color:#e9a8ff">custom</span>'
    : '<span class="chip">built-in</span>';
  const moveBtn = p.source === 'custom'
    ? `<button class="btn-xs btn-warn" data-to-allowed="${escapeHtml(p.key)}" title="Mover a permitidos">→ permitir</button>`
    : '';
  const delBtn = p.deletable
    ? `<button class="btn-xs btn-bad" data-del="${escapeHtml(p.key)}" title="Eliminar regla">✕</button>`
    : '';
  return `
    <div class="row">
      ${switchHtml(p.enabled, { rule: p.key, source: p.source })}
      <div class="flex-1 min-w-0">
        <div class="text-sm">${escapeHtml(p.reason)}</div>
        <code class="mono-sub">${escapeHtml(p.regex)}</code>
      </div>
      <div class="flex items-center gap-1.5 flex-none">${sourceChip}${moveBtn}${delBtn}</div>
    </div>`;
}

function allowedRow(perm) {
  const moveBtn = perm.bash
    ? `<button class="btn-xs btn-warn" data-to-blocked="${escapeHtml(perm.entry)}" title="Mover a bloqueados">→ bloquear</button>`
    : '';
  return `
    <div class="row items-center">
      <code class="flex-1 min-w-0 text-sm font-mono truncate">${escapeHtml(perm.entry)}</code>
      <div class="flex items-center gap-1.5 flex-none">
        ${moveBtn}
        <button class="btn-xs btn-bad" data-allow-del="${escapeHtml(perm.entry)}" title="Quitar permiso">✕</button>
      </div>
    </div>`;
}

export default {
  id: 'commands',
  label: 'Comandos',
  icon: '⌨️',
  badge: (state) => state.patterns.filter((p) => p.enabled).length,

  render({ state }) {
    const blocked = state.patterns.map(blockedRow).join('');
    const allowed = state.permissions.map(allowedRow).join('') ||
      '<p class="text-xs text-slate-500">Sin comandos permitidos.</p>';

    return `
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <section class="card">
        <h2 class="text-lg font-semibold mb-1">⛔ Comandos bloqueados</h2>
        <p class="text-xs text-slate-400 mb-4">Patrones (regex) vetados al ejecutar shell. Desactiva sin borrar con el interruptor; las reglas <b>custom</b> se pueden eliminar o mover a permitidos.</p>
        <div class="space-y-2.5 max-h-[26rem] overflow-y-auto pr-1">${blocked}</div>

        <div class="mt-5 pt-4 border-t border-edge/60">
          <h3 class="text-sm font-semibold mb-2">➕ Añadir comando bloqueado</h3>
          <div class="space-y-2">
            <input type="text" id="new-reason" class="field" placeholder="Motivo (p. ej. borrado de /etc)"/>
            <input type="text" id="new-regex" class="field" placeholder="Regex (p. ej. \\brm\\s+-rf\\s+/etc)"/>
            <button class="btn-primary w-full" data-add-rule>Bloquear comando</button>
          </div>
        </div>
      </section>

      <section class="card">
        <h2 class="text-lg font-semibold mb-1">✅ Comandos permitidos</h2>
        <p class="text-xs text-slate-400 mb-4">Allowlist del harness (<span class="chip">.claude/settings.json</span>). Las entradas <span class="chip">Bash(...)</span> pueden moverse a bloqueados.</p>
        <div class="space-y-2.5 max-h-[26rem] overflow-y-auto pr-1">${allowed}</div>

        <div class="mt-5 pt-4 border-t border-edge/60">
          <h3 class="text-sm font-semibold mb-2">➕ Añadir permitido</h3>
          <div class="space-y-2">
            <input type="text" id="new-allow" class="field" placeholder="Bash(npm test*)  ·  mcp__pw__browser_click"/>
            <button class="btn-primary w-full" data-add-allow>Permitir</button>
          </div>
        </div>
      </section>
    </div>`;
  },

  mount(root, { actions }) {
    // toggle a rule on/off
    root.querySelectorAll('[data-rule]').forEach((cb) => {
      cb.addEventListener('change', () =>
        actions.toggleRule(cb.dataset.rule, cb.checked, cb.dataset.source));
    });
    // delete / move custom blocked rules
    root.querySelectorAll('[data-del]').forEach((b) =>
      b.addEventListener('click', () => actions.deleteRule(b.dataset.del)));
    root.querySelectorAll('[data-to-allowed]').forEach((b) =>
      b.addEventListener('click', () => actions.blockedToAllowed(b.dataset.toAllowed)));
    // allowed list: remove / move to blocked
    root.querySelectorAll('[data-allow-del]').forEach((b) =>
      b.addEventListener('click', () => actions.allowedRemove(b.dataset.allowDel)));
    root.querySelectorAll('[data-to-blocked]').forEach((b) =>
      b.addEventListener('click', () => actions.allowedToBlocked(b.dataset.toBlocked)));
    // add forms
    root.querySelector('[data-add-rule]').addEventListener('click', () => {
      const reason = root.querySelector('#new-reason').value.trim();
      const regex = root.querySelector('#new-regex').value.trim();
      if (!reason || !regex) return actions.warn('Indica motivo y regex.');
      actions.addRule(reason, regex);
    });
    root.querySelector('[data-add-allow]').addEventListener('click', () => {
      const entry = root.querySelector('#new-allow').value.trim();
      if (!entry) return actions.warn('Indica una entrada de permiso.');
      actions.allowedAdd(entry);
    });
  },
};
