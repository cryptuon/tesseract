// @ts-check
import { defineConfig } from 'astro/config';
import vue from '@astrojs/vue';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';

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
    ssr: {
      noExternal: ['@heroicons/vue'],
    },
  },
});
