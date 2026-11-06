<!-- Full-size photo: step through the list, delete it, and name the faces in it. -->
<script lang="ts">
	import { api, type FaceLabel, type Person, type Photo, type PhotoFace } from '#lib/api-client.ts';
	import { describePhotoTrigger, formatTakenAt } from '#lib/formatting.ts';
	import { showErrorToast, showToast } from '#lib/toasts.svelte.ts';

	interface Props {
		/** The photos being browsed, in order. */
		photos: Photo[];
		people: Person[];
		onPhotoUpdated: (updatedPhoto: Photo) => void;
		onPhotoDeleted: (photoId: string) => void;
	}
	let { photos, people, onPhotoUpdated, onPhotoDeleted }: Props = $props();

	let dialogElement: HTMLDialogElement | undefined = $state();
	let currentPhotoId: string | null = $state(null);
	const currentPhoto = $derived(photos.find((photo) => photo.id === currentPhotoId) ?? null);
	const currentPhotoIndex = $derived(currentPhoto ? photos.indexOf(currentPhoto) : -1);
	let showFaceLabels = $state(true);
	let faceBeingNamed: PhotoFace | null = $state(null);
	let enteredName = $state('');
	let isSaving = $state(false);

	export function open(photo: Photo) {
		currentPhotoId = photo.id;
		faceBeingNamed = null;
		dialogElement?.showModal();
	}

	function moveBy(offset: number) {
		const targetPhoto = photos[currentPhotoIndex + offset];
		if (targetPhoto) {
			currentPhotoId = targetPhoto.id;
			faceBeingNamed = null;
		}
	}

	function handleKeyDown(event: KeyboardEvent) {
		const isTyping = (event.target as HTMLElement).closest('input, select');
		if (!dialogElement?.open || isTyping) return;
		if (event.key === 'ArrowRight') moveBy(1);
		if (event.key === 'ArrowLeft') moveBy(-1);
	}

	async function deletePhoto(photo: Photo) {
		if (!confirm('Delete this photo?')) return;
		try {
			await api.deletePhoto(photo.id);
			const nextPhotoToShow = photos[currentPhotoIndex + 1] ?? photos[currentPhotoIndex - 1];
			onPhotoDeleted(photo.id);
			if (nextPhotoToShow) currentPhotoId = nextPhotoToShow.id;
			else dialogElement?.close();
		} catch (error) {
			showErrorToast(error, 'Could not delete');
		}
	}

	function startNamingFace(face: PhotoFace) {
		faceBeingNamed = face;
		enteredName = face.name ?? '';
	}

	async function saveFaceLabel(photo: Photo, face: PhotoFace, faceLabel: FaceLabel) {
		isSaving = true;
		try {
			const updatedPhoto = await api.labelFace(photo.id, face.index, faceLabel);
			onPhotoUpdated(updatedPhoto);
			faceBeingNamed = null;
			const learnedName = updatedPhoto.faces.find((updatedFace) => updatedFace.index === face.index)?.name;
			if (learnedName) {
				showToast({ kind: 'success', title: `Learned ${learnedName}'s face`, detail: 'Added as a reference photo' });
			}
		} catch (error) {
			showErrorToast(error, 'Could not save');
		} finally {
			isSaving = false;
		}
	}

	function submitEnteredName(event: SubmitEvent, photo: Photo, face: PhotoFace) {
		event.preventDefault();
		const name = enteredName.trim();
		if (!name) return;
		const existingPerson = people.find((person) => person.name.toLowerCase() === name.toLowerCase());
		saveFaceLabel(photo, face, existingPerson ? { person_id: existingPerson.id } : { name });
	}

	function faceBoxStyle(photo: Photo, face: PhotoFace) {
		const [boxLeft, boxTop, boxWidth, boxHeight] = face.bbox;
		const toPercent = (value: number, total: number) => `${(value / total) * 100}%`;
		return [
			`left:${toPercent(boxLeft, photo.width)}`,
			`top:${toPercent(boxTop, photo.height)}`,
			`width:${toPercent(boxWidth, photo.width)}`,
			`height:${toPercent(boxHeight, photo.height)}`
		].join(';');
	}

	const downloadFilename = (photo: Photo) => `techpreneure-${photo.taken_at.slice(0, 19).replace(/[:T]/g, '-')}.jpg`;
</script>

<svelte:window onkeydown={handleKeyDown} />

<dialog bind:this={dialogElement} class="viewer" closedby="any" onclose={() => (faceBeingNamed = null)}>
	{#if currentPhoto}
		{@const photo = currentPhoto}
		<div class="viewer-head">
			<div>
				<strong>{formatTakenAt(photo.taken_at)}</strong>
				<span class="muted small">· {describePhotoTrigger(photo)} · {photo.width}×{photo.height}</span>
			</div>
			<div class="tools">
				<label class="small"><input type="checkbox" bind:checked={showFaceLabels} /> Names</label>
				<a class="btn small" href={photo.url} download={downloadFilename(photo)}>Download</a>
				<button class="btn small danger" onclick={() => deletePhoto(photo)}>Delete</button>
				<button class="btn small ghost" onclick={() => dialogElement?.close()} aria-label="Close">✕</button>
			</div>
		</div>
		<div class="viewer-body">
			<button class="nav prev" onclick={() => moveBy(-1)} disabled={currentPhotoIndex <= 0} aria-label="Previous photo"
				>‹</button
			>
			<div class="photo" style:aspect-ratio="{photo.width} / {photo.height}">
				<img src={photo.url} alt="" />
				{#if showFaceLabels}
					{#each photo.faces as face (face.index)}
						<button
							class="face"
							class:known={!!face.name}
							class:active={faceBeingNamed?.index === face.index}
							style={faceBoxStyle(photo, face)}
							onclick={() => startNamingFace(face)}
							title={face.name ? `${face.name} — click to change` : 'Who is this? Click to name'}
						>
							<span class="tag">{face.name ?? '?'}</span>
						</button>
					{/each}
				{/if}
			</div>
			<button
				class="nav next"
				onclick={() => moveBy(1)}
				disabled={currentPhotoIndex >= photos.length - 1}
				aria-label="Next photo">›</button
			>
		</div>
		{#if faceBeingNamed}
			{@const face = faceBeingNamed}
			<form class="namer" onsubmit={(event) => submitEnteredName(event, photo, face)}>
				<span>Who is this?</span>
				<!-- The form appears inside an already-open dialog, where autofocus does nothing. -->
				<input
					type="text"
					list="student-names"
					bind:value={enteredName}
					placeholder="Student name"
					disabled={isSaving}
					{@attach (inputElement) => inputElement.focus()}
				/>
				<datalist id="student-names">
					{#each people as person (person.id)}<option value={person.name}></option>{/each}
				</datalist>
				<button class="btn primary small" disabled={isSaving || !enteredName.trim()}>
					{isSaving ? 'Saving…' : 'Save'}
				</button>
				{#if face.assigned}
					<button type="button" class="btn small ghost" disabled={isSaving} onclick={() => saveFaceLabel(photo, face, null)}
						>Clear label</button
					>
				{/if}
				<button type="button" class="btn small ghost" onclick={() => (faceBeingNamed = null)}>Cancel</button>
				<span class="faint small hint">Naming a face also teaches the camera to recognise them.</span>
			</form>
		{:else}
			<p class="caption muted small">
				{#if photo.faces.length === 0}
					No faces found in this photo.
				{:else}
					{photo.people.length ? `In this photo: ${photo.people.join(', ')}.` : 'No one recognised yet.'}
					{photo.faces.some((face) => !face.name) ? 'Click a “?” to name that student.' : ''}
				{/if}
			</p>
		{/if}
	{/if}
</dialog>

<style>
	.viewer {
		max-width: min(1400px, calc(100vw - 32px));
		background: #000;
	}
	.viewer-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		margin-bottom: 8px;
		padding: 6px 12px;
		background: var(--panel-2);
		border-bottom: 1px solid var(--border-strong);
		font-family: var(--font-data);
		font-size: 0.86em;
	}
	.tools {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.tools label {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-right: 6px;
	}
	.viewer-body {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 0 8px;
	}
	.photo {
		position: relative;
		max-height: calc(100vh - 220px);
		max-width: 100%;
		height: calc(100vh - 220px);
	}
	.photo img {
		width: 100%;
		height: 100%;
		display: block;
	}
	/* the same tracking gates as the live view */
	.face {
		--c: var(--warn);
		--len: min(26%, 12px);
		position: absolute;
		border: 0;
		background:
			linear-gradient(var(--c), var(--c)) 0 0 / var(--len) 1.5px,
			linear-gradient(var(--c), var(--c)) 0 0 / 1.5px var(--len),
			linear-gradient(var(--c), var(--c)) 100% 0 / var(--len) 1.5px,
			linear-gradient(var(--c), var(--c)) 100% 0 / 1.5px var(--len),
			linear-gradient(var(--c), var(--c)) 0 100% / var(--len) 1.5px,
			linear-gradient(var(--c), var(--c)) 0 100% / 1.5px var(--len),
			linear-gradient(var(--c), var(--c)) 100% 100% / var(--len) 1.5px,
			linear-gradient(var(--c), var(--c)) 100% 100% / 1.5px var(--len);
		background-repeat: no-repeat;
		cursor: pointer;
		padding: 0;
	}
	.face.known {
		--c: var(--accent);
	}
	.face.active,
	.face:hover {
		--c: #fff;
	}
	.tag {
		position: absolute;
		left: 50%;
		top: calc(100% + 3px);
		transform: translateX(-50%);
		padding: 0 5px;
		background: rgb(0 0 0 / 0.66);
		color: var(--c);
		font-family: var(--font-data);
		font-size: 12px;
		font-weight: 700;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.nav {
		flex: none;
		width: 34px;
		height: 60px;
		border: 1px solid var(--border-strong);
		background: var(--panel-2);
		color: var(--text);
		font-size: 1.5em;
		cursor: pointer;
	}
	.nav:hover:enabled {
		border-color: var(--muted);
	}
	.nav:disabled {
		opacity: 0.25;
		cursor: default;
	}
	.namer {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
		padding: 12px 16px 16px;
	}
	.namer input {
		width: 220px;
	}
	.hint {
		flex-basis: 100%;
	}
	.caption {
		padding: 12px 16px 16px;
		margin: 0;
	}
	@media (max-width: 700px) {
		.photo {
			height: auto;
		}
		.nav {
			display: none;
		}
	}
</style>
