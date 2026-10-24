import js from '@eslint/js';
import ts from 'typescript-eslint';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default ts.config(
  { ignores: ['node_modules/**', '**/dist/**', '**/.venv/**', '**/__pycache__/**', '.pytest_cache/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  // React Compiler memoizes, so the hooks rules check the app's own code; shadcn/ui copies stay as shipped.
  { ...reactHooks.configs.flat.recommended, files: ['apps/web/src/**/*.{ts,tsx}'], ignores: ['apps/web/src/components/ui/**'] },
  // shadcn/ui's copied source uses optional callbacks and exports alongside components.
  { files: ['apps/web/src/components/ui/**'], rules: { '@typescript-eslint/no-empty-object-type': 'off' } },
);
