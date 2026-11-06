// Camera, microphone, image and sound helpers.

import { errorMessage } from '#lib/formatting.ts';

const IDEAL_CAMERA_WIDTH = 1920;
const IDEAL_CAMERA_HEIGHT = 1080;
const IDEAL_CAMERA_FRAME_RATE = 30;
const DEFAULT_UPLOAD_MAXIMUM_SIDE = 1600;
const UPLOAD_JPEG_QUALITY = 0.9;
const MICROPHONE_LEVEL_GAIN = 6;
const MICROPHONE_LEVEL_DECAY = 0.7;

const failedWith = (error: unknown, errorName: string) => error instanceof DOMException && error.name === errorName;

export function describeCameraError(error: unknown): string {
	if (failedWith(error, 'NotAllowedError'))
		return 'Camera access was blocked. Allow the camera for this site in the address bar, then retry.';
	if (failedWith(error, 'NotFoundError')) return 'No camera found. Plug one in and retry.';
	if (failedWith(error, 'NotReadableError')) return 'Another app is using the camera. Close it, then retry.';
	if (failedWith(error, 'OverconstrainedError'))
		return 'The chosen camera is not connected. Plug it back in, or pick another under Camera & display.';
	return `Could not open the camera: ${errorMessage(error)}`;
}

export function describeMicrophoneError(error: unknown): string {
	if (failedWith(error, 'NotAllowedError'))
		return 'Microphone access was blocked. Allow it in the address bar to use the voice trigger.';
	if (failedWith(error, 'NotFoundError')) return 'No microphone found. Plug one in and retry.';
	if (failedWith(error, 'OverconstrainedError')) return 'The chosen microphone is not connected. Pick another above.';
	return `Voice trigger unavailable: ${errorMessage(error)}`;
}

export async function openCamera(cameraId?: string): Promise<MediaStream> {
	return navigator.mediaDevices.getUserMedia({
		audio: false,
		video: {
			deviceId: cameraId ? { exact: cameraId } : undefined,
			// Photos are taken from this stream, so ask for the best the camera offers.
			width: { ideal: IDEAL_CAMERA_WIDTH },
			height: { ideal: IDEAL_CAMERA_HEIGHT },
			frameRate: { ideal: IDEAL_CAMERA_FRAME_RATE }
		}
	});
}

export async function listMediaDevices(deviceKind: MediaDeviceKind) {
	const allDevices = await navigator.mediaDevices.enumerateDevices();
	return allDevices.filter((device) => device.kind === deviceKind && device.deviceId);
}

export function stopMediaStream(stream: MediaStream | null | undefined) {
	stream?.getTracks().forEach((track) => track.stop());
}

export function playStreamInVideo(videoElement: HTMLVideoElement, stream: MediaStream, onAutoplayBlocked?: () => void) {
	videoElement.srcObject = stream;
	videoElement.play().catch((error) => {
		if (error.name !== 'NotAllowedError') return;
		onAutoplayBlocked?.();
		const retryPlayback = () => videoElement.play().catch(() => {});
		addEventListener('click', retryPlayback, { once: true });
		addEventListener('keydown', retryPlayback, { once: true });
	});
}

export async function captureVideoFrame(
	videoElement: HTMLVideoElement,
	maximumWidth?: number,
	jpegQuality = 0.8
): Promise<Blob> {
	const scaleFactor = maximumWidth ? Math.min(1, maximumWidth / videoElement.videoWidth) : 1;
	const frameWidth = Math.round(videoElement.videoWidth * scaleFactor);
	const frameHeight = Math.round(videoElement.videoHeight * scaleFactor);
	const canvas = new OffscreenCanvas(frameWidth, frameHeight);
	canvas.getContext('2d')!.drawImage(videoElement, 0, 0, frameWidth, frameHeight);
	return canvas.convertToBlob({ type: 'image/jpeg', quality: jpegQuality });
}

export async function normalizeUploadedImage(file: File, maximumSide = DEFAULT_UPLOAD_MAXIMUM_SIDE): Promise<Blob> {
	try {
		const bitmap = await createImageBitmap(file);
		const scaleFactor = Math.min(1, maximumSide / Math.max(bitmap.width, bitmap.height));
		const canvas = new OffscreenCanvas(Math.round(bitmap.width * scaleFactor), Math.round(bitmap.height * scaleFactor));
		canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
		bitmap.close();
		const jpegBlob = await canvas.convertToBlob({ type: 'image/jpeg', quality: UPLOAD_JPEG_QUALITY });
		return new File([jpegBlob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' });
	} catch {
		return file;
	}
}

export class Microphone {
	private audioContext?: AudioContext;
	private stream?: MediaStream;
	private workletNode?: AudioWorkletNode;
	private isStopped = false;
	level = 0;

	constructor(private onAudioChunk: (pcmSamples: Int16Array) => void) {}

	async start(microphoneId?: string) {
		const stream = await navigator.mediaDevices.getUserMedia({
			audio: {
				deviceId: microphoneId ? { exact: microphoneId } : undefined,
				channelCount: 1,
				echoCancellation: true,
				noiseSuppression: true,
				autoGainControl: true
			}
		});
		if (this.isStopped) return stopMediaStream(stream);
		this.stream = stream;
		this.audioContext = new AudioContext();
		await this.audioContext.audioWorklet.addModule('/pcm-worklet.js');
		if (this.isStopped) return;
		const microphoneSource = this.audioContext.createMediaStreamSource(stream);
		this.workletNode = new AudioWorkletNode(this.audioContext, 'pcm-worklet');
		this.workletNode.port.onmessage = (message: MessageEvent<ArrayBuffer>) => {
			const pcmSamples = new Int16Array(message.data);
			const currentLevel = Math.min(1, rootMeanSquare(pcmSamples) * MICROPHONE_LEVEL_GAIN);
			this.level = Math.max(currentLevel, this.level * MICROPHONE_LEVEL_DECAY);
			this.onAudioChunk(pcmSamples);
		};
		microphoneSource.connect(this.workletNode);
	}

	async stop() {
		this.isStopped = true;
		this.workletNode?.disconnect();
		stopMediaStream(this.stream);
		await this.audioContext?.close().catch(() => {});
		this.audioContext = this.workletNode = this.stream = undefined;
		this.level = 0;
	}
}

function rootMeanSquare(pcmSamples: Int16Array): number {
	let sumOfSquares = 0;
	for (const sample of pcmSamples) sumOfSquares += sample * sample;
	return Math.sqrt(sumOfSquares / pcmSamples.length) / 32768;
}

let soundEffectsContext: AudioContext | undefined;

export function playShutterSound() {
	try {
		soundEffectsContext ??= new AudioContext();
		const audioContext = soundEffectsContext;
		const sampleCount = Math.floor(audioContext.sampleRate * 0.12);
		const buffer = audioContext.createBuffer(1, sampleCount, audioContext.sampleRate);
		const samples = buffer.getChannelData(0);
		for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex++) {
			const progress = sampleIndex / sampleCount;
			const envelope = Math.exp(-progress * 40) + 0.6 * Math.exp(-Math.abs(progress - 0.55) * 60);
			samples[sampleIndex] = (Math.random() * 2 - 1) * envelope * 0.5;
		}
		const bufferSource = audioContext.createBufferSource();
		const highPassFilter = audioContext.createBiquadFilter();
		highPassFilter.type = 'highpass';
		highPassFilter.frequency.value = 1200;
		bufferSource.buffer = buffer;
		bufferSource.connect(highPassFilter).connect(audioContext.destination);
		bufferSource.start();
	} catch {
		// Audio is blocked; the flash still shows.
	}
}

export function playBeep(frequencyHz = 880) {
	try {
		soundEffectsContext ??= new AudioContext();
		const oscillator = soundEffectsContext.createOscillator();
		const gain = soundEffectsContext.createGain();
		oscillator.frequency.value = frequencyHz;
		gain.gain.setValueAtTime(0.15, soundEffectsContext.currentTime);
		gain.gain.exponentialRampToValueAtTime(0.001, soundEffectsContext.currentTime + 0.15);
		oscillator.connect(gain).connect(soundEffectsContext.destination);
		oscillator.start();
		oscillator.stop(soundEffectsContext.currentTime + 0.15);
	} catch {
		// Audio is blocked; the countdown still shows.
	}
}
