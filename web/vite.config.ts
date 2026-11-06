import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// During `npm run dev`, the REST API (/api) and the live stream (/ws) are proxied to the backend.
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8004';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Runes mode for this project's files, but not for libraries. Can be removed in Svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// A single-page app: unknown paths fall back to index.html, which routes in the browser.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: {
			'/api': BACKEND_URL,
			'/ws': { target: BACKEND_URL.replace(/^http/, 'ws'), ws: true }
		}
	}
});
