// @ts-check
import { defineConfig } from 'astro/config';
import vue from '@astrojs/vue';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// https://astro.build/config
export default defineConfig({
  site: 'https://tesseract.io',
  integrations: [
    vue(),
    tailwind(),
    sitemap({
      filter: (page) => !page.includes('/dashboard'),
      changefreq: 'weekly',
      priority: 0.7,
    }),
    mdx(),
  ],
  vite: {
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@lib': path.resolve(__dirname, './src/lib'),
        '@components': path.resolve(__dirname, './src/components'),
      },
    },
    ssr: {
      noExternal: ['@heroicons/vue'],
    },
  },
});
