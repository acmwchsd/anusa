<!-- How the voice trigger listens, which phrases it accepts, and what it heard. -->
<script lang="ts">
	import SidePanel from '#lib/components/SidePanel.svelte';
	import { liveConnection } from '#lib/live-connection.svelte.ts';
	import { preferences } from '#lib/preferences.svelte.ts';
	import { showToast } from '#lib/toasts.svelte.ts';
	import type { VoiceTrigger } from '#lib/voice-trigger.svelte.ts';

	const VOICE_MODE_OPTIONS = [
		{ value: 'auto', label: 'Auto' },
		{ value: 'server', label: 'Whisper' },
		{ value: 'browser', label: 'Browser' },
		{ value: 'off', label: 'Off' }
	] as const;
	const RUNNING_MODE_LABELS = { server: 'Whisper', browser: 'Browser', off: 'Off' };
	const VISIBLE_TRANSCRIPT_COUNT = 5;

	let { voiceTrigger }: { voiceTrigger: VoiceTrigger } = $props();

	let newKeywordInput = $state('');
	const keywords = $derived(liveConnection.keywords);
	const isWhisperAvailable = $derived(!!liveConnection.speechStatus?.available);

	/** Why a voice mode cannot be picked right now, or undefined when it can. */
	function reasonModeIsUnavailable(mode: (typeof VOICE_MODE_OPTIONS)[number]['value']) {
		if (mode === 'server' && !isWhisperAvailable) return 'Whisper is not running';
		if (mode === 'browser' && !voiceTrigger.isBrowserRecognitionSupported) {
			return 'This browser has no speech recognition';
		}
	}

	function addKeyword(phrase: string) {
		const trimmedPhrase = phrase.trim();
		const isAlreadyAKeyword = keywords.some((keyword) => keyword.toLowerCase() === trimmedPhrase.toLowerCase());
		if (!trimmedPhrase || isAlreadyAKeyword) return;
		liveConnection.updateSettings({ keywords: [...keywords, trimmedPhrase] });
		showToast({ kind: 'info', title: `“${trimmedPhrase}” now takes a photo too` });
	}

	function removeKeyword(keywordToRemove: string) {
		if (keywords.length > 1) {
			liveConnection.updateSettings({ keywords: keywords.filter((keyword) => keyword !== keywordToRemove) });
		}
	}

	function submitNewKeyword(event: SubmitEvent) {
		event.preventDefault();
		addKeyword(newKeywordInput);
		newKeywordInput = '';
	}

	const withoutTrailingPunctuation = (text: string) => text.replace(/[.!?,]+$/, '');
</script>

<SidePanel title="Voice trigger">
	{#snippet aside()}
		<span class="chip" class:accent={voiceTrigger.runningMode !== 'off'}>
			{RUNNING_MODE_LABELS[voiceTrigger.runningMode]}
		</span>
	{/snippet}

	<div class="segmented" role="radiogroup" aria-label="Voice recognition">
		{#each VOICE_MODE_OPTIONS as { value, label } (value)}
			{@const unavailableReason = reasonModeIsUnavailable(value)}
			<button
				role="radio"
				aria-checked={preferences.voiceMode === value}
				class:active={preferences.voiceMode === value}
				disabled={!!unavailableReason}
				title={unavailableReason}
				onclick={() => (preferences.voiceMode = value)}>{label}</button
			>
		{/each}
	</div>

	<p class="muted small">
		{#if voiceTrigger.runningMode === 'server'}
			Whisper is listening on this machine, so your audio stays out of the cloud.
		{:else if voiceTrigger.runningMode === 'browser'}
			Using the browser's speech recognition{#if !isWhisperAvailable}&nbsp;because Whisper is not running{/if}. In
			Chrome this audio goes to Google.
		{:else if !isWhisperAvailable && !voiceTrigger.isBrowserRecognitionSupported}
			No speech recognition available: start the server with Whisper, or use Chrome or Safari.
		{:else}
			Voice trigger is off.
		{/if}
	</p>

	{#if voiceTrigger.wantedMode === 'server'}
		<label class="setting-row">
			<span>Microphone</span>
			<select bind:value={preferences.microphoneId}>
				<option value="">Default</option>
				{#each voiceTrigger.availableMicrophones as microphone (microphone.deviceId)}
					<option value={microphone.deviceId}>{microphone.label || 'Microphone'}</option>
				{/each}
			</select>
		</label>
	{/if}

	{#if voiceTrigger.error}
		<p class="error small">
			{voiceTrigger.error}
			<button class="btn small" onclick={() => voiceTrigger.start(voiceTrigger.wantedMode, preferences.microphoneId)}
				>Retry</button
			>
		</p>
	{/if}
	{#if liveConnection.speechError}
		<p class="error small" title={liveConnection.speechError}>
			Whisper failed on the last phrase. Try saying it again.
		</p>
	{/if}

	<div class="keywords">
		{#each keywords as keyword (keyword)}
			<span class="chip accent">
				{keyword}
				{#if keywords.length > 1}
					<button class="x" aria-label="Remove {keyword}" onclick={() => removeKeyword(keyword)}>×</button>
				{/if}
			</span>
		{/each}
		<form onsubmit={submitNewKeyword}>
			<input type="text" placeholder="Add phrase…" bind:value={newKeywordInput} aria-label="Add trigger phrase" />
		</form>
	</div>

	{#if liveConnection.transcripts.length}
		<ul class="transcripts">
			{#each liveConnection.transcripts.slice(0, VISIBLE_TRANSCRIPT_COUNT) as transcript (transcript.id)}
				<li class:hit={!!transcript.keywordMatch}>
					<span class="text">“{transcript.text}”</span>
					{#if transcript.keywordMatch}
						<span class="chip accent" title="matched by {transcript.keywordMatch.by}">
							{transcript.keywordMatch.heard}
						</span>
					{:else}
						<button
							class="btn small ghost"
							title="Make this phrase take a photo"
							onclick={() => addKeyword(withoutTrailingPunctuation(transcript.text))}>+ trigger</button
						>
					{/if}
				</li>
			{/each}
		</ul>
		<p class="faint small">Not triggering? Say the word, then tap <strong>+ trigger</strong> on what was heard.</p>
	{/if}
</SidePanel>

<style>
	p {
		margin: 8px 0;
	}
	.segmented {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 1px;
		background: var(--border-strong);
		border: 1px solid var(--border-strong);
	}
	.segmented button {
		padding: 4px 0;
		border: 0;
		background: var(--panel);
		color: var(--muted);
		font-family: var(--font-data);
		font-size: 0.76em;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		cursor: pointer;
	}
	.segmented button:hover:enabled {
		color: var(--text);
	}
	.segmented button.active {
		background: var(--panel-3);
		color: var(--accent);
	}
	.segmented button:disabled {
		color: var(--faint);
		opacity: 0.6;
		cursor: not-allowed;
	}
	.error {
		color: var(--danger);
	}
	.keywords {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
	}
	.keywords form {
		flex: 1;
		min-width: 110px;
	}
	.keywords input {
		width: 100%;
		padding: 0.15em 0.5em;
		font-size: 0.86em;
	}
	.x {
		border: 0;
		background: none;
		color: inherit;
		cursor: pointer;
		padding: 0 0 0 2px;
		font-size: 1.1em;
		line-height: 1;
	}
	.transcripts {
		list-style: none;
		margin: 10px 0 6px;
		padding: 0;
		display: flex;
		flex-direction: column;
		font-family: var(--font-data);
		font-size: 0.82em;
		border-top: 1px solid var(--border);
	}
	.transcripts li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		min-height: 24px;
		color: var(--muted);
		border-bottom: 1px solid var(--border);
	}
	.transcripts li.hit {
		color: var(--text);
	}
	.text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
