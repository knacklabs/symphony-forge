import js from '@eslint/js';
import ts from 'typescript-eslint';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default ts.config(
  { ignores: ['node_modules/**', '**/dist/**', '**/.venv/**', '**/__pycache__/**', '.pytest_cache/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  // One date, time, number and money format: only the shared helpers may format them by hand.
  {
    files: ['apps/*/src/**/*.{ts,tsx}', 'libs/*/*/src/**/*.ts'],
    ignores: ['libs/shared/util/src/format.ts'],
    rules: {
      'no-restricted-syntax': ['error', ...[
        "NewExpression[callee.object.name='Intl']",
        "CallExpression[callee.object.name='Intl']",
        'CallExpression[callee.property.name=/^toLocale(Date|Time)?String$/]',
        "CallExpression[callee.property.name='toFixed']",
      ].map((selector) => ({ selector, message: 'Format dates, times, numbers and money with the helpers in @app/shared-util.' }))],
    },
  },
  // React Compiler memoizes, so the hooks rules check the app's own code; shadcn/ui copies stay as shipped.
  { ...reactHooks.configs.flat.recommended, files: ['apps/web/src/**/*.{ts,tsx}'], ignores: ['apps/web/src/components/ui/**'] },
  // shadcn/ui's copied source uses optional callbacks and exports alongside components.
  { files: ['apps/web/src/components/ui/**'], rules: { '@typescript-eslint/no-empty-object-type': 'off' } },
);
