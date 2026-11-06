<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		/** folded until its title is clicked */
		collapsible?: boolean;
		/** shown to the right of the title */
		aside?: Snippet;
		children: Snippet;
	}
	let { title, collapsible = false, aside, children }: Props = $props();
</script>

{#if collapsible}
	<details class="section">
		<summary><h3>{title}</h3></summary>
		{@render children()}
	</details>
{:else}
	<section class="section">
		<div class="head">
			<h3>{title}</h3>
			{@render aside?.()}
		</div>
		{@render children()}
	</section>
{/if}

<style>
	.section {
		padding: 9px 14px 12px;
		border-bottom: 1px solid var(--border-strong);
	}
	details.section {
		padding-bottom: 9px;
	}
	.head,
	summary {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}
	.head {
		margin-bottom: 8px;
	}
	h3 {
		font-family: var(--font-data);
		font-size: 0.76em;
		font-weight: 400;
		letter-spacing: 0.1em;
		color: var(--muted);
	}
	summary {
		cursor: pointer;
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary::after {
		content: '+';
		font-family: var(--font-data);
		color: var(--muted);
	}
	details[open] summary::after {
		content: '−';
	}
	details[open] summary {
		margin-bottom: 10px;
	}
</style>
