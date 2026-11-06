<!-- Live: the camera, who is in frame, and taking the photo. -->
<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { api, type Person, type Photo, type PhotoTrigger } from '#lib/api-client.ts';
	import { CameraFeed } from '#lib/camera-feed.svelte.ts';
	import CameraPanel from '#lib/components/live/CameraPanel.svelte';
	import InFramePanel from '#lib/components/live/InFramePanel.svelte';
	import LiveStage from '#lib/components/live/LiveStage.svelte';
	import RecentPhotos from '#lib/components/live/RecentPhotos.svelte';
	import RecognitionPanel from '#lib/components/live/RecognitionPanel.svelte';
	import ShutterCard from '#lib/components/live/ShutterCard.svelte';
	import TelemetryStrip from '#lib/components/live/TelemetryStrip.svelte';
	import VoicePanel from '#lib/components/live/VoicePanel.svelte';
	import { pluralize } from '#lib/formatting.ts';
	import { liveConnection, type CaptureRequest } from '#lib/live-connection.svelte.ts';
	import { playBeep, playShutterSound } from '#lib/media.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import { sleep } from '#lib/timing.ts';
	import { showErrorToast, showToast } from '#lib/toasts.svelte.ts';
	import { VoiceTrigger } from '#lib/voice-trigger.svelte.ts';

	const RECENT_PHOTO_COUNT = 6;
	const RECOGNITION_FRAME_JPEG_QUALITY = 0.75;
	const PHOTO_JPEG_QUALITY = 0.92;
	const FLASH_DURATION_MS = 200;
	const LAST_PHOTO_PREVIEW_MS = 4000;

	const cameraFeed = new CameraFeed();
	const voiceTrigger = new VoiceTrigger((keywordMatch) => takePhoto('browser-voice', keywordMatch.heard));

	let people: Person[] = $state([]);
	let recentPhotos: Photo[] = $state([]);
	let isTakingPhoto = $state(false);
	let countdownSecondsLeft = $state(0);
	let showFlash = $state(false);
	let lastPhotoUrl: string | null = $state(null);
	/** The server's capture request that the photo being taken answers, if any. */
	let pendingCaptureRequestId: string | undefined;
	let isStreamingFrames = true;

	$effect(() => {
		cameraFeed.start(preferences.cameraId);
	});

	$effect(() => {
		voiceTrigger.start(voiceTrigger.wantedMode, preferences.microphoneId);
	});

	/** Sends downscaled camera frames to the server for recognition, as fast as it answers. */
	async function streamFramesForRecognition() {
		while (isStreamingFrames) {
			if (cameraFeed.isReady && liveConnection.canSendFrame()) {
				try {
					const frame = await cameraFeed.captureFrame(
						preferences.recognitionFrameWidth,
						RECOGNITION_FRAME_JPEG_QUALITY
					);
					liveConnection.sendCameraFrame(await frame.arrayBuffer());
				} catch {
					// A frame can fail while the camera switches; the next one is tried.
				}
			}
			await new Promise((resolveNextAnimationFrame) => requestAnimationFrame(resolveNextAnimationFrame));
		}
	}

	async function takePhoto(trigger: PhotoTrigger, heardText?: string, captureRequestId?: string) {
		if (isTakingPhoto) {
			// A photo is already on its way, and it answers this request too.
			pendingCaptureRequestId ??= captureRequestId;
			return;
		}
		if (!cameraFeed.isReady) return;
		isTakingPhoto = true;
		pendingCaptureRequestId = captureRequestId;
		try {
			for (let secondsLeft = preferences.countdownSeconds; secondsLeft > 0; secondsLeft--) {
				countdownSecondsLeft = secondsLeft;
				playBeep();
				await sleep(1000);
			}
			countdownSecondsLeft = 0;
			const photoBlob = await cameraFeed.captureFrame(undefined, PHOTO_JPEG_QUALITY);
			showFlash = true;
			playShutterSound();
			setTimeout(() => (showFlash = false), FLASH_DURATION_MS);
			const savedPhoto = await api.uploadPhoto(photoBlob, trigger, heardText, pendingCaptureRequestId);
			lastPhotoUrl = savedPhoto.url;
			setTimeout(() => (lastPhotoUrl = null), LAST_PHOTO_PREVIEW_MS);
			announcePhoto(savedPhoto, trigger, heardText);
		} catch (error) {
			showErrorToast(error, 'Could not take the photo');
		} finally {
			countdownSecondsLeft = 0;
			isTakingPhoto = false;
			pendingCaptureRequestId = undefined;
		}
	}

	function handleCaptureRequest(captureRequest: CaptureRequest) {
		const trigger = captureRequest.source === 'api' ? 'api' : 'voice';
		takePhoto(trigger, captureRequest.keywordMatch?.heard, captureRequest.requestId);
	}

	function announcePhoto(photo: Photo, trigger: PhotoTrigger, heardText?: string) {
		const nobodyRecognized = photo.faces.length
			? `${pluralize(photo.faces.length, 'face')}, no one recognised yet`
			: 'No faces in this one';
		const spokenPhrase = heardText ?? liveConnection.keywords[0];
		showToast({
			kind: 'success',
			title: trigger.includes('voice') ? `“${spokenPhrase}” — photo taken` : 'Photo taken',
			detail: photo.people.join(', ') || nobodyRecognized,
			imageUrl: photo.url
		});
	}

	function handleKeyDown(event: KeyboardEvent) {
		const target = event.target as HTMLElement;
		const isTypingInAControl = target.closest('input, textarea, select, button, [contenteditable]');
		if (event.code !== 'Space' || event.repeat || isTypingInAControl) return;
		event.preventDefault();
		takePhoto('key');
	}

	function addRecentPhoto(newPhoto: Photo) {
		const otherPhotos = recentPhotos.filter((photo) => photo.id !== newPhoto.id);
		recentPhotos = [newPhoto, ...otherPhotos].slice(0, RECENT_PHOTO_COUNT);
	}

	function removeRecentPhoto(photoId: string) {
		recentPhotos = recentPhotos.filter((photo) => photo.id !== photoId);
	}

	const refreshPeople = () =>
		api
			.listPeople()
			.then((loadedPeople) => (people = loadedPeople))
			.catch(() => {});

	onMount(() => {
		streamFramesForRecognition();
		refreshPeople();
		api
			.listPhotos()
			.then((photos) => (recentPhotos = photos.slice(0, RECENT_PHOTO_COUNT)))
			.catch(() => {});
		const unsubscribeAll = [
			liveConnection.on('captureRequested', handleCaptureRequest),
			liveConnection.on('photoTaken', addRecentPhoto),
			liveConnection.on('photoDeleted', removeRecentPhoto),
			liveConnection.on('rosterChanged', refreshPeople)
		];
		return () => unsubscribeAll.forEach((unsubscribe) => unsubscribe());
	});

	onDestroy(() => {
		isStreamingFrames = false;
		voiceTrigger.stop();
		cameraFeed.stop();
		liveConnection.clearFrameAnalysis();
	});
</script>

<svelte:head><title>Live · Techpreneure Cam</title></svelte:head>
<svelte:window onkeydown={handleKeyDown} />

<div class="workstation">
	<div class="feed">
		<LiveStage {cameraFeed} {countdownSecondsLeft} {showFlash} {lastPhotoUrl} />
		<TelemetryStrip {voiceTrigger} />
	</div>

	<aside>
		<ShutterCard disabled={!cameraFeed.stream || isTakingPhoto} onTakePhoto={() => takePhoto('button')} />
		<InFramePanel {people} />
		<VoicePanel {voiceTrigger} />
		<CameraPanel {cameraFeed} />
		<RecognitionPanel />
		{#if recentPhotos.length}
			<RecentPhotos photos={recentPhotos} />
		{/if}
	</aside>
</div>

<style>
	/* one fixed screen, like a workstation: the rail scrolls, the page does not */
	.workstation {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 340px;
		height: calc(100dvh - var(--header-h));
	}
	.feed {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
	}
	aside {
		overflow-y: auto;
		background: var(--panel);
		border-left: 1px solid var(--border-strong);
	}
	@media (max-width: 1000px) {
		.workstation {
			grid-template-columns: 1fr;
			height: auto;
		}
		aside {
			overflow: visible;
			border-left: 0;
		}
	}
</style>
