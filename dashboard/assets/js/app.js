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

const actions = {
  warn: (msg) => toast(msg, false),
  goTo: (id) => selectTab(id),

  setBool: (field, value) => Api.saveConfig({ [field]: value }).then((r) => settle(r, 'Guardado')),
  saveConfig: (partial) => Api.saveConfig(partial).then((r) => settle(r, 'Configuración guardada')),

  toggleRule: (key, enabled, source) =>
    Api.rule.toggle(key, enabled, source).then((r) => settle(r, enabled ? 'Regla activada' : 'Regla desactivada')),
  addRule: (reason, regex) => Api.rule.add(reason, regex).then((r) => settle(r, 'Comando bloqueado añadido')),
  deleteRule: (key) => Api.rule.remove(key).then((r) => settle(r, 'Regla eliminada')),

  allowedAdd: (entry) => Api.allowed.add(entry).then((r) => settle(r, 'Permiso añadido')),
  allowedRemove: (entry) => Api.allowed.remove(entry).then((r) => settle(r, 'Permiso eliminado')),
  allowedToBlocked: (entry) => Api.allowed.toBlocked(entry).then((r) => settle(r, 'Movido a bloqueados')),
  blockedToAllowed: (key) => Api.blocked.toAllowed(key).then((r) => settle(r, 'Movido a permitidos')),

  lesson: (action, id) =>
    Api.lesson(action, id).then((r) => settle(r, action === 'resolve' ? 'Lección validada' : 'Lección eliminada')),
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
  state = await Api.getState();
  h('#cfgfile').textContent = state.config_file;
  renderStats();
  renderTabs();
  renderView();
}

h('#reload').addEventListener('click', refresh);
refresh();
