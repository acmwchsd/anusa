<script lang="ts">
	import { activeToasts, dismissToast } from '#lib/toasts.svelte.ts';
	import { fly } from 'svelte/transition';

	let popoverElement: HTMLDivElement | undefined = $state();

	// A manual popover lives in the browser's top layer. Showing it again for every new toast
	// lifts it above any modal dialog opened since, such as the photo viewer.
	$effect(() => {
		const toastCount = activeToasts.length;
		if (!popoverElement) return;
		if (popoverElement.matches(':popover-open')) popoverElement.hidePopover();
		if (toastCount) popoverElement.showPopover();
	});
</script>

<div class="toasts" popover="manual" bind:this={popoverElement} aria-live="polite">
	{#each activeToasts as toast (toast.id)}
		<button
			class="toast {toast.kind}"
			onclick={() => dismissToast(toast.id)}
			transition:fly={{ x: 20, duration: 120 }}
		>
			{#if toast.imageUrl}
				<img src={toast.imageUrl} alt="" />
			{/if}
			<span class="text">
				<strong>{toast.title}</strong>
				{#if toast.detail}<span class="muted small">{toast.detail}</span>{/if}
			</span>
		</button>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		inset: auto 16px 16px auto;
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		overflow: visible;
		display: flex;
		flex-direction: column;
		gap: 10px;
		z-index: 100;
		max-width: min(380px, calc(100vw - 32px));
	}
	.toast {
		display: flex;
		align-items: center;
		gap: 12px;
		text-align: left;
		padding: 6px 12px 6px 6px;
		background: var(--panel-2);
		border: 1px solid var(--border-strong);
		border-left: 2px solid var(--muted);
		cursor: pointer;
	}
	.toast.success {
		border-left-color: var(--accent);
	}
	.toast.error {
		border-left-color: var(--danger);
	}
	img {
		width: 56px;
		height: 38px;
		object-fit: cover;
		flex: none;
	}
	.text {
		display: flex;
		flex-direction: column;
		min-width: 0;
		padding-left: 4px;
	}
</style>
