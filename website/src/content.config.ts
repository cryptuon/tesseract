import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Documentation collection
const docs = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/docs' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    order: z.number().optional(),
    draft: z.boolean().optional().default(false),
    lastUpdated: z.date().optional(),
  }),
});

// Blog collection
const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.date(),
    updatedDate: z.date().optional(),
    author: z.string().optional().default('Tesseract Team'),
    draft: z.boolean().optional().default(false),
    image: z.string().optional(),
    tags: z.array(z.string()).optional().default([]),
  }),
});

export const collections = {
  docs,
  blog,
};
