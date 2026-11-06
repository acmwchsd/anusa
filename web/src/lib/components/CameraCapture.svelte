<script lang="ts">
	import { onDestroy } from 'svelte';
	import {
		captureVideoFrame,
		describeCameraError,
		openCamera,
		playShutterSound,
		playStreamInVideo,
		stopMediaStream
	} from '#lib/media.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import { sleep } from '#lib/timing.ts';

	interface Props {
		onPhotosCaptured: (capturedPhotos: Blob[]) => void | Promise<void>;
		isBusy?: boolean;
	}
	let { onPhotosCaptured, isBusy = false }: Props = $props();

	// Small pose changes make the reference photos robust to how students sit in class.
	const POSE_PROMPTS = ['Look at the camera', 'Turn a little left', 'Turn a little right', 'Chin up a little', 'Big smile!'];
	const FIRST_PHOTO_DELAY_MS = 900;
	const NEXT_PHOTO_DELAY_MS = 1100;
	const CAPTURE_WIDTH = 1280;
	const CAPTURE_JPEG_QUALITY = 0.9;
	const FLASH_DURATION_MS = 120;

	let videoElement: HTMLVideoElement | undefined = $state();
	let cameraStream: MediaStream | null = $state(null);
	let errorMessage: string | null = $state(null);
	let currentPoseIndex = $state(-1);
	let showFlash = $state(false);

	const isCapturing = $derived(currentPoseIndex >= 0);

	$effect(() => {
		let isCancelled = false;
		openCamera(preferences.cameraId || undefined)
			.then((stream) => {
				if (isCancelled) return stopMediaStream(stream);
				cameraStream = stream;
			})
			.catch((error) => (errorMessage = describeCameraError(error)));
		return () => {
			isCancelled = true;
		};
	});

	$effect(() => {
		if (videoElement && cameraStream) playStreamInVideo(videoElement, cameraStream);
	});

	onDestroy(() => stopMediaStream(cameraStream));

	async function captureReferencePhotos() {
		if (!videoElement || isCapturing) return;
		const capturedPhotos: Blob[] = [];
		try {
			for (let poseIndex = 0; poseIndex < POSE_PROMPTS.length; poseIndex++) {
				currentPoseIndex = poseIndex;
				await sleep(poseIndex === 0 ? FIRST_PHOTO_DELAY_MS : NEXT_PHOTO_DELAY_MS);
				capturedPhotos.push(await captureVideoFrame(videoElement, CAPTURE_WIDTH, CAPTURE_JPEG_QUALITY));
				showFlash = true;
				playShutterSound();
				setTimeout(() => (showFlash = false), FLASH_DURATION_MS);
			}
		} catch {
			errorMessage = 'Lost the camera picture partway through. Check the camera and try again.';
			return;
		} finally {
			currentPoseIndex = -1;
		}
		errorMessage = null;
		await onPhotosCaptured(capturedPhotos);
	}
</script>

<div class="capture">
	<div class="frame">
		<!-- svelte-ignore a11y_media_has_caption -->
		<video bind:this={videoElement} class:mirror={preferences.mirrorPreview} autoplay muted playsinline></video>
		<div class="guide" aria-hidden="true"></div>
		{#if isCapturing}
			<div class="prompt">
				<strong>{POSE_PROMPTS[currentPoseIndex]}</strong>
				<span class="pips" aria-label="Photo {currentPoseIndex + 1} of {POSE_PROMPTS.length}">
					{#each POSE_PROMPTS as posePrompt, poseIndex (posePrompt)}
						<i class:done={poseIndex <= currentPoseIndex}></i>
					{/each}
				</span>
			</div>
		{/if}
		{#if showFlash}<div class="flash"></div>{/if}
		{#if errorMessage}<div class="error">{errorMessage}</div>{/if}
	</div>
	<button class="btn primary" onclick={captureReferencePhotos} disabled={!cameraStream || isCapturing || isBusy}>
		{isBusy ? 'Learning…' : isCapturing ? 'Hold still…' : `Capture ${POSE_PROMPTS.length} photos`}
	</button>
</div>

<style>
	.capture {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.frame {
		position: relative;
		aspect-ratio: 4 / 3;
		background: #000;
		border: 1px solid var(--border-strong);
		overflow: hidden;
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
	.guide {
		position: absolute;
		left: 50%;
		top: 46%;
		width: 34%;
		aspect-ratio: 3 / 4;
		transform: translate(-50%, -50%);
		border: 1px solid #fff;
		border-radius: 50%;
		box-shadow: 0 0 0 9999px rgb(0 0 0 / 0.5);
	}
	.prompt {
		position: absolute;
		left: 50%;
		bottom: 10px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 5px;
		padding: 3px 12px 6px;
		transform: translateX(-50%);
		background: rgb(0 0 0 / 0.66);
		font-family: var(--font-data);
		white-space: nowrap;
		text-transform: uppercase;
	}
	.pips {
		display: flex;
		gap: 3px;
	}
	.pips i {
		width: 20px;
		height: 3px;
		background: rgb(255 255 255 / 0.25);
	}
	.pips i.done {
		background: var(--accent);
	}
	.flash {
		position: absolute;
		inset: 0;
		background: rgb(255 255 255 / 0.6);
	}
	.error {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		padding: 20px;
		text-align: center;
		color: var(--danger);
		background: rgb(9 11 10 / 0.86);
	}
</style>
