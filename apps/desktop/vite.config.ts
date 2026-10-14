import { defineConfig } from 'vitest/config';
import {searchForWorkspaceRoot} from 'vite';
import {fileURLToPath} from 'node:url';
export default defineConfig({ base: './', server:{fs:{allow:[searchForWorkspaceRoot(process.cwd()),fileURLToPath(new URL('../../LICENSES/basic-pitch',import.meta.url))]}}, ...(process.env.DAWLOOP_TEST_OUTPUT_ROOT ? { cacheDir: process.env.DAWLOOP_TEST_OUTPUT_ROOT + '/vite-cache' } : {}), build: { outDir: 'dist' }, test: { environment: 'jsdom', include: ['src/**/*.test.tsx'] } });
