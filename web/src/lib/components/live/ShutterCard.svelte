<script lang="ts">
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { preferences } from '#lib/preferences.svelte.ts';

	interface Props {
		disabled: boolean;
		onTakePhoto: () => void;
	}
	let { disabled, onTakePhoto }: Props = $props();
</script>

<div class="shutter-card">
	<button class="btn primary shutter" onclick={onTakePhoto} {disabled}>
		Take photo
		<kbd>Space</kbd>
	</button>
	<p class="muted small">
		Or say “{liveConnection.keywords[0]}”.{#if preferences.countdownSeconds}
			&nbsp;{preferences.countdownSeconds}s countdown.{/if}
	</p>
</div>

<style>
	.shutter-card {
		padding: 12px 14px;
		border-bottom: 1px solid var(--border-strong);
	}
	.shutter {
		width: 100%;
		justify-content: space-between;
		padding: 0.8em 1em;
		font-size: 0.92em;
	}
	.shutter kbd {
		border-color: rgb(7 19 10 / 0.5);
		background: transparent;
		font-weight: 400;
	}
	p {
		margin: 6px 0 0;
	}
</style>
