<!-- Bulk import: review the students found in the selected files, then add them all. -->
<script lang="ts">
	import { api, type Person } from '#lib/api-client.ts';
	import { errorMessage, pluralize } from '#lib/formatting.ts';
	import { normalizeUploadedImage } from '#lib/media.ts';
	import { groupFilesByStudent, type StudentImportGroup } from '#lib/student-import.ts';
	import { showToast } from '#lib/toasts.svelte.ts';

	interface Props {
		people: Person[];
		/** A student was created or received new reference photos. */
		onPersonUpdated: (updatedPerson: Person) => void;
	}
	let { people, onPersonUpdated }: Props = $props();

	interface ImportRow extends StudentImportGroup {
		/** Also used as the row's CSS class. */
		status: 'ready' | 'working' | 'done' | 'error';
		resultNote?: string;
	}

	let dialogElement: HTMLDialogElement | undefined = $state();
	let importRows: ImportRow[] = $state([]);
	let isImporting = $state(false);

	export function open(selectedFiles: FileList | null) {
		importRows = groupFilesByStudent(selectedFiles ?? []).map((group) => ({ ...group, status: 'ready' }));
		if (importRows.length) dialogElement?.showModal();
		else showToast({ kind: 'error', title: 'No images found in that selection' });
	}

	async function importStudent(importRow: ImportRow) {
		importRow.status = 'working';
		try {
			const name = importRow.name.trim();
			const existingPerson = people.find((person) => person.name.toLowerCase() === name.toLowerCase());
			const person = existingPerson ?? (await api.createPerson(name));
			const normalizedImages = await Promise.all(importRow.files.map((file) => normalizeUploadedImage(file)));
			const result = await api.addReferencePhotos(person.id, normalizedImages, 'upload');
			onPersonUpdated(result.person);
			importRow.status = result.added.length ? 'done' : 'error';
			importRow.resultNote = result.rejected.length
				? `${result.added.length} added, ${result.rejected.length} skipped (${result.rejected[0].error})`
				: `${result.added.length} added`;
		} catch (error) {
			importRow.status = 'error';
			importRow.resultNote = errorMessage(error);
		}
	}

	async function importAllStudents() {
		isImporting = true;
		for (const importRow of importRows) {
			if (importRow.status !== 'done' && importRow.name.trim()) await importStudent(importRow);
		}
		isImporting = false;
		const importedCount = importRows.filter((importRow) => importRow.status === 'done').length;
		showToast({
			kind: importedCount ? 'success' : 'error',
			title: `Imported ${importedCount} of ${pluralize(importRows.length, 'student')}`
		});
	}

	function describeRowStatus(importRow: ImportRow) {
		if (importRow.status === 'working') return 'Learning…';
		if (importRow.status === 'ready') return '';
		return importRow.resultNote ?? '';
	}
</script>

<dialog bind:this={dialogElement} closedby={isImporting ? 'none' : 'any'}>
	<div class="dialog-head">
		<h2>Import {pluralize(importRows.length, 'student')}</h2>
	</div>
	<div class="dialog-body">
		<p class="muted small">
			Names come from file or folder names — fix any before importing. Existing students get the new photos added.
		</p>
		<ul class="rows">
			{#each importRows as importRow, rowIndex (rowIndex)}
				<li class={importRow.status}>
					<input
						type="text"
						bind:value={importRow.name}
						disabled={isImporting || importRow.status === 'done'}
						aria-label="Name"
					/>
					<span class="muted small">{pluralize(importRow.files.length, 'photo')}</span>
					<span class="status small">{describeRowStatus(importRow)}</span>
				</li>
			{/each}
		</ul>
	</div>
	<div class="dialog-foot">
		<button class="btn ghost" disabled={isImporting} onclick={() => dialogElement?.close()}>Close</button>
		<button
			class="btn primary"
			disabled={isImporting || importRows.every((importRow) => importRow.status === 'done')}
			onclick={importAllStudents}
		>
			{isImporting ? 'Importing…' : 'Import'}
		</button>
	</div>
</dialog>

<style>
	.rows {
		list-style: none;
		margin: 12px 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-height: 50vh;
		overflow: auto;
	}
	li {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 80px minmax(0, 1fr);
		gap: 10px;
		align-items: center;
	}
	li.done .status {
		color: var(--accent);
	}
	li.error .status {
		color: var(--danger);
	}
</style>
