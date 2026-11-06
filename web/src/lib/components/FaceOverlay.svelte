<!-- Tracking gates over the live video: corner marks and a small data block on a leader line. -->
<script lang="ts">
	import type { FrameAnalysis } from '#lib/live-connection.svelte.ts';

	// Past these fractions of the frame, a data block moves so it stays on screen.
	const FLIP_LEFT_FROM = 0.84;
	const FLIP_BELOW_UNDER = 0.16;
	const FLIP_ABOVE_FROM = 0.92;
	// From this many faces, or on a feed narrower than this many pixels, blocks shrink to names only.
	const COMPACT_FROM_FACE_COUNT = 8;
	const COMPACT_UNDER_WIDTH = 560;

	interface Props {
		frameAnalysis: FrameAnalysis | null;
		isMirrored: boolean;
		showDebugInfo: boolean;
	}
	let { frameAnalysis, isMirrored, showDebugInfo }: Props = $props();

	let overlayWidth = $state(0);
	const isCompact = $derived(
		(frameAnalysis?.faces.length ?? 0) >= COMPACT_FROM_FACE_COUNT || overlayWidth < COMPACT_UNDER_WIDTH
	);

	/** Every other face from left to right gets a longer leader, so neighboring names never collide. */
	const raisedTrackIds = $derived.by(() => {
		const facesLeftToRight = [...(frameAnalysis?.faces ?? [])].sort(
			(firstFace, secondFace) => firstFace.bbox[0] - secondFace.bbox[0]
		);
		return new Set(facesLeftToRight.filter((_, faceIndex) => faceIndex % 2 === 1).map((face) => face.track));
	});

	const toCssPercent = (fraction: number) => `${(fraction * 100).toFixed(3)}%`;
	const toDisplayPercent = (fraction: number) => `${Math.round(fraction * 100)}%`;
	const formatTrackId = (trackId: number) => `T${String(trackId).padStart(3, '0')}`;
</script>

{#if frameAnalysis}
	<div class="overlay" class:compact={isCompact} bind:clientWidth={overlayWidth} aria-hidden="true">
		{#each frameAnalysis.faces as face (face.track)}
			{@const [boxLeft, boxTop, boxWidth, boxHeight] = face.bbox}
			{@const leftFraction = isMirrored
				? 1 - (boxLeft + boxWidth) / frameAnalysis.width
				: boxLeft / frameAnalysis.width}
			<div
				class="target"
				class:known={!!face.name}
				class:small={face.small}
				class:raised={raisedTrackIds.has(face.track)}
				class:flip={leftFraction > FLIP_LEFT_FROM}
				class:below={boxTop / frameAnalysis.height < FLIP_BELOW_UNDER}
				class:above={(boxTop + boxHeight) / frameAnalysis.height > FLIP_ABOVE_FROM}
				style:left={toCssPercent(leftFraction)}
				style:top={toCssPercent(boxTop / frameAnalysis.height)}
				style:width={toCssPercent(boxWidth / frameAnalysis.width)}
				style:height={toCssPercent(boxHeight / frameAnalysis.height)}
			>
				<span class="gate"></span>
				{#if face.name || !face.small}
					<span class="leader"></span>
					<span class="block">
						<span class="name">{face.name ?? 'Unknown'}</span>
						<span class="meta">
							{formatTrackId(face.track)}
							{#if face.name && face.similarity !== null}
								{toDisplayPercent(face.similarity)}
							{:else if showDebugInfo && face.nearest && face.similarity !== null}
								≈ {face.nearest} {toDisplayPercent(face.similarity)}
							{/if}
						</span>
					</span>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.overlay {
		position: absolute;
		inset: 0;
		pointer-events: none;
		overflow: hidden;
	}
	.target {
		--c: var(--warn);
		--rise: 0px;
		position: absolute;
		transition:
			left 0.09s linear,
			top 0.09s linear,
			width 0.09s linear,
			height 0.09s linear;
	}
	.target.known {
		--c: var(--accent);
	}
	.target.small {
		--c: #fff;
		opacity: 0.55;
	}
	.target.raised {
		--rise: 36px;
	}

	.gate {
		--len: min(24%, 12px);
		position: absolute;
		inset: 0;
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
	}

	/* the diagonal from the gate's corner up to its data block */
	.leader {
		position: absolute;
		left: 100%;
		bottom: 100%;
		width: 12px;
		height: calc(12px + var(--rise));
		background: linear-gradient(
			to top right,
			transparent calc(50% - 0.6px),
			var(--c) calc(50% - 0.6px),
			var(--c) calc(50% + 0.6px),
			transparent calc(50% + 0.6px)
		);
	}
	.flip .leader {
		left: auto;
		right: 100%;
		transform: scaleX(-1);
	}
	.below .leader {
		bottom: auto;
		top: 100%;
		transform: scaleY(-1);
	}
	.flip.below .leader {
		transform: scale(-1);
	}

	.block {
		position: absolute;
		left: calc(100% + 12px);
		bottom: calc(100% + 8px + var(--rise));
		display: flex;
		flex-direction: column;
		padding: 1px 5px;
		background: rgb(0 0 0 / 0.62);
		font-family: var(--font-data);
		font-size: clamp(10px, 0.9vw, 12.5px);
		line-height: 1.25;
		white-space: nowrap;
	}
	.flip .block {
		left: auto;
		right: calc(100% + 12px);
		text-align: right;
	}
	.below .block {
		bottom: auto;
		top: calc(100% + 8px + var(--rise));
	}
	.name {
		font-weight: 700;
		text-transform: uppercase;
		color: var(--c);
	}
	.meta {
		color: #fff;
	}

	/* a whole class in frame, or a small screen: names only, under each chin. The amber
	   gate alone already says "unknown". */
	.compact .leader,
	.compact .meta,
	.compact .target:not(.known) .block {
		display: none;
	}
	.compact .block {
		left: 50%;
		right: auto;
		top: calc(100% + 2px);
		bottom: auto;
		padding: 0 4px;
		transform: translateX(-50%);
		font-size: clamp(9px, 0.8vw, 11px);
	}
	.compact .above .block {
		top: auto;
		bottom: calc(100% + 2px);
	}
</style>
