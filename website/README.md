# Tesseract Protocol Website

Marketing website and live dashboard for the Tesseract cross-rollup atomic swap protocol.

## Tech Stack

- **Framework**: [Astro](https://astro.build/) 5.x with static site generation
- **UI Components**: [Vue.js](https://vuejs.org/) 3.x islands for interactive features
- **Styling**: [TailwindCSS](https://tailwindcss.com/) 3.x with custom design system
- **Deployment**: Docker + Nginx, CapRover-ready

## Features

- GEO-optimized content structure for AI search engines (ChatGPT, Perplexity)
- FAQPage schema markup for rich results
- Live dashboard connected to Tesseract relayer API
- Dark mode support
- Mobile-responsive design
- Sitemap generation

## Commands

| Command           | Action                                      |
| :---------------- | :------------------------------------------ |
| `npm install`     | Install dependencies                        |
| `npm run dev`     | Start dev server at `localhost:4321`        |
| `npm run build`   | Build production site to `./dist/`          |
| `npm run preview` | Preview production build locally            |

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
PUBLIC_API_URL=http://localhost:8080      # Relayer API endpoint
PUBLIC_METRICS_URL=http://localhost:9090  # Prometheus metrics endpoint
```

## Project Structure

```
src/
├── components/
│   ├── common/        # Header, Footer, SEO, JsonLd
│   ├── landing/       # Hero, Features, HowItWorks, Networks, FAQ
│   ├── vue/           # Interactive Vue.js components
│   │   └── dashboard/ # LiveDashboard, ChainStatusCard, TransactionStats
│   └── docs/          # Documentation components
├── composables/       # Vue composables for API data fetching
├── content/           # MDX content (docs, blog)
├── layouts/           # Astro layouts (BaseLayout, DocsLayout)
├── lib/               # API client, constants, utilities
├── pages/             # Astro pages
│   ├── compare/       # Comparison pages (vs bridges, vs DEXs)
│   ├── docs/          # Documentation pages
│   └── dashboard.astro
└── styles/            # Global CSS with Tailwind
```

## Deployment

### CapRover

The project includes a `captain-definition` file for CapRover deployment:

1. Create a new app in CapRover
2. Set environment variables:
   - `PUBLIC_API_URL`: Your relayer API endpoint
3. Deploy using CapRover CLI or GitHub integration

### Docker

```bash
# Build image
docker build -t tesseract-website \
  --build-arg PUBLIC_API_URL=https://api.tesseract.io \
  .

# Run container
docker run -p 80:80 tesseract-website
```

## Content Guidelines (GEO/AI Optimization)

Every content page follows this structure:

1. **Quick Answer** (40-80 words): Direct answer to the page's core query
2. **Key Facts**: Bullet points with specific, extractable information
3. **Detailed Sections**: Question-based H2/H3 headers
4. **Comparison Table**: Where applicable
5. **FAQ Section**: 5-10 questions with FAQPage schema

## Pages

| Page | Purpose | Schema |
|------|---------|--------|
| `/` | Landing page | SoftwareApplication, FAQPage |
| `/dashboard` | Live relayer monitoring | - |
| `/docs` | Documentation hub | Article |
| `/compare/vs-bridges` | Bridge comparison | FAQPage |
| `/compare/vs-dexs` | DEX comparison | FAQPage |
