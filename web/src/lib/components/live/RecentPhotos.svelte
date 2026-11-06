<script lang="ts">
	import type { Photo } from '#lib/api-client.ts';
	import SidePanel from '#lib/components/SidePanel.svelte';
	import { resolve } from '$app/paths';

	let { photos }: { photos: Photo[] } = $props();
</script>

<SidePanel title="Latest photos">
	{#snippet aside()}
		<a class="small muted" href={resolve('/photos')}>All photos →</a>
	{/snippet}

	<div class="recent">
		{#each photos as photo (photo.id)}
			<a href={resolve('/photos')} title={photo.people.join(', ') || 'No one recognised'}>
				<img src={photo.url} alt="" loading="lazy" />
			</a>
		{/each}
	</div>
</SidePanel>

<style>
	.recent {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 2px;
	}
	img {
		width: 100%;
		aspect-ratio: 4 / 3;
		object-fit: cover;
		display: block;
	}
	a:hover img {
		outline: 1px solid var(--muted);
		outline-offset: -1px;
	}
</style>
