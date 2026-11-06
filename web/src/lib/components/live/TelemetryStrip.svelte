<!-- The readouts under the camera feed, so the picture itself stays clean. -->
<script lang="ts">
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import type { VoiceTrigger } from '#lib/voice-trigger.svelte.ts';

	let { voiceTrigger }: { voiceTrigger: VoiceTrigger } = $props();

	const formatCount = (count: number) => String(count).padStart(2, '0');

	const readouts = $derived.by(() => {
		const frameAnalysis = liveConnection.latestFrameAnalysis;
		const faces = frameAnalysis?.faces ?? [];
		const identifiedCount = faces.filter((face) => face.name).length;
		const tooFarCount = faces.filter((face) => face.small && !face.name).length;
		const unknownCount = faces.length - identifiedCount - tooFarCount;
		const readoutRows: { label: string; value: string; tone?: string }[] = [
			{ label: 'Tracks', value: formatCount(faces.length) },
			{ label: 'Identified', value: formatCount(identifiedCount), tone: identifiedCount ? 'ok' : '' },
			{ label: 'Unknown', value: formatCount(unknownCount), tone: 'warn' },
			{ label: 'Too far', value: formatCount(tooFarCount) },
			{ label: 'Frame rate', value: frameAnalysis ? `${liveConnection.framesPerSecond} fps` : '—' },
			{ label: 'Latency', value: frameAnalysis ? `${liveConnection.roundTripMs} ms` : '—' },
			{ label: 'Sensor', value: frameAnalysis ? `${frameAnalysis.width}×${frameAnalysis.height}` : '—' }
		];
		if (preferences.showDebugInfo && frameAnalysis) {
			readoutRows.push({ label: 'Server', value: `${frameAnalysis.ms.total} ms` });
		}
		return readoutRows;
	});
</script>

<div class="strip">
	<div
		class="voice"
		class:off={voiceTrigger.runningMode === 'off'}
		class:speaking={liveConnection.isSpeaking}
		style:--level={voiceTrigger.microphoneLevel}
	>
		<span class="label">Voice</span>
		<span class="prompt">
			{#if voiceTrigger.runningMode === 'off'}
				Off — press <kbd>Space</kbd> to take a photo
			{:else if liveConnection.isTranscribing}
				Listening…
			{:else}
				Say “{liveConnection.keywords[0]}” to take a photo
			{/if}
		</span>
		{#if voiceTrigger.runningMode !== 'off'}<span class="level" aria-hidden="true"></span>{/if}
	</div>
	{#each readouts as readout (readout.label)}
		<div class="cell">
			<span class="label">{readout.label}</span>
			<span class="value {readout.tone ?? ''}">{readout.value}</span>
		</div>
	{/each}
</div>

<style>
	.strip {
		flex: none;
		display: flex;
		min-height: 58px;
		background: var(--panel);
		border-top: 1px solid var(--border-strong);
		font-family: var(--font-data);
	}
	.voice,
	.cell {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 2px;
		padding: 6px 12px;
		border-right: 1px solid var(--border);
		white-space: nowrap;
	}
	.voice {
		position: relative;
		flex: 1;
		min-width: 0;
	}
	.cell:last-child {
		border-right: 0;
	}
	.label {
		font-size: 0.72em;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--faint);
	}
	.value {
		font-size: 1.05em;
		font-variant-numeric: tabular-nums;
	}
	.value.ok {
		color: var(--accent);
	}
	.value.warn {
		color: var(--warn);
	}
	.prompt {
		overflow: hidden;
		text-overflow: ellipsis;
		font-size: 0.92em;
	}
	.voice.off .prompt {
		color: var(--muted);
	}
	.voice.speaking .prompt {
		color: var(--accent);
	}
	/* the live input level, as a hairline along the bottom of the cell */
	.level {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 2px;
		background: var(--accent);
		transform: scaleX(var(--level, 0));
		transform-origin: left;
	}
	@media (max-width: 1280px) {
		.strip {
			flex-wrap: wrap;
		}
		.voice {
			flex-basis: 100%;
			border-right: 0;
			border-bottom: 1px solid var(--border);
		}
		.cell {
			flex: 1;
		}
	}
	@media (max-width: 760px) {
		.cell {
			flex-basis: 25%;
			padding: 4px 8px;
		}
	}
</style>
