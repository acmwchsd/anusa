<script lang="ts">
	import '@fontsource/b612/latin-400.css';
	import '@fontsource/b612/latin-700.css';
	import '@fontsource/b612-mono/latin-400.css';
	import '@fontsource/b612-mono/latin-700.css';
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import Toasts from '#lib/components/Toasts.svelte';
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	liveConnection.connect();

	const navigationLinks = [
		{ href: resolve('/'), label: 'Live' },
		{ href: resolve('/students'), label: 'Students' },
		{ href: resolve('/photos'), label: 'Photos' }
	];

	const SERVER_STATUS_DISPLAY = {
		idle: { text: 'Connecting…', lamp: 'wait' },
		connecting: { text: 'Connecting…', lamp: 'wait' },
		open: { text: 'Connected', lamp: 'ok' },
		closed: { text: 'Offline', lamp: 'fault' }
	};
	const serverStatusDisplay = $derived(SERVER_STATUS_DISPLAY[liveConnection.connectionStatus]);
	const whisperStatusDisplay = $derived(
		liveConnection.speechStatus?.available
			? { text: 'Ready', lamp: 'ok' }
			: { text: 'Not running', lamp: 'wait' }
	);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Techpreneure Cam</title>
</svelte:head>

<header>
	<a class="brand" href={resolve('/')}>Techpreneure Cam</a>
	<nav>
		{#each navigationLinks as navigationLink (navigationLink.href)}
			<a href={navigationLink.href} aria-current={page.url.pathname === navigationLink.href ? 'page' : undefined}
				>{navigationLink.label}</a
			>
		{/each}
	</nav>
	<dl class="status">
		<div title="Connection to the recognition server: {liveConnection.connectionStatus}">
			<dt>Server</dt>
			<dd class={serverStatusDisplay.lamp}>{serverStatusDisplay.text}</dd>
		</div>
		{#if liveConnection.speechStatus}
			<div title="Speech recognition for the voice trigger">
				<dt>Whisper</dt>
				<dd class={whisperStatusDisplay.lamp}>{whisperStatusDisplay.text}</dd>
			</div>
		{/if}
	</dl>
</header>

<main class:console={page.url.pathname === resolve('/')}>
	{@render children()}
</main>

<Toasts />

<style>
	header {
		position: sticky;
		top: 0;
		z-index: 20;
		height: var(--header-h);
		display: flex;
		align-items: stretch;
		gap: 24px;
		padding: 0 14px;
		background: var(--panel);
		border-bottom: 1px solid var(--border-strong);
	}
	.brand {
		align-self: center;
		font-weight: 700;
		font-size: 0.92em;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		text-decoration: none;
		white-space: nowrap;
	}
	nav {
		display: flex;
	}
	nav a {
		display: flex;
		align-items: center;
		padding: 0 14px;
		font-family: var(--font-data);
		font-size: 0.8em;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		text-decoration: none;
		color: var(--muted);
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
	}
	nav a:hover {
		color: var(--text);
	}
	nav a[aria-current='page'] {
		color: var(--text);
		border-bottom-color: var(--accent);
	}
	.status {
		margin: 0 0 0 auto;
		display: flex;
		align-items: center;
		gap: 20px;
		font-family: var(--font-data);
		font-size: 0.76em;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.status div {
		display: flex;
		align-items: center;
		gap: 7px;
	}
	dt {
		color: var(--faint);
	}
	dd {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 6px;
		white-space: nowrap;
	}
	dd::before {
		content: '';
		width: 7px;
		height: 7px;
		background: currentColor;
	}
	dd.ok {
		color: var(--accent);
	}
	dd.wait {
		color: var(--warn);
	}
	dd.fault {
		color: var(--danger);
	}
	main {
		padding: 16px 18px;
		max-width: 1720px;
		margin: 0 auto;
	}
	main.console {
		padding: 0;
		max-width: none;
	}
	@media (max-width: 760px) {
		header {
			gap: 8px;
			padding: 0 10px;
		}
		.brand,
		dt {
			display: none;
		}
		nav a {
			padding: 0 8px;
		}
		.status {
			gap: 10px;
		}
		dd {
			font-size: 0;
			gap: 0;
		}
		main {
			padding: 12px;
		}
	}
</style>
