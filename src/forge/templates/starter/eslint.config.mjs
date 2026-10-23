import js from '@eslint/js';
import ts from 'typescript-eslint';
import globals from 'globals';

export default ts.config(
  { ignores: ['node_modules/**', '**/dist/**', '.nx/**', 'test-results/**', 'playwright-report/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  // shadcn/ui's copied source uses optional callbacks and exports alongside components.
  { files: ['apps/web/src/components/ui/**'], rules: { '@typescript-eslint/no-empty-object-type': 'off' } },
);
