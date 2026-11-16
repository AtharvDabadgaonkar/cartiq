import nextPlugin from '@next/eslint-plugin-next';
import base from '@cartiq/eslint-config';

/**
 * Flat config. eslint-config-next still ships eslintrc format, so the Next
 * plugin is wired up directly rather than through FlatCompat.
 */
export default [
  ...base,
  { ignores: ['.next/**', 'e2e/**', 'next-env.d.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { '@next/next': nextPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
    },
  },
];
