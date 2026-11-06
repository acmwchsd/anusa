<!-- A sector scope of who is in view, with the camera at the apex. A face's position across the frame
     gives its bearing and its size gives its range. Identified faces are squares, unknown ones circles. -->
<script lang="ts">
	import type { FrameAnalysis, LiveFace } from '#lib/live-connection.svelte.ts';

	const SCOPE_RADIUS = 100;
	/** Half the angle of the camera's view shown on the scope, in degrees. */
	const HALF_VIEW_ANGLE_DEGREES = 55;
	/** Face width as a fraction of the frame that reads as "right here"... */
	const NEAREST_FACE_WIDTH_FRACTION = 0.35;
	/** ...and as "at the back of the room". */
	const FARTHEST_FACE_WIDTH_FRACTION = 0.015;

	interface Props {
		frameAnalysis: FrameAnalysis | null;
		isMirrored: boolean;
	}
	let { frameAnalysis, isMirrored }: Props = $props();

	function polarToCartesian(angleDegrees: number, range: number) {
		const angleRadians = (angleDegrees * Math.PI) / 180;
		return { x: Math.sin(angleRadians) * range, y: -Math.cos(angleRadians) * range };
	}

	function arcPath(range: number) {
		const arcStart = polarToCartesian(-HALF_VIEW_ANGLE_DEGREES, range);
		const arcEnd = polarToCartesian(HALF_VIEW_ANGLE_DEGREES, range);
		return `M${arcStart.x} ${arcStart.y}A${range} ${range} 0 0 1 ${arcEnd.x} ${arcEnd.y}`;
	}

	function spokePath(angleDegrees: number) {
		const spokeEnd = polarToCartesian(angleDegrees, SCOPE_RADIUS);
		return `M0 0L${spokeEnd.x} ${spokeEnd.y}`;
	}

	const GRID_PATH = [
		arcPath(SCOPE_RADIUS),
		arcPath(SCOPE_RADIUS * (2 / 3)),
		arcPath(SCOPE_RADIUS / 3),
		...[-1, -0.5, 0, 0.5, 1].map((angleFraction) => spokePath(angleFraction * HALF_VIEW_ANGLE_DEGREES))
	].join('');

	function scopePosition(face: LiveFace, frameWidth: number) {
		const [boxLeft, , boxWidth] = face.bbox;
		// -1 at the left edge of the frame, 1 at the right edge.
		const horizontalPosition = ((boxLeft + boxWidth / 2) / frameWidth) * 2 - 1;
		const nearness =
			Math.log(boxWidth / frameWidth / FARTHEST_FACE_WIDTH_FRACTION) /
			Math.log(NEAREST_FACE_WIDTH_FRACTION / FARTHEST_FACE_WIDTH_FRACTION);
		const range = SCOPE_RADIUS * (0.96 - 0.82 * Math.min(1, Math.max(0, nearness)));
		const bearing = (isMirrored ? -horizontalPosition : horizontalPosition) * HALF_VIEW_ANGLE_DEGREES;
		return polarToCartesian(bearing, range);
	}

	const faceMarks = $derived(
		(frameAnalysis?.faces ?? []).map((face) => ({
			...scopePosition(face, frameAnalysis!.width),
			trackId: face.track,
			isIdentified: !!face.name,
			isFar: face.small
		}))
	);
</script>

<svg class="scope" viewBox="-88 -112 176 122" role="img" aria-label="{faceMarks.length} in view">
	<path class="grid" d={GRID_PATH} />
	<text x="0" y="-104">Far</text>
	<text x="0" y="9">Camera</text>
	{#each faceMarks as faceMark (faceMark.trackId)}
		<g
			class="mark"
			class:known={faceMark.isIdentified}
			class:far={faceMark.isFar && !faceMark.isIdentified}
			style:transform="translate({faceMark.x}px, {faceMark.y}px)"
		>
			{#if faceMark.isIdentified}<rect x="-3" y="-3" width="6" height="6" />{:else}<circle r="3" />{/if}
		</g>
	{/each}
</svg>

<style>
	.scope {
		display: block;
		width: 100%;
		max-width: 300px;
		margin: 0 auto;
	}
	.grid {
		fill: none;
		stroke: var(--border-strong);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	text {
		font-family: var(--font-data);
		font-size: 6.5px;
		letter-spacing: 0.06em;
		text-anchor: middle;
		text-transform: uppercase;
		fill: var(--faint);
	}
	.mark {
		fill: none;
		stroke: var(--warn);
		stroke-width: 1.25;
		vector-effect: non-scaling-stroke;
		transition: transform 0.12s linear;
	}
	.mark.known {
		fill: var(--accent);
		stroke: none;
	}
	.mark.far {
		stroke: var(--faint);
	}
</style>
