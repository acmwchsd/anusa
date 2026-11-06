<!-- Who the camera sees right now: a scope for where they are, and a table for who they are. -->
<script lang="ts">
	import { personAvatarUrl, type Person } from '#lib/api-client.ts';
	import TargetRadar from '#lib/components/live/TargetRadar.svelte';
	import SidePanel from '#lib/components/SidePanel.svelte';
	import { liveConnection, type LiveFace } from '#lib/live-connection.svelte.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import { resolve } from '$app/paths';

	const MAXIMUM_VISIBLE_ROWS = 8;

	let { people }: { people: Person[] } = $props();

	const peopleById = $derived(new Map(people.map((person) => [person.id, person])));
	const facesInFrame = $derived(liveConnection.latestFrameAnalysis?.faces ?? []);

	/** Identified faces first, then unknown, then too far away to tell. */
	const displayRank = (face: LiveFace) => (face.name ? 0 : face.small ? 2 : 1);
	const sortedFaces = $derived(
		[...facesInFrame].sort(
			(firstFace, secondFace) => displayRank(firstFace) - displayRank(secondFace) || firstFace.track - secondFace.track
		)
	);
	const hiddenRowCount = $derived(sortedFaces.length - MAXIMUM_VISIBLE_ROWS);

	const faceLabel = (face: LiveFace) => face.name ?? (face.small ? 'Too far' : 'Unknown');
	const matchPercent = (face: LiveFace) =>
		face.name && face.similarity !== null ? `${Math.round(face.similarity * 100)}%` : '—';
</script>

<SidePanel title="In frame">
	<TargetRadar frameAnalysis={liveConnection.latestFrameAnalysis} isMirrored={preferences.mirrorPreview} />

	{#if sortedFaces.length}
		<table>
			<thead>
				<tr><th>Trk</th><th>Name</th><th class="num">Match</th></tr>
			</thead>
			<tbody>
				{#each sortedFaces.slice(0, MAXIMUM_VISIBLE_ROWS) as face (face.track)}
					{@const avatarUrl = personAvatarUrl(peopleById.get(face.person_id ?? ''))}
					<tr class:unknown={!face.name && !face.small} class:far={!face.name && face.small}>
						<td class="id">{String(face.track).padStart(3, '0')}</td>
						<td class="name">
							{#if avatarUrl}<img src={avatarUrl} alt="" />{/if}
							<span>{faceLabel(face)}</span>
						</td>
						<td class="num">{matchPercent(face)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if hiddenRowCount > 0}<p class="faint small more">+{hiddenRowCount} more</p>{/if}
	{:else}
		<p class="muted small empty">
			{#if people.length === 0}
				No students enrolled yet. <a href={resolve('/students')}>Add your class</a> to see names here.
			{:else}
				Nobody in frame.
			{/if}
		</p>
	{/if}
</SidePanel>

<style>
	table {
		width: 100%;
		margin-top: 8px;
		border-collapse: collapse;
		font-family: var(--font-data);
		font-size: 0.82em;
		table-layout: fixed;
	}
	th {
		padding: 2px 0;
		font-size: 0.86em;
		font-weight: 400;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		text-align: left;
		color: var(--faint);
		border-bottom: 1px solid var(--border-strong);
	}
	th:first-child {
		width: 38px;
	}
	th.num {
		width: 52px;
	}
	td {
		height: 24px;
		padding: 0;
		border-bottom: 1px solid var(--border);
		color: var(--accent);
	}
	tr.unknown td {
		color: var(--warn);
	}
	tr.far td {
		color: var(--faint);
	}
	.id {
		color: var(--muted);
	}
	.name {
		overflow: hidden;
		white-space: nowrap;
	}
	.name > * {
		vertical-align: middle;
	}
	.name span {
		overflow: hidden;
		text-overflow: ellipsis;
	}
	img {
		width: 18px;
		height: 18px;
		margin-right: 6px;
		object-fit: cover;
	}
	.num {
		text-align: right;
	}
	.more {
		margin: 4px 0 0;
		font-family: var(--font-data);
	}
	.empty {
		margin: 8px 0 0;
	}
</style>
