// View: Memoria — Qdrant / embedder / retrieval configuration.

import { fieldHtml, readFields } from '../dom.js';

export default {
  id: 'memory',
  label: 'Memoria',
  icon: '🗄️',

  render({ state }) {
    const c = state.config;
    return `
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <section class="card">
        <h2 class="text-lg font-semibold mb-4">🗄️ Almacén · Qdrant</h2>
        <div class="grid grid-cols-2 gap-3">
          ${fieldHtml('Host', 'qdrant_host', c.qdrant_host)}
          ${fieldHtml('Puerto', 'qdrant_port', c.qdrant_port, 'number')}
          ${fieldHtml('Colección', 'collection', c.collection)}
          ${fieldHtml('Namespace (user)', 'mem_user', c.mem_user)}
        </div>
      </section>

      <section class="card">
        <h2 class="text-lg font-semibold mb-4">🧬 Embedder & recuperación</h2>
        <div class="grid grid-cols-2 gap-3">
          ${fieldHtml('Provider', 'embedder_provider', c.embedder_provider)}
          ${fieldHtml('Dimensiones', 'embedder_dims', c.embedder_dims, 'number')}
          ${fieldHtml('Modelo', 'embedder_model', c.embedder_model)}
          ${fieldHtml('Base URL', 'embedder_base_url', c.embedder_base_url)}
          ${fieldHtml('Búsqueda top-k', 'lesson_search_limit', c.lesson_search_limit, 'number')}
          ${fieldHtml('Listado top-k', 'lesson_list_limit', c.lesson_list_limit, 'number')}
        </div>
        <p class="text-xs text-amber-300/80 mt-3">Cambiar provider/dimensiones requiere una colección Qdrant nueva (cambia el tamaño del vector).</p>
      </section>

      <section class="card lg:col-span-2 flex items-center justify-between">
        <p class="text-sm text-slate-400">Los cambios se escriben en <span class="chip">${c.qdrant_host ? 'config.env' : 'config.env'}</span>.</p>
        <button class="btn-primary" data-act="save">Guardar configuración de memoria</button>
      </section>
    </div>`;
  },

  mount(root, { actions }) {
    root.querySelector('[data-act="save"]').addEventListener('click', () =>
      actions.saveConfig(readFields(root)));
  },
};
