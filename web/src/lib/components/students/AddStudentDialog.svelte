<script lang="ts">
	import { api, type Person } from '#lib/api-client.ts';
	import { showErrorToast } from '#lib/toasts.svelte.ts';

	let { onPersonCreated }: { onPersonCreated: (newPerson: Person) => void } = $props();

	let dialogElement: HTMLDialogElement | undefined = $state();
	let enteredName = $state('');

	export function open() {
		dialogElement?.showModal();
	}

	async function createStudent(event: SubmitEvent) {
		event.preventDefault();
		try {
			const newPerson = await api.createPerson(enteredName.trim());
			enteredName = '';
			dialogElement?.close();
			onPersonCreated(newPerson);
		} catch (error) {
			showErrorToast(error, 'Could not add student');
		}
	}
</script>

<dialog bind:this={dialogElement} closedby="any">
	<form onsubmit={createStudent}>
		<div class="dialog-head">
			<h2>Add a student</h2>
		</div>
		<div class="dialog-body">
			<label class="field">
				<span class="muted small">Name, as it should appear on the camera</span>
				<!-- svelte-ignore a11y_autofocus -->
				<input type="text" bind:value={enteredName} placeholder="e.g. Sophea Chan" autofocus maxlength="80" />
			</label>
		</div>
		<div class="dialog-foot">
			<button type="button" class="btn ghost" onclick={() => dialogElement?.close()}>Cancel</button>
			<button class="btn primary" disabled={!enteredName.trim()}>Continue — take photos</button>
		</div>
	</form>
</dialog>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.field input {
		font-size: 1.1em;
	}
</style>
