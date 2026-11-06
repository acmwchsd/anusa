<!-- Students: the class roster. Adding, editing and importing happen in the dialogs. -->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { api, compareByName, MINIMUM_REFERENCE_PHOTOS, personAvatarUrl, type Person } from '#lib/api-client.ts';
	import AddStudentDialog from '#lib/components/students/AddStudentDialog.svelte';
	import ImportDialog from '#lib/components/students/ImportDialog.svelte';
	import StudentDialog from '#lib/components/students/StudentDialog.svelte';
	import { pluralize } from '#lib/formatting.ts';
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { showErrorToast } from '#lib/toasts.svelte.ts';
	import { resolve } from '$app/paths';

	/** Short lists are quicker to scan than to search. */
	const SHOW_SEARCH_FROM_STUDENT_COUNT = 7;
	/** A full bar in the roster: one round of camera capture. */
	const FULL_REFERENCE_PHOTO_COUNT = 5;

	let people: Person[] = $state([]);
	let loadingStatus: 'loading' | 'ready' | 'failed' = $state('loading');
	let searchQuery = $state('');

	let addStudentDialog: AddStudentDialog | undefined = $state();
	let studentDialog: StudentDialog | undefined = $state();
	let importDialog: ImportDialog | undefined = $state();

	const matchingPeople = $derived(
		people.filter((person) => person.name.toLowerCase().includes(searchQuery.trim().toLowerCase()))
	);
	const totalReferencePhotos = $derived(people.reduce((total, person) => total + person.samples.length, 0));

	async function loadPeople() {
		try {
			people = await api.listPeople();
			loadingStatus = 'ready';
		} catch (error) {
			if (loadingStatus === 'loading') loadingStatus = 'failed';
			showErrorToast(error, 'Could not load students');
		}
	}

	onMount(() => {
		loadPeople();
		return liveConnection.on('rosterChanged', loadPeople);
	});

	function upsertPerson(updatedPerson: Person) {
		people = [...people.filter((person) => person.id !== updatedPerson.id), updatedPerson].sort(compareByName);
	}

	function removePerson(personId: string) {
		people = people.filter((person) => person.id !== personId);
	}

	/** A new student goes straight to taking their photos. */
	async function handlePersonCreated(newPerson: Person) {
		upsertPerson(newPerson);
		await tick();
		studentDialog?.open(newPerson, 'camera');
	}

	function openImportDialog(fileInput: HTMLInputElement) {
		importDialog?.open(fileInput.files);
		fileInput.value = '';
	}
</script>

<svelte:head><title>Students · Techpreneure Cam</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Students</h1>
		<p class="muted">
			{pluralize(people.length, 'student')} enrolled · {pluralize(totalReferencePhotos, 'reference photo')}. Each
			student needs a few clear photos of their face.
		</p>
	</div>
	<div class="actions">
		{#if people.length >= SHOW_SEARCH_FROM_STUDENT_COUNT}
			<input type="search" placeholder="Search…" bind:value={searchQuery} aria-label="Search students" />
		{/if}
		<label class="btn">
			Import photos…
			<input
				class="visually-hidden"
				type="file"
				accept="image/*"
				multiple
				onchange={(event) => openImportDialog(event.currentTarget)}
			/>
		</label>
		<label class="btn">
			Import folder…
			<input
				class="visually-hidden"
				type="file"
				webkitdirectory
				multiple
				onchange={(event) => openImportDialog(event.currentTarget)}
			/>
		</label>
		<button class="btn primary" onclick={() => addStudentDialog?.open()}>+ Add student</button>
	</div>
</div>

{#if loadingStatus === 'loading'}
	<p class="muted">Loading students…</p>
{:else if loadingStatus === 'failed'}
	<div class="panel empty-state">
		<h2>Could not load your students</h2>
		<p class="muted">The recognition server is not answering. Check that it is running, then try again.</p>
		<button class="btn primary" onclick={loadPeople}>Try again</button>
	</div>
{:else if people.length === 0}
	<div class="panel empty-state">
		<h2>Enroll your class</h2>
		<p class="muted">
			Add each student with 3–5 photos of their face — taken right here with the camera, or imported from files. Name
			files after the student (<code>alice.jpg</code>, <code>alice_2.jpg</code>) or put each student's photos in a folder
			named after them, then use <strong>Import</strong>.
		</p>
		<p class="muted">
			Already took a class photo? Open it in <a href={resolve('/photos')}>Photos</a> and click each face to name it.
		</p>
		<button class="btn primary" onclick={() => addStudentDialog?.open()}>+ Add the first student</button>
	</div>
{:else if matchingPeople.length === 0}
	<p class="muted">No student matches “{searchQuery.trim()}”.</p>
{:else}
	<div class="roster panel">
		<div class="columns head" aria-hidden="true">
			<span></span>
			<span>Name</span>
			<span>Reference photos</span>
			<span>Status</span>
		</div>
		<ul>
			{#each matchingPeople as person (person.id)}
				{@const avatarUrl = personAvatarUrl(person)}
				{@const needsMorePhotos = person.samples.length < MINIMUM_REFERENCE_PHOTOS}
				<li>
					<button class="columns row" onclick={() => studentDialog?.open(person)}>
						{#if avatarUrl}
							<img class="thumb" src={avatarUrl} alt="" loading="lazy" />
						{:else}
							<span class="thumb initial">{person.name.slice(0, 1)}</span>
						{/if}
						<span class="name">{person.name}</span>
						<span class="samples">
							<span class="pips" aria-hidden="true">
								{#each { length: FULL_REFERENCE_PHOTO_COUNT } as _, pipIndex (pipIndex)}
									<i class:on={pipIndex < person.samples.length}></i>
								{/each}
							</span>
							{pluralize(person.samples.length, 'photo')}
						</span>
						<span class="status" class:warn={needsMorePhotos}>{needsMorePhotos ? 'Add more' : 'Ready'}</span>
					</button>
				</li>
			{/each}
		</ul>
	</div>
{/if}

<AddStudentDialog bind:this={addStudentDialog} onPersonCreated={handlePersonCreated} />
<StudentDialog bind:this={studentDialog} {people} onPersonUpdated={upsertPerson} onPersonRemoved={removePerson} />
<ImportDialog bind:this={importDialog} {people} onPersonUpdated={upsertPerson} />

<style>
	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.columns {
		display: grid;
		grid-template-columns: 36px minmax(0, 1fr) 190px 90px;
		align-items: center;
		gap: 14px;
		padding: 0 12px;
	}
	.head {
		height: 26px;
		background: var(--panel-2);
		border-bottom: 1px solid var(--border-strong);
		font-family: var(--font-data);
		font-size: 0.74em;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--faint);
	}
	.row {
		width: 100%;
		height: 46px;
		border: 0;
		border-bottom: 1px solid var(--border);
		background: none;
		cursor: pointer;
		text-align: left;
	}
	li:last-child .row {
		border-bottom: 0;
	}
	.row:hover {
		background: var(--panel-2);
	}
	.thumb {
		display: block;
		width: 36px;
		height: 36px;
		object-fit: cover;
		background: var(--panel-3);
	}
	.initial {
		display: grid;
		place-items: center;
		font-family: var(--font-data);
		color: var(--muted);
	}
	.name {
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.samples {
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: var(--font-data);
		font-size: 0.82em;
		color: var(--muted);
	}
	.pips {
		display: flex;
		gap: 2px;
	}
	.pips i {
		width: 10px;
		height: 8px;
		background: var(--panel-3);
	}
	.pips i.on {
		background: var(--accent);
	}
	.status {
		font-family: var(--font-data);
		font-size: 0.8em;
		text-transform: uppercase;
		color: var(--accent);
	}
	.status.warn {
		color: var(--warn);
	}
	@media (max-width: 640px) {
		.columns {
			grid-template-columns: 36px minmax(0, 1fr) 70px;
			gap: 10px;
		}
		.head,
		.samples {
			display: none;
		}
	}
</style>
