<!-- One student: rename, remove, and manage their reference photos. -->
<script lang="ts">
	import {
		api,
		MINIMUM_REFERENCE_PHOTOS,
		referencePhotoUrl,
		type AddReferencePhotosResult,
		type Person
	} from '#lib/api-client.ts';
	import CameraCapture from '#lib/components/CameraCapture.svelte';
	import { pluralize } from '#lib/formatting.ts';
	import { normalizeUploadedImage } from '#lib/media.ts';
	import { showErrorToast, showToast } from '#lib/toasts.svelte.ts';

	type DialogView = 'reference-photos' | 'camera';

	interface Props {
		people: Person[];
		onPersonUpdated: (updatedPerson: Person) => void;
		onPersonRemoved: (personId: string) => void;
	}
	let { people, onPersonUpdated, onPersonRemoved }: Props = $props();

	let dialogElement: HTMLDialogElement | undefined = $state();
	let selectedPersonId: string | null = $state(null);
	const selectedPerson = $derived(people.find((person) => person.id === selectedPersonId) ?? null);
	let currentView: DialogView = $state('reference-photos');
	let isAddingPhotos = $state(false);
	let lastAddResult: AddReferencePhotosResult | null = $state(null);

	export function open(person: Person, initialView: DialogView = 'reference-photos') {
		selectedPersonId = person.id;
		currentView = initialView;
		lastAddResult = null;
		dialogElement?.showModal();
	}

	function closeDialog() {
		currentView = 'reference-photos';
		dialogElement?.close();
	}

	/** Esc or a click outside: leave the camera view so the camera stops. */
	function handleDialogClosed() {
		// The close event arrives late, so the dialog may already be open again.
		if (!dialogElement?.open) currentView = 'reference-photos';
	}

	async function renameStudent(person: Person, nameInput: HTMLInputElement) {
		const newName = nameInput.value.trim();
		if (!newName || newName === person.name) {
			nameInput.value = person.name;
			return;
		}
		try {
			onPersonUpdated(await api.renamePerson(person.id, newName));
		} catch (error) {
			nameInput.value = person.name;
			showErrorToast(error, 'Rename failed');
		}
	}

	async function removeStudent(person: Person) {
		const confirmationMessage = `Remove ${person.name} and their ${pluralize(person.samples.length, 'reference photo')}?`;
		if (!confirm(confirmationMessage)) return;
		try {
			await api.deletePerson(person.id);
			onPersonRemoved(person.id);
			closeDialog();
			showToast({ kind: 'info', title: `${person.name} removed` });
		} catch (error) {
			showErrorToast(error, 'Could not remove');
		}
	}

	async function addReferencePhotos(person: Person, images: Blob[], source: 'upload' | 'camera') {
		isAddingPhotos = true;
		try {
			const imagesToSend =
				source === 'upload'
					? await Promise.all(images.map((image) => normalizeUploadedImage(image as File)))
					: images;
			const result = await api.addReferencePhotos(person.id, imagesToSend, source);
			lastAddResult = result;
			onPersonUpdated(result.person);
			if (result.added.length) currentView = 'reference-photos';
		} catch (error) {
			showErrorToast(error, 'Could not add photos');
		} finally {
			isAddingPhotos = false;
		}
	}

	async function deleteReferencePhoto(person: Person, referencePhotoId: string) {
		try {
			await api.deleteReferencePhoto(person.id, referencePhotoId);
			const remainingPhotos = person.samples.filter((referencePhoto) => referencePhoto.id !== referencePhotoId);
			onPersonUpdated({ ...person, samples: remainingPhotos });
		} catch (error) {
			showErrorToast(error, 'Could not delete');
		}
	}

	function uploadSelectedFiles(person: Person, fileInput: HTMLInputElement) {
		const selectedFiles = [...(fileInput.files ?? [])];
		fileInput.value = '';
		if (selectedFiles.length) addReferencePhotos(person, selectedFiles, 'upload');
	}

	function switchToCamera() {
		currentView = 'camera';
		lastAddResult = null;
	}
</script>

<dialog bind:this={dialogElement} closedby="any" onclose={handleDialogClosed}>
	{#if selectedPerson}
		{@const person = selectedPerson}
		<div class="dialog-head">
			<input
				class="title-input"
				type="text"
				value={person.name}
				aria-label="Student name"
				onchange={(event) => renameStudent(person, event.currentTarget)}
				onkeydown={(event) => event.key === 'Enter' && event.currentTarget.blur()}
			/>
			<button class="btn ghost" onclick={closeDialog} aria-label="Close">✕</button>
		</div>
		<div class="dialog-body">
			{#if currentView === 'camera'}
				<CameraCapture
					isBusy={isAddingPhotos}
					onPhotosCaptured={(capturedPhotos) => addReferencePhotos(person, capturedPhotos, 'camera')}
				/>
				<p class="muted small center">
					Frame one face inside the oval. Five photos are taken a second apart — follow the prompts.
				</p>
			{:else}
				{#if person.samples.length}
					<ul class="samples">
						{#each person.samples as referencePhoto (referencePhoto.id)}
							<li>
								<img src={referencePhotoUrl(person.id, referencePhoto.id)} alt="Reference of {person.name}" />
								<button
									class="del"
									aria-label="Delete this photo"
									onclick={() => deleteReferencePhoto(person, referencePhoto.id)}>✕</button
								>
								<span class="src">
									{referencePhoto.source.startsWith('photo:') ? 'from photo' : referencePhoto.source}
								</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="muted">No reference photos yet.</p>
				{/if}
				<p class="muted small">
					{person.samples.length < MINIMUM_REFERENCE_PHOTOS
						? `Add at least ${MINIMUM_REFERENCE_PHOTOS} photos from slightly different angles for reliable recognition.`
						: 'Recognition improves with variety: different days, lighting, glasses on and off.'}
				</p>
			{/if}

			{#if lastAddResult}
				<div class="result">
					{#if lastAddResult.added.length}
						<p class="ok">✓ Learned {pluralize(lastAddResult.added.length, 'photo')}.</p>
					{/if}
					{#each lastAddResult.added.filter((addedPhoto) => addedPhoto.warning) as addedPhoto (addedPhoto.sample.id)}
						<p class="warn small">⚠ {addedPhoto.file}: {addedPhoto.warning}</p>
					{/each}
					{#each lastAddResult.rejected as rejectedFile, rejectedIndex (rejectedIndex)}
						<p class="bad small">✕ {rejectedFile.file}: {rejectedFile.error}</p>
					{/each}
				</div>
			{/if}
		</div>
		<div class="dialog-foot split">
			<button class="btn danger" onclick={() => removeStudent(person)}>Remove student</button>
			<div class="actions">
				{#if currentView === 'camera'}
					<button class="btn" onclick={() => (currentView = 'reference-photos')}>Done</button>
				{:else}
					<label class="btn" class:disabled={isAddingPhotos}>
						{isAddingPhotos ? 'Learning…' : 'Upload photos'}
						<input
							class="visually-hidden"
							type="file"
							accept="image/*"
							multiple
							disabled={isAddingPhotos}
							onchange={(event) => uploadSelectedFiles(person, event.currentTarget)}
						/>
					</label>
					<button class="btn primary" onclick={switchToCamera}>Use camera</button>
				{/if}
			</div>
		</div>
	{/if}
</dialog>

<style>
	.title-input {
		font-size: 1.1em;
		font-weight: 700;
		border-color: transparent !important;
		background: transparent !important;
		padding-left: 0 !important;
		flex: 1;
	}
	.title-input:focus {
		border-bottom: 1px solid var(--accent) !important;
	}
	.samples {
		list-style: none;
		margin: 0 0 12px;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
		gap: 10px;
	}
	.samples li {
		position: relative;
	}
	.samples img {
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		display: block;
	}
	.del {
		position: absolute;
		top: 4px;
		right: 4px;
		width: 24px;
		height: 24px;
		border: 1px solid var(--border-strong);
		background: rgb(0 0 0 / 0.72);
		color: var(--danger);
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s;
	}
	.samples li:hover .del,
	.del:focus-visible {
		opacity: 1;
	}
	/* a touch screen has no hover to reveal it */
	@media (hover: none) {
		.del {
			opacity: 1;
		}
	}
	.src {
		position: absolute;
		left: 6px;
		bottom: 5px;
		font-family: var(--font-data);
		font-size: 0.7em;
		text-transform: uppercase;
		padding: 0 5px;
		background: rgb(0 0 0 / 0.66);
	}
	.center {
		text-align: center;
	}
	.result {
		margin-top: 12px;
		padding: 10px 12px;
		border-left: 2px solid var(--border-strong);
		background: var(--panel-2);
	}
	.result p {
		margin: 2px 0;
	}
	.ok {
		color: var(--accent);
	}
	.warn {
		color: var(--warn);
	}
	.bad {
		color: var(--danger);
	}
	.split {
		justify-content: space-between;
	}
	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}
	label.btn.disabled {
		opacity: 0.5;
		pointer-events: none;
	}
</style>
