# syntax=docker/dockerfile:1
# The frontend: the SvelteKit app, built to static files and served by nginx.
# nginx also passes /api and /ws on to the backend (see nginx.conf), so the
# browser talks to one address, just like with `npm run dev`.
#   docker compose up -d --build     (from the repo root: starts the backend too)

# ---- stage 1: build the app -> static files
FROM node:24-slim AS build
WORKDIR /web
COPY package.json package-lock.json .npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

# ---- stage 2: serve them
FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/build /usr/share/nginx/html
EXPOSE 80
