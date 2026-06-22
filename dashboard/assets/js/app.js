// Application controller — composition root.
// Owns the state, builds the `actions` facade (depending on the Api abstraction, not on
// fetch), wires the tab navigation and delegates rendering to the registered views.
// Views depend on { state, actions }; they never import Api or touch global state.

import { Api } from './api.js';
import { h, toast } from './dom.js';

import guardrails from './views/guardrails.js';
import commands from './views/commands.js';
import lessons from './views/lessons.js';
import memory from './views/settings.js';

const VIEWS = [guardrails, commands, lessons, memory];

let state = null;
let activeId = VIEWS[0].id;

// ---- actions facade: intention -> Api call -> toast + refresh ---------- //
function settle(res, okMsg) {
  if (res && res.ok !== false) { toast(okMsg, true); return refresh(); }
  toast('Error: ' + ((res && res.error) || 'falló'), false);
}

// Run an Api call: on success settle (toast + refresh); on a transport/network failure
// surface it as a toast instead of leaving an unhandled promise rejection.
function run(promise, okMsg) {
  return promise.then((r) => settle(r, okMsg)).catch((e) => toast('Error: ' + e.message, false));
}

const actions = {
  warn: (msg) => toast(msg, false),
  goTo: (id) => selectTab(id),

  setBool: (field, value) => run(Api.saveConfig({ [field]: value }), 'Guardado'),
  saveConfig: (partial) => run(Api.saveConfig(partial), 'Configuración guardada'),

  toggleRule: (key, enabled, source) =>
    run(Api.rule.toggle(key, enabled, source), enabled ? 'Regla activada' : 'Regla desactivada'),
  addRule: (reason, regex) => run(Api.rule.add(reason, regex), 'Comando bloqueado añadido'),
  deleteRule: (key) => run(Api.rule.remove(key), 'Regla eliminada'),

  allowedAdd: (entry) => run(Api.allowed.add(entry), 'Permiso añadido'),
  allowedRemove: (entry) => run(Api.allowed.remove(entry), 'Permiso eliminado'),
  allowedToBlocked: (entry) => run(Api.allowed.toBlocked(entry), 'Movido a bloqueados'),
  blockedToAllowed: (key) => run(Api.blocked.toAllowed(key), 'Movido a permitidos'),

  lesson: (action, id) =>
    run(Api.lesson(action, id), action === 'resolve' ? 'Lección validada' : 'Lección eliminada'),
};

// ---- rendering -------------------------------------------------------- //
function renderStats() {
  const L = state.lessons;
  const activePatterns = state.patterns.filter((p) => p.enabled).length;
  const cards = [
    ['Lecciones por revisar', L.pending_count, 'text-amber-400'],
    ['Lecciones totales', L.total, 'text-indigo-300'],
    ['Comandos bloqueados', `${activePatterns}/${state.patterns.length}`, 'text-rose-400'],
    ['Comandos permitidos', state.permissions.length, 'text-emerald-400'],
  ];
  h('#stats').innerHTML = cards
    .map(([cap, num, color]) => `<div class="stat"><div class="num ${color}">${num}</div><div class="cap">${cap}</div></div>`)
    .join('');
}

function renderTabs() {
  h('#tabs').innerHTML = VIEWS.map((v) => {
    const badge = v.badge ? v.badge(state) : '';
    const badgeHtml = badge ? `<span class="badge">${badge}</span>` : '';
    return `<button class="tab" role="tab" aria-selected="${v.id === activeId}" data-tab="${v.id}">
      ${v.icon} ${v.label}${badgeHtml}</button>`;
  }).join('');
  h('#tabs').querySelectorAll('[data-tab]').forEach((b) =>
    b.addEventListener('click', () => selectTab(b.dataset.tab)));
}

function renderView() {
  const view = VIEWS.find((v) => v.id === activeId);
  const root = h('#view');
  root.innerHTML = view.render({ state, actions });
  root.classList.remove('animate-fadein'); void root.offsetWidth; root.classList.add('animate-fadein');
  view.mount(root, { state, actions });
}

function selectTab(id) {
  activeId = id;
  renderTabs();
  renderView();
}

async function refresh() {
  try {
    state = await Api.getState();
  } catch (e) {
    toast('No se pudo contactar el panel: ' + e.message, false);
    return;
  }
  h('#cfgfile').textContent = state.config_file;
  renderStats();
  renderTabs();
  renderView();
}

h('#reload').addEventListener('click', refresh);
refresh();
