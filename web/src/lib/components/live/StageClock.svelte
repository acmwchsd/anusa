<!-- The timestamp shown over the camera feed. -->
<script lang="ts">
	import { onMount } from 'svelte';

	let currentTime = $state(new Date());

	onMount(() => {
		const clockTimer = setInterval(() => (currentTime = new Date()), 1000);
		return () => clearInterval(clockTimer);
	});
</script>

<!-- The Swedish locale formats as 2026-10-30 21:57:09. -->
<time datetime={currentTime.toISOString()}>{currentTime.toLocaleString('sv-SE')}</time>
