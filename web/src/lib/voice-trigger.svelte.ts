import {
	BrowserSpeechRecognition,
	isBrowserSpeechRecognitionSupported
} from '#lib/browser-speech-recognition.ts';
import { findKeyword, type KeywordMatch } from '#lib/keyword-matching.ts';
import { liveConnection } from '#lib/live-connection.svelte.ts';
import { describeMicrophoneError, listMediaDevices, Microphone } from '#lib/media.ts';
import { preferences, type VoiceMode } from '#lib/preferences.svelte.ts';

const DEFAULT_KEYWORD_SENSITIVITY = 0.75;
const DEFAULT_COOLDOWN_SECONDS = 3;

export class VoiceTrigger {
	readonly isBrowserRecognitionSupported = isBrowserSpeechRecognitionSupported();

	/** The mode the preference resolves to, given what is available right now. */
	wantedMode: VoiceMode = $derived.by(() => {
		if (preferences.voiceMode !== 'auto') return preferences.voiceMode;
		// Wait to hear about Whisper first: browser recognition can send audio to the cloud.
		if (!liveConnection.speechStatus) return 'off';
		if (liveConnection.speechStatus.available) return 'server';
		return this.isBrowserRecognitionSupported ? 'browser' : 'off';
	});
	runningMode: VoiceMode = $state('off');
	error: string | null = $state(null);
	microphoneLevel = $state(0);
	availableMicrophones: MediaDeviceInfo[] = $state([]);

	private microphone?: Microphone;
	private browserRecognition?: BrowserSpeechRecognition;
	private lastBrowserMatchTime = 0;
	private levelMeterAnimationFrame = 0;

	constructor(private onBrowserKeywordMatch: (keywordMatch: KeywordMatch) => void) {}

	async start(mode: VoiceMode, microphoneId: string) {
		this.stop();
		this.error = null;
		try {
			if (mode === 'server') {
				const isStillCurrent = await this.startStreamingToWhisper(microphoneId);
				if (!isStillCurrent) return;
			} else if (mode === 'browser') {
				this.startBrowserRecognition();
			}
			this.runningMode = mode;
		} catch (error) {
			this.error = describeMicrophoneError(error);
		}
	}

	stop() {
		this.browserRecognition?.stop();
		this.browserRecognition = undefined;
		this.microphone?.stop();
		this.microphone = undefined;
		cancelAnimationFrame(this.levelMeterAnimationFrame);
		this.microphoneLevel = 0;
		this.runningMode = 'off';
	}

	private async startStreamingToWhisper(microphoneId: string): Promise<boolean> {
		const microphone = new Microphone((pcmSamples) => liveConnection.sendMicrophoneAudio(pcmSamples));
		this.microphone = microphone;
		await microphone.start(microphoneId || undefined);
		if (microphone !== this.microphone) return false;
		const microphones = await listMediaDevices('audioinput');
		this.availableMicrophones = microphones.filter((device) => device.deviceId !== 'default');
		this.updateMicrophoneLevel();
		return true;
	}

	private startBrowserRecognition() {
		const browserRecognition = new BrowserSpeechRecognition(
			(transcript, isFinal) => this.handleBrowserTranscript(transcript, isFinal),
			(errorMessage) => {
				if (browserRecognition === this.browserRecognition) this.error = `Speech recognition: ${errorMessage}`;
			}
		);
		this.browserRecognition = browserRecognition;
		browserRecognition.start();
	}

	private updateMicrophoneLevel = () => {
		this.microphoneLevel = this.microphone?.level ?? 0;
		this.levelMeterAnimationFrame = requestAnimationFrame(this.updateMicrophoneLevel);
	};

	private handleBrowserTranscript(transcript: string, isFinal: boolean) {
		const settings = liveConnection.settings;
		const keywordMatch = findKeyword(
			transcript,
			liveConnection.keywords,
			settings?.keyword_sensitivity ?? DEFAULT_KEYWORD_SENSITIVITY
		);
		if (isFinal) {
			liveConnection.addTranscript({
				text: transcript,
				keywordMatch,
				utteranceSeconds: 0,
				transcriptionMs: 0,
				source: 'browser'
			});
		}
		const cooldownMs = (settings?.cooldown_s ?? DEFAULT_COOLDOWN_SECONDS) * 1000;
		const isCooledDown = performance.now() - this.lastBrowserMatchTime > cooldownMs;
		if (keywordMatch && isCooledDown) {
			this.lastBrowserMatchTime = performance.now();
			this.onBrowserKeywordMatch(keywordMatch);
		}
	}
}
