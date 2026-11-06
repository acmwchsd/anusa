interface SpeechRecognitionEngine extends EventTarget {
	continuous: boolean;
	interimResults: boolean;
	lang: string;
	start(): void;
	stop(): void;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	onresult: ((event: any) => void) | null;
	onend: (() => void) | null;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	onerror: ((event: any) => void) | null;
}

const RESTART_DELAY_MS = 250;
const IGNORED_ERRORS = ['no-speech', 'aborted'];

function speechRecognitionConstructor(): (new () => SpeechRecognitionEngine) | undefined {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const browserWindow = window as any;
	return browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
}

export const isBrowserSpeechRecognitionSupported = () =>
	typeof window !== 'undefined' && !!speechRecognitionConstructor();

export class BrowserSpeechRecognition {
	private recognitionEngine?: SpeechRecognitionEngine;
	private isRunning = false;

	constructor(
		private onTranscript: (transcript: string, isFinal: boolean) => void,
		private onError: (errorMessage: string) => void
	) {}

	start(language = 'en-US') {
		const SpeechRecognition = speechRecognitionConstructor();
		if (!SpeechRecognition) {
			throw new Error('This browser has no built-in speech recognition (try Chrome, Edge or Safari).');
		}
		this.isRunning = true;
		const recognitionEngine = new SpeechRecognition();
		recognitionEngine.continuous = true;
		recognitionEngine.interimResults = true;
		recognitionEngine.lang = language;
		recognitionEngine.onresult = (event) => {
			for (let resultIndex = event.resultIndex; resultIndex < event.results.length; resultIndex++) {
				const result = event.results[resultIndex];
				this.onTranscript(result[0].transcript, result.isFinal);
			}
		};
		recognitionEngine.onerror = (event) => {
			if (!IGNORED_ERRORS.includes(event.error)) this.onError(event.error);
		};
		// Recognition stops by itself after silence or about a minute, so restart it while running.
		recognitionEngine.onend = () => {
			if (this.isRunning) setTimeout(() => this.isRunning && recognitionEngine.start(), RESTART_DELAY_MS);
		};
		recognitionEngine.start();
		this.recognitionEngine = recognitionEngine;
	}

	stop() {
		this.isRunning = false;
		this.recognitionEngine?.stop();
		this.recognitionEngine = undefined;
	}
}
