import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    outDir: '../server/src/vic_rego_estimator/static/widget',
    emptyOutDir: true
  }
});
