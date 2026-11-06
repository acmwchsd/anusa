<!-- The camera feed. Everything here is a layer over the video, and photos are captured from the
     video itself, so none of it ever ends up in a picture. -->
<script lang="ts">
	import { fade } from 'svelte/transition';
	import type { CameraFeed } from '#lib/camera-feed.svelte.ts';
	import FaceOverlay from '#lib/components/FaceOverlay.svelte';
	import StageClock from '#lib/components/live/StageClock.svelte';
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { playStreamInVideo } from '#lib/media.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import { resolve } from '$app/paths';

	interface Props {
		cameraFeed: CameraFeed;
		/** Seconds left before the photo, 0 when no countdown is running. */
		countdownSecondsLeft: number;
		showFlash: boolean;
		/** The photo just taken, shown in the corner for a moment. */
		lastPhotoUrl: string | null;
	}
	let { cameraFeed, countdownSecondsLeft, showFlash, lastPhotoUrl }: Props = $props();

	const latestTranscript = $derived(liveConnection.transcripts[0]);
	let isAutoplayBlocked = $state(false);

	$effect(() => {
		if (cameraFeed.videoElement && cameraFeed.stream) {
			playStreamInVideo(cameraFeed.videoElement, cameraFeed.stream, () => (isAutoplayBlocked = true));
		}
	});
</script>

<div class="stage-area">
	<div class="stage" style:--ar={cameraFeed.videoSize.width / cameraFeed.videoSize.height}>
		<!-- svelte-ignore a11y_media_has_caption -->
		<video
			bind:this={cameraFeed.videoElement}
			class:mirror={preferences.mirrorPreview}
			autoplay
			muted
			playsinline
			onloadedmetadata={() => cameraFeed.updateVideoSize()}
			onresize={() => cameraFeed.updateVideoSize()}
			onplaying={() => (isAutoplayBlocked = false)}
		></video>

		<FaceOverlay
			frameAnalysis={cameraFeed.stream ? liveConnection.latestFrameAnalysis : null}
			isMirrored={preferences.mirrorPreview}
			showDebugInfo={preferences.showDebugInfo}
		/>

		{#if cameraFeed.error}
			<div class="stage-message">
				<p>{cameraFeed.error}</p>
				<button class="btn primary" onclick={() => cameraFeed.start(preferences.cameraId)}>Retry</button>
			</div>
		{:else if !cameraFeed.stream}
			<div class="stage-message"><p class="muted">Starting camera…</p></div>
		{:else if isAutoplayBlocked}
			<div class="stage-message"><p>Click anywhere to start the video.</p></div>
		{/if}

		<div class="burn-in top-left"><span class="rec"></span>Live</div>
		<div class="burn-in top-right"><StageClock /></div>

		{#if liveConnection.connectionStatus !== 'open'}
			<span class="alert chip warn">Reconnecting to the server…</span>
		{:else if liveConnection.frameError}
			<span class="alert chip warn" title={liveConnection.frameError}>
				Face recognition hit a problem, still trying…
			</span>
		{/if}

		{#key latestTranscript?.id}
			{#if latestTranscript}
				<div class="heard" class:hit={!!latestTranscript.keywordMatch} in:fade={{ duration: 100 }}>
					“{latestTranscript.text}”
				</div>
			{/if}
		{/key}

		{#if countdownSecondsLeft > 0}
			<div class="countdown">
				<span class="count">{countdownSecondsLeft}</span>
				<span class="hold">Hold still</span>
			</div>
		{/if}
		{#if showFlash}<div class="flash" out:fade={{ duration: 220 }}></div>{/if}
		{#if lastPhotoUrl}
			<a class="last-shot" href={resolve('/photos')}>
				<img src={lastPhotoUrl} alt="Just taken" />
				<span>Saved</span>
			</a>
		{/if}
	</div>
</div>

<style>
	.stage-area {
		flex: 1;
		min-height: 0;
		display: grid;
		place-items: center;
		background: #000;
	}
	.stage {
		--strip-h: 58px;
		position: relative;
		aspect-ratio: var(--ar);
		width: min(100%, calc((100dvh - var(--header-h) - var(--strip-h)) * var(--ar)));
		overflow: hidden;
		background: #000;
	}
	video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	video.mirror {
		transform: scaleX(-1);
	}

	.stage-message {
		position: absolute;
		inset: 0;
		z-index: 1; /* above everything else: on a phone the stage is short */
		display: grid;
		place-content: center;
		justify-items: center;
		gap: 12px;
		padding: 24px;
		text-align: center;
		background: rgb(9 11 10 / 0.86);
	}
	.stage-message p {
		margin: 0;
		max-width: 46ch;
	}

	.burn-in {
		position: absolute;
		top: 10px;
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 0 5px;
		background: rgb(0 0 0 / 0.5);
		font-family: var(--font-data);
		font-size: 0.8em;
		text-transform: uppercase;
		color: #fff;
	}
	.top-left {
		left: 10px;
	}
	.top-right {
		right: 10px;
	}
	.rec {
		width: 7px;
		height: 7px;
		background: var(--live);
	}
	.alert {
		position: absolute;
		top: 36px;
		left: 10px;
	}
	.heard {
		position: absolute;
		left: 50%;
		bottom: 12px;
		max-width: 80%;
		padding: 1px 8px;
		transform: translateX(-50%);
		background: rgb(0 0 0 / 0.66);
		font-family: var(--font-data);
		font-size: 0.86em;
		color: #fff;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.heard.hit {
		color: var(--accent);
	}

	.countdown {
		position: absolute;
		left: 50%;
		top: 50%;
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 6px 28px 8px;
		transform: translate(-50%, -50%);
		background: rgb(0 0 0 / 0.62);
		font-family: var(--font-data);
		pointer-events: none;
	}
	.count {
		font-size: min(20vh, 110px);
		line-height: 1.05;
		color: #fff;
	}
	.hold {
		font-size: 0.8em;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--warn);
	}

	.flash {
		position: absolute;
		inset: 0;
		background: #fff;
		opacity: 0.7;
		pointer-events: none;
	}
	.last-shot {
		position: absolute;
		right: 10px;
		bottom: 10px;
		width: 18%;
		min-width: 100px;
		border: 1px solid #fff;
		background: #000;
		text-decoration: none;
	}
	.last-shot img {
		display: block;
		width: 100%;
	}
	.last-shot span {
		display: block;
		padding: 0 5px;
		font-family: var(--font-data);
		font-size: 0.72em;
		text-transform: uppercase;
		color: var(--accent);
	}
	@media (max-width: 1000px) {
		.stage {
			width: 100%;
		}
	}
</style>
