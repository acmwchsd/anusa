export type VoiceMode = 'server' | 'browser' | 'off';
export type RecognitionFrameWidth = 640 | 960 | 1280;

interface Preferences {
	cameraId: string;
	microphoneId: string;
	recognitionFrameWidth: RecognitionFrameWidth;
	countdownSeconds: number;
	mirrorPreview: boolean;
	voiceMode: VoiceMode | 'auto';
	showDebugInfo: boolean;
}

const STORAGE_KEY = 'techpreneure-cam:preferences';
const DEFAULT_PREFERENCES: Preferences = {
	cameraId: '',
	microphoneId: '',
	recognitionFrameWidth: 960,
	countdownSeconds: 0,
	mirrorPreview: true,
	voiceMode: 'auto',
	showDebugInfo: false
};

function loadPreferences(): Preferences {
	try {
		return { ...DEFAULT_PREFERENCES, ...JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') };
	} catch {
		return { ...DEFAULT_PREFERENCES };
	}
}

export const preferences: Preferences = $state(loadPreferences());

$effect.root(() => {
	$effect(() => {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
		} catch {
			// Storage is unavailable (private mode), so preferences just won't persist.
		}
	});
});
