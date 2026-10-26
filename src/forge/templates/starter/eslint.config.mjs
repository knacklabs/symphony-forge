import js from '@eslint/js';
import ts from 'typescript-eslint';
import globals from 'globals';
import nx from '@nx/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';

export default ts.config(
  { ignores: ['node_modules/**', '**/dist/**', '.nx/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  {
    files: ['**/*.ts', '**/*.tsx'],
    plugins: { '@nx': nx },
    rules: {
      '@nx/enforce-module-boundaries': ['error', {
        depConstraints: [
          { sourceTag: 'type:util', onlyDependOnLibsWithTags: ['type:util'] },
          { sourceTag: 'type:ui', onlyDependOnLibsWithTags: ['type:ui', 'type:util'] },
          { sourceTag: 'type:contracts', onlyDependOnLibsWithTags: ['type:contracts', 'type:util'] },
          { sourceTag: 'type:server', onlyDependOnLibsWithTags: ['type:server', 'type:contracts', 'type:util'] },
          { sourceTag: 'type:web', onlyDependOnLibsWithTags: ['type:web', 'type:ui', 'type:contracts', 'type:util'] },
          { sourceTag: 'type:api', onlyDependOnLibsWithTags: ['type:server', 'type:contracts', 'type:util'] },
          { sourceTag: 'type:app-web', onlyDependOnLibsWithTags: ['type:web', 'type:ui', 'type:contracts', 'type:util'] },
          { sourceTag: 'scope:shared', onlyDependOnLibsWithTags: ['scope:shared'] },
          { sourceTag: 'scope:core', onlyDependOnLibsWithTags: ['scope:core', 'scope:shared'] },
          // Add a scope line here for each new module. Other modules expose only their contracts.
          { sourceTag: 'scope:auth', onlyDependOnLibsWithTags: ['scope:auth', 'scope:core', 'scope:shared', 'type:contracts'] },
          { sourceTag: 'scope:projects', onlyDependOnLibsWithTags: ['scope:projects', 'scope:core', 'scope:shared', 'type:contracts'] },
          { sourceTag: 'scope:organisations', onlyDependOnLibsWithTags: ['scope:organisations', 'scope:core', 'scope:shared', 'type:contracts'] },
          { sourceTag: 'scope:history', onlyDependOnLibsWithTags: ['scope:history', 'scope:core', 'scope:shared', 'type:contracts'] },
          { sourceTag: 'scope:app', onlyDependOnLibsWithTags: ['*'] },
        ],
      }],
    },
  },
  // One date, time, number and money format: only the shared helpers may format them by hand.
  {
    files: ['apps/*/src/**/*.{ts,tsx}', 'libs/*/*/src/**/*.{ts,tsx}'],
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
