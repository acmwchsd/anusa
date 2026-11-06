import { captureVideoFrame, describeCameraError, listMediaDevices, openCamera, stopMediaStream } from '#lib/media.ts';

// HTMLMediaElement.readyState value meaning there is a picture to capture.
const HAVE_CURRENT_DATA = 2;

export class CameraFeed {
	videoElement: HTMLVideoElement | undefined = $state();
	stream: MediaStream | null = $state(null);
	error: string | null = $state(null);
	availableCameras: MediaDeviceInfo[] = $state([]);
	videoSize = $state({ width: 16, height: 9 });

	/** Increases on every start and stop, so a slow start that was overtaken closes its own stream. */
	private startAttempt = 0;

	async start(cameraId: string) {
		const thisAttempt = ++this.startAttempt;
		try {
			const stream = await openCamera(cameraId || undefined);
			if (thisAttempt !== this.startAttempt) return stopMediaStream(stream);
			stopMediaStream(this.stream);
			this.stream = stream;
			this.error = null;
		} catch (error) {
			if (thisAttempt === this.startAttempt) this.error = describeCameraError(error);
		}
		this.availableCameras = await listMediaDevices('videoinput').catch(() => []);
	}

	stop() {
		this.startAttempt++;
		stopMediaStream(this.stream);
		this.stream = null;
	}

	get isReady() {
		return !!this.stream && !!this.videoElement && this.videoElement.readyState >= HAVE_CURRENT_DATA;
	}

	updateVideoSize() {
		if (this.videoElement?.videoWidth) {
			this.videoSize = { width: this.videoElement.videoWidth, height: this.videoElement.videoHeight };
		}
	}

	/** The current picture as a JPEG, scaled down to `maximumWidth`, or at full resolution without it. */
	captureFrame(maximumWidth: number | undefined, jpegQuality: number) {
		return captureVideoFrame(this.videoElement!, maximumWidth, jpegQuality);
	}
}
