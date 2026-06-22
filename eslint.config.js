// ESLint flat config for the dashboard front-end (vanilla ES modules, browser runtime).
import js from '@eslint/js';
import globals from 'globals';

export default [
  // Never descend into installed deps.
  { ignores: ['node_modules/**'] },

  // Baseline recommended rules for every linted JS file (incl. this config).
  js.configs.recommended,

  // The hand-written SPA runs in the browser as ES modules.
  {
    files: ['dashboard/assets/js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser },
    },
  },
];
