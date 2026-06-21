// Data-access layer — the ONLY module that talks HTTP. Views never call fetch directly;
// they depend on the injected `actions` (see app.js), which depend on this Api object.
// Single responsibility: turn intentions into requests and return parsed JSON.

async function post(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

export const Api = {
  getState: () => fetch('/api/state').then((r) => r.json()),

  saveConfig: (config) => post('/api/save', config),

  lesson: (action, id) => post('/api/lesson', { action, id }),

  rule: {
    add: (reason, regex) => post('/api/rules/add', { reason, regex }),
    toggle: (key, enabled, source) => post('/api/rules/toggle', { key, enabled, source }),
    remove: (key) => post('/api/rules/delete', { key }),
  },

  allowed: {
    add: (entry) => post('/api/allowed/add', { entry }),
    remove: (entry) => post('/api/allowed/remove', { entry }),
    toBlocked: (entry) => post('/api/allowed/to-blocked', { entry }),
  },

  blocked: {
    toAllowed: (key) => post('/api/blocked/to-allowed', { key }),
  },
};
