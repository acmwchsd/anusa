<script lang="ts">
	import type { CameraFeed } from '#lib/camera-feed.svelte.ts';
	import SidePanel from '#lib/components/SidePanel.svelte';
	import { preferences } from '#lib/preferences.svelte.ts';

	let { cameraFeed }: { cameraFeed: CameraFeed } = $props();
</script>

<SidePanel title="Camera & display" collapsible>
	<label class="setting-row">
		<span>Camera</span>
		<select bind:value={preferences.cameraId}>
			<option value="">Default</option>
			{#each cameraFeed.availableCameras as camera (camera.deviceId)}
				<option value={camera.deviceId}>{camera.label || 'Camera'}</option>
			{/each}
		</select>
	</label>
	<label class="setting-row">
		<span>Detail</span>
		<select bind:value={preferences.recognitionFrameWidth}>
			<option value={640}>Fast — faces near the camera</option>
			<option value={960}>Balanced</option>
			<option value={1280}>Detailed — whole classroom</option>
		</select>
	</label>
	<label class="setting-row">
		<span>Countdown</span>
		<select bind:value={preferences.countdownSeconds}>
			<option value={0}>Off</option>
			<option value={3}>3 seconds</option>
			<option value={5}>5 seconds</option>
		</select>
	</label>
	<label class="setting-row check">
		<input type="checkbox" bind:checked={preferences.mirrorPreview} /> Mirror preview
	</label>
	<label class="setting-row check">
		<input type="checkbox" bind:checked={preferences.showDebugInfo} /> Show scores &amp; timings
	</label>
</SidePanel>

<style>
	.check {
		justify-content: flex-start;
	}
</style>
