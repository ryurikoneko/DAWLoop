import { defineConfig } from 'vitest/config';
export default defineConfig({ base: './', ...(process.env.DAWLOOP_TEST_OUTPUT_ROOT ? { cacheDir: process.env.DAWLOOP_TEST_OUTPUT_ROOT + '/vite-cache' } : {}), build: { outDir: 'dist' }, test: { environment: 'jsdom', include: ['src/**/*.test.tsx'] } });
