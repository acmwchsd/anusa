import { api, type Photo, type Settings, type SpeechStatus } from '#lib/api-client.ts';
import type { KeywordMatch } from '#lib/keyword-matching.ts';
import { showErrorToast } from '#lib/toasts.svelte.ts';

export interface LiveFace {
	track: number;
	bbox: [number, number, number, number];
	score: number;
	person_id: string | null;
	name: string | null;
	nearest: string | null;
	similarity: number | null;
	small: boolean;
}

export interface FrameAnalysis {
	frame: number;
	width: number;
	height: number;
	faces: LiveFace[];
	embedded: number;
	ms: { decode: number; detect: number; embed: number; total: number };
}

export interface Transcript {
	id: number;
	text: string;
	keywordMatch: KeywordMatch | null;
	utteranceSeconds: number;
	transcriptionMs: number;
	source: 'server' | 'browser';
}

export interface CaptureRequest {
	source: string;
	keywordMatch: KeywordMatch | null;
	requestId?: string;
}

type ServerMessage =
	| { type: 'hello'; speech: SpeechStatus; settings: Settings }
	| ({ type: 'faces' } & FrameAnalysis)
	| { type: 'error'; frame: number; message: string }
	| { type: 'vad'; speaking: boolean }
	| { type: 'transcribing'; seconds: number }
	| { type: 'transcript'; text: string; seconds: number; elapsed_ms: number; hit: KeywordMatch | null }
	| { type: 'speech_error'; message: string }
	| { type: 'trigger'; source: string; hit: KeywordMatch | null; request_id?: string }
	| { type: 'pong' }
	| { type: 'speech_status'; speech: SpeechStatus }
	| { type: 'settings'; settings: Settings }
	| { type: 'photo'; photo: Photo }
	| { type: 'photo_deleted'; id: string }
	| { type: 'gallery'; version: number };

type LiveEvents = {
	captureRequested: CaptureRequest;
	photoTaken: Photo;
	photoDeleted: string;
	rosterChanged: number;
};

const CAMERA_FRAME_MESSAGE = 1;
const MICROPHONE_AUDIO_MESSAGE = 2;
const CAMERA_FRAME_HEADER_LENGTH = 5;
const FRAME_RESPONSE_TIMEOUT_MS = 2000;
const INITIAL_RECONNECT_DELAY_MS = 500;
const MAXIMUM_RECONNECT_DELAY_MS = 10_000;
const MAXIMUM_TRANSCRIPTS = 8;
const SETTINGS_SAVE_DELAY_MS = 350;
const DEFAULT_KEYWORD = 'techpreneure';

class LiveConnection {
	connectionStatus: 'idle' | 'connecting' | 'open' | 'closed' = $state('idle');
	latestFrameAnalysis: FrameAnalysis | null = $state(null);
	isSpeaking = $state(false);
	isTranscribing = $state(false);
	transcripts: Transcript[] = $state([]);
	speechStatus: SpeechStatus | null = $state(null);
	settings: Settings | null = $state(null);
	framesPerSecond = $state(0);
	roundTripMs = $state(0);
	frameError: string | null = $state(null);
	speechError: string | null = $state(null);

	private socket?: WebSocket;
	private lastFrameId = 0;
	private frameAwaitingResponse: { frameId: number; sentAt: number } | null = null;
	private reconnectAttempts = 0;
	private recentFrameTimes: number[] = [];
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	private listeners = new Map<keyof LiveEvents, Set<(payload: any) => void>>();
	private lastTranscriptId = 0;
	private settingsSaveTimer: ReturnType<typeof setTimeout> | undefined;

	get keywords() {
		return this.settings?.keywords ?? [DEFAULT_KEYWORD];
	}

	connect() {
		if (this.socket && this.socket.readyState <= WebSocket.OPEN) return;
		this.connectionStatus = 'connecting';
		const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
		const socket = new WebSocket(`${protocol}://${location.host}/ws`);
		socket.binaryType = 'arraybuffer';
		socket.onopen = () => {
			this.connectionStatus = 'open';
			this.reconnectAttempts = 0;
			this.frameAwaitingResponse = null;
		};
		socket.onmessage = (event) => this.handleServerMessage(JSON.parse(event.data));
		socket.onclose = () => {
			this.connectionStatus = 'closed';
			this.socket = undefined;
			this.frameAwaitingResponse = null;
			this.isSpeaking = false;
			this.isTranscribing = false;
			const reconnectDelayMs = Math.min(
				MAXIMUM_RECONNECT_DELAY_MS,
				INITIAL_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts++
			);
			setTimeout(() => this.connect(), reconnectDelayMs);
		};
		this.socket = socket;
	}

	on<EventName extends keyof LiveEvents>(
		eventName: EventName,
		listener: (payload: LiveEvents[EventName]) => void
	): () => void {
		if (!this.listeners.has(eventName)) this.listeners.set(eventName, new Set());
		const eventListeners = this.listeners.get(eventName)!;
		eventListeners.add(listener);
		return () => eventListeners.delete(listener);
	}

	private emit<EventName extends keyof LiveEvents>(eventName: EventName, payload: LiveEvents[EventName]) {
		this.listeners.get(eventName)?.forEach((listener) => listener(payload));
	}

	canSendFrame(): boolean {
		if (this.connectionStatus !== 'open') return false;
		const responseTimedOut =
			this.frameAwaitingResponse && performance.now() - this.frameAwaitingResponse.sentAt > FRAME_RESPONSE_TIMEOUT_MS;
		if (responseTimedOut) this.frameAwaitingResponse = null;
		return !this.frameAwaitingResponse;
	}

	sendCameraFrame(jpegBytes: ArrayBuffer) {
		if (!this.socket || !this.canSendFrame()) return;
		const frameId = ++this.lastFrameId >>> 0;
		const message = new Uint8Array(CAMERA_FRAME_HEADER_LENGTH + jpegBytes.byteLength);
		message[0] = CAMERA_FRAME_MESSAGE;
		new DataView(message.buffer).setUint32(1, frameId, true);
		message.set(new Uint8Array(jpegBytes), CAMERA_FRAME_HEADER_LENGTH);
		this.frameAwaitingResponse = { frameId, sentAt: performance.now() };
		this.socket.send(message);
	}

	sendMicrophoneAudio(pcmSamples: Int16Array) {
		if (this.connectionStatus !== 'open' || !this.socket) return;
		const message = new Uint8Array(1 + pcmSamples.byteLength);
		message[0] = MICROPHONE_AUDIO_MESSAGE;
		message.set(new Uint8Array(pcmSamples.buffer, pcmSamples.byteOffset, pcmSamples.byteLength), 1);
		this.socket.send(message);
	}

	addTranscript(transcript: Omit<Transcript, 'id'>) {
		this.transcripts.unshift({ ...transcript, id: ++this.lastTranscriptId });
		this.transcripts.length = Math.min(this.transcripts.length, MAXIMUM_TRANSCRIPTS);
	}

	clearFrameAnalysis() {
		this.latestFrameAnalysis = null;
	}

	updateSettings(settingsChanges: Partial<Settings>) {
		if (!this.settings) return;
		const updatedSettings = { ...this.settings, ...settingsChanges };
		this.settings = updatedSettings;
		clearTimeout(this.settingsSaveTimer);
		this.settingsSaveTimer = setTimeout(
			() => api.saveSettings(updatedSettings).catch((error) => showErrorToast(error, 'Settings not saved')),
			SETTINGS_SAVE_DELAY_MS
		);
	}

	private handleServerMessage(message: ServerMessage) {
		switch (message.type) {
			case 'hello':
				this.speechStatus = message.speech;
				this.settings = message.settings;
				break;
			case 'faces':
				this.handleFrameAnalysis(message);
				break;
			case 'error':
				if (this.frameAwaitingResponse?.frameId === message.frame) this.frameAwaitingResponse = null;
				this.frameError = message.message;
				break;
			case 'vad':
				this.isSpeaking = message.speaking;
				break;
			case 'transcribing':
				this.isTranscribing = true;
				break;
			case 'transcript':
				this.isTranscribing = false;
				this.speechError = null;
				if (message.text) {
					this.addTranscript({
						text: message.text,
						keywordMatch: message.hit,
						utteranceSeconds: message.seconds,
						transcriptionMs: message.elapsed_ms,
						source: 'server'
					});
				}
				break;
			case 'speech_error':
				this.isTranscribing = false;
				this.speechError = message.message;
				break;
			case 'trigger':
				this.emit('captureRequested', {
					source: message.source,
					keywordMatch: message.hit,
					requestId: message.request_id
				});
				break;
			case 'speech_status':
				this.speechStatus = message.speech;
				break;
			case 'settings':
				this.settings = message.settings;
				break;
			case 'photo':
				this.emit('photoTaken', message.photo);
				break;
			case 'photo_deleted':
				this.emit('photoDeleted', message.id);
				break;
			case 'gallery':
				this.emit('rosterChanged', message.version);
				break;
		}
	}

	private handleFrameAnalysis(frameAnalysis: FrameAnalysis) {
		const now = performance.now();
		if (this.frameAwaitingResponse?.frameId === frameAnalysis.frame) {
			this.roundTripMs = Math.round(now - this.frameAwaitingResponse.sentAt);
			this.frameAwaitingResponse = null;
		}
		this.recentFrameTimes.push(now);
		this.recentFrameTimes = this.recentFrameTimes.filter((frameTime) => now - frameTime < 1000);
		this.framesPerSecond = this.recentFrameTimes.length;
		this.latestFrameAnalysis = frameAnalysis;
		this.frameError = null;
	}
}

export const liveConnection = new LiveConnection();
