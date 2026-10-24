import js from '@eslint/js';
import ts from 'typescript-eslint';
import globals from 'globals';
import nx from '@nx/eslint-plugin';

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
          { sourceTag: 'type:web', onlyDependOnLibsWithTags: ['type:shared'] },
          { sourceTag: 'type:api', onlyDependOnLibsWithTags: ['type:module', 'type:core', 'type:shared'] },
          { sourceTag: 'type:module', onlyDependOnLibsWithTags: ['type:module', 'type:core', 'type:shared'] },
          { sourceTag: 'type:core', onlyDependOnLibsWithTags: ['type:core', 'type:shared'] },
          { sourceTag: 'type:shared', onlyDependOnLibsWithTags: ['type:shared'] },
        ],
      }],
    },
  },
  // shadcn/ui's copied source uses optional callbacks and exports alongside components.
  { files: ['apps/web/src/components/ui/**'], rules: { '@typescript-eslint/no-empty-object-type': 'off' } },
);
