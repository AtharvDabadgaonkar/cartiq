import nextPlugin from '@next/eslint-plugin-next';
import base from '@cartiq/eslint-config';

/**
 * Flat config. eslint-config-next still ships eslintrc format, so the Next
 * plugin is wired up directly rather than through FlatCompat.
 */
export default [
  ...base,
  { ignores: ['.next/**', 'e2e/**', 'next-env.d.ts'] },
  // Registered unscoped: `next build` looks for the plugin at the top level of
  // the config and warns that it is missing when it only appears inside a
  // `files` block, even though the rules below do run.
  { plugins: { '@next/next': nextPlugin } },
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
    },
  },
];
