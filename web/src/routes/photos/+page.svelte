<!-- Photos: everything the camera has taken. Click a photo to open it in the viewer. -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type Person, type Photo } from '#lib/api-client.ts';
	import PhotoViewer from '#lib/components/PhotoViewer.svelte';
	import { describePhotoTrigger, formatTakenAt, pluralize } from '#lib/formatting.ts';
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { showErrorToast } from '#lib/toasts.svelte.ts';
	import { resolve } from '$app/paths';

	let photos: Photo[] = $state([]);
	let people: Person[] = $state([]);
	let loadingStatus: 'loading' | 'ready' | 'failed' = $state('loading');
	let selectedPersonId = $state('');
	let photoViewer: PhotoViewer | undefined = $state();

	const visiblePhotos = $derived(
		selectedPersonId
			? photos.filter((photo) => photo.faces.some((face) => face.person_id === selectedPersonId))
			: photos
	);

	async function loadPhotosAndPeople() {
		try {
			[photos, people] = await Promise.all([api.listPhotos(), api.listPeople()]);
			loadingStatus = 'ready';
		} catch (error) {
			if (loadingStatus === 'loading') loadingStatus = 'failed';
			showErrorToast(error, 'Could not load photos');
		}
	}

	function addNewPhoto(newPhoto: Photo) {
		photos = [newPhoto, ...photos.filter((photo) => photo.id !== newPhoto.id)];
	}

	function replacePhoto(updatedPhoto: Photo) {
		photos = photos.map((photo) => (photo.id === updatedPhoto.id ? updatedPhoto : photo));
	}

	function removePhoto(photoId: string) {
		photos = photos.filter((photo) => photo.id !== photoId);
	}

	onMount(() => {
		loadPhotosAndPeople();
		const unsubscribeAll = [
			liveConnection.on('photoTaken', addNewPhoto),
			liveConnection.on('photoDeleted', removePhoto),
			// A new or renamed student can change the names on every photo.
			liveConnection.on('rosterChanged', loadPhotosAndPeople)
		];
		return () => unsubscribeAll.forEach((unsubscribe) => unsubscribe());
	});
</script>

<svelte:head><title>Photos · Techpreneure Cam</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Photos</h1>
		<p class="muted">
			{pluralize(photos.length, 'photo')} taken. Click a photo to see who is in it, or to name the faces.
		</p>
	</div>
	{#if people.length}
		<label class="filter">
			<span class="muted small">Show photos with</span>
			<select bind:value={selectedPersonId}>
				<option value="">Everyone</option>
				{#each people as person (person.id)}<option value={person.id}>{person.name}</option>{/each}
			</select>
		</label>
	{/if}
</div>

{#if loadingStatus === 'loading'}
	<p class="muted">Loading photos…</p>
{:else if loadingStatus === 'failed'}
	<div class="panel empty-state">
		<h2>Could not load your photos</h2>
		<p class="muted">The recognition server is not answering. Check that it is running, then try again.</p>
		<button class="btn primary" onclick={loadPhotosAndPeople}>Try again</button>
	</div>
{:else if photos.length === 0}
	<div class="panel empty-state">
		<h2>No photos yet</h2>
		<p class="muted">
			Go to <a href={resolve('/')}>Live</a> and say “{liveConnection.keywords[0]}” — or press Space.
		</p>
	</div>
{:else if visiblePhotos.length === 0}
	<div class="panel empty-state">
		<h2>No photos of this student yet</h2>
		<p class="muted">They appear here once the camera recognises them in a photo.</p>
		<button class="btn" onclick={() => (selectedPersonId = '')}>Show everyone</button>
	</div>
{:else}
	<ul class="grid">
		{#each visiblePhotos as photo (photo.id)}
			<li>
				<button class="tile" onclick={() => photoViewer?.open(photo)}>
					<img src={photo.url} alt="Photo with {photo.people.join(', ') || 'unknown people'}" loading="lazy" />
					<span class="meta">
						<span class="names">
							{photo.people.length ? photo.people.join(', ') : pluralize(photo.faces.length, 'face')}
						</span>
						<span class="when">{formatTakenAt(photo.taken_at)} · {describePhotoTrigger(photo)}</span>
					</span>
				</button>
			</li>
		{/each}
	</ul>
{/if}

<PhotoViewer
	bind:this={photoViewer}
	photos={visiblePhotos}
	{people}
	onPhotoUpdated={replacePhoto}
	onPhotoDeleted={removePhoto}
/>

<style>
	.filter {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.grid {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 10px;
	}
	.tile {
		width: 100%;
		padding: 0;
		border: 1px solid var(--border);
		background: var(--panel);
		overflow: hidden;
		cursor: pointer;
		text-align: left;
		display: flex;
		flex-direction: column;
	}
	.tile:hover {
		border-color: var(--muted);
	}
	.tile img {
		width: 100%;
		aspect-ratio: 16 / 10;
		object-fit: cover;
		display: block;
	}
	.meta {
		display: flex;
		flex-direction: column;
		padding: 5px 8px 6px;
		font-family: var(--font-data);
		font-size: 0.82em;
	}
	.names {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.when {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--faint);
	}
</style>
