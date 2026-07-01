// View: Guardrails — master switches, URL-guard settings and an info panel.
// Conforms to the View interface { id, label, icon, render(ctx), mount(root, ctx) }.

import { switchHtml, fieldHtml, readFields, escapeHtml } from '../dom.js';

export default {
  id: 'guardrails',
  label: 'Guardrails',
  icon: '🛡️',

  render({ state }) {
    const c = state.config;
    const urlTools = state.policed_tools.url.map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join(' ');
    const cmdTools = state.policed_tools.command.map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join(' ');

    return `
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <section class="card">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-lg font-semibold">🌐 Guardrail de navegación URL</h2>
          ${switchHtml(c.guard_url_enabled, { bool: 'guard_url_enabled' })}
        </div>
        <p class="text-xs text-slate-400 mb-4">Veta URLs mal formadas, fuera de la allowlist o inalcanzables (404/DNS).</p>
        <div class="space-y-3">
          <div class="flex items-center justify-between row">
            <span class="text-sm">Comprobar accesibilidad (probe HTTP)</span>
            ${switchHtml(c.guard_check_reachable, { bool: 'guard_check_reachable' })}
          </div>
          <div>
            <label class="label">Allowlist de dominios (coma-separada · vacío = cualquiera)</label>
            <input type="text" data-field="guard_allow_domains" class="field" placeholder="example.com, intranet.acme.corp" value="${escapeHtml(c.guard_allow_domains)}"/>
          </div>
          <div class="grid grid-cols-2 gap-3">
            ${fieldHtml('Timeout probe (s)', 'probe_timeout', c.probe_timeout, 'number')}
            ${fieldHtml('User-Agent probe', 'probe_user_agent', c.probe_user_agent)}
          </div>
          <div class="text-xs text-slate-500">Tools vigiladas: ${urlTools}</div>
          <button class="btn-primary" data-act="save">Guardar configuración URL</button>
        </div>
      </section>

      <section class="card">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-lg font-semibold">⛔ Guardrail de comandos destructivos</h2>
          ${switchHtml(c.guard_destructive_enabled, { bool: 'guard_destructive_enabled' })}
        </div>
        <p class="text-xs text-slate-400 mb-4">Bloquea patrones de shell peligrosos antes de ejecutarse.</p>
        <div class="space-y-3 text-sm text-slate-300">
          <div class="row block">
            <p class="mb-2">Activos: <b class="text-rose-300">${state.patterns.filter((p) => p.enabled).length}</b> de ${state.patterns.length} patrones
            (<b>${state.patterns.filter((p) => p.source === 'custom').length}</b> personalizados).</p>
            <p class="text-xs text-slate-400">Gestiona, activa/desactiva y añade comandos en la pestaña <b>Comandos</b>.</p>
          </div>
          <div class="text-xs text-slate-500">Tools vigiladas: ${cmdTools}</div>
          <button class="btn-ghost" data-goto="commands">Ir a Comandos →</button>
        </div>
      </section>

      <section class="card lg:col-span-2">
        <h2 class="text-lg font-semibold mb-2">ℹ️ Cómo funcionan</h2>
        <ul class="text-sm text-slate-400 space-y-1.5 list-disc pl-5">
          <li>Los guardrails se aplican en el hook <span class="chip">PreToolUse</span>: vetan la llamada <i>antes</i> de ejecutarse.</li>
          <li>El primer veto gana; con un guardrail desactivado, su cadena se omite por completo.</li>
          <li>Cambios aquí se escriben en <span class="chip">config.yaml</span> y aplican en la siguiente llamada del agente.</li>
        </ul>
      </section>
    </div>`;
  },

  mount(root, { actions }) {
    root.querySelectorAll('[data-bool]').forEach((cb) => {
      cb.addEventListener('change', () => actions.setBool(cb.dataset.bool, cb.checked));
    });
    const save = root.querySelector('[data-act="save"]');
    if (save) save.addEventListener('click', () => actions.saveConfig(readFields(root)));
    const goto = root.querySelector('[data-goto]');
    if (goto) goto.addEventListener('click', () => actions.goTo(goto.dataset.goto));
  },
};
