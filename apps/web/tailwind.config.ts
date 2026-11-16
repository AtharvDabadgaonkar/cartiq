import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

/**
 * CartIQ "Ember" theme — warm charcoal + amber/clay/moss.
 * Deliberately not blue-on-white: the console reads as an operations surface,
 * and the accents stay distinguishable for the most common colour-vision
 * deficiencies (amber vs clay vs moss differ in lightness as well as hue).
 * Tokens live in globals.css so dark and light share one contract.
 */
const config: Config = {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        surface: {
          DEFAULT: 'hsl(var(--surface) / <alpha-value>)',
          raised: 'hsl(var(--surface-raised) / <alpha-value>)',
        },
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
        muted: {
          DEFAULT: 'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        // Amber: primary actions, the "signal" colour.
        primary: {
          DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
        },
        // Clay: friction, drop-off, destructive.
        clay: {
          DEFAULT: 'hsl(var(--clay) / <alpha-value>)',
          foreground: 'hsl(var(--clay-foreground) / <alpha-value>)',
        },
        // Moss: conversion, wins, "ship it".
        moss: {
          DEFAULT: 'hsl(var(--moss) / <alpha-value>)',
          foreground: 'hsl(var(--moss-foreground) / <alpha-value>)',
        },
        plum: 'hsl(var(--plum) / <alpha-value>)',
        ochre: 'hsl(var(--ochre) / <alpha-value>)',
        destructive: {
          DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        // Ordered categorical ramp for Recharts series.
        chart: {
          1: 'hsl(var(--chart-1) / <alpha-value>)',
          2: 'hsl(var(--chart-2) / <alpha-value>)',
          3: 'hsl(var(--chart-3) / <alpha-value>)',
          4: 'hsl(var(--chart-4) / <alpha-value>)',
          5: 'hsl(var(--chart-5) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: { 'fade-up': 'fade-up 180ms ease-out' },
    },
  },
  plugins: [animate],
};

export default config;
