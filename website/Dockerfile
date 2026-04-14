# Tesseract Website - Production Dockerfile
# Multi-stage build for Astro static site

# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source files
COPY . .

# Build arguments for environment variables
# Default to /api for embedded deployment (proxied through nginx)
ARG PUBLIC_API_URL=/api
ARG PUBLIC_METRICS_URL=/metrics

# Set environment variables for build
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
ENV PUBLIC_METRICS_URL=${PUBLIC_METRICS_URL}

# Build the site
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
