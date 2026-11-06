// Microphone -> 16 kHz mono Int16 PCM, posted in 100 ms chunks.
// Runs on the audio thread. `sampleRate` is the AudioContext's (usually 44.1/48 kHz).
const TARGET_RATE = 16000;
const CHUNK = TARGET_RATE / 10;

class PcmWorklet extends AudioWorkletProcessor {
	constructor() {
		super();
		this.step = sampleRate / TARGET_RATE; // input samples per output sample
		this.pos = 0;
		this.sum = 0;
		this.count = 0;
		this.out = new Int16Array(CHUNK);
		this.n = 0;
	}

	process(inputs) {
		const input = inputs[0];
		if (!input || input.length === 0) return true;
		const channel = input[0];
		for (let i = 0; i < channel.length; i++) {
			// box filter: average every input sample that falls in one output slot
			// (a cheap low-pass, so 48 kHz -> 16 kHz does not alias)
			this.sum += channel[i];
			this.count++;
			this.pos += 1;
			if (this.pos >= this.step) {
				this.pos -= this.step;
				const v = this.sum / this.count;
				this.sum = 0;
				this.count = 0;
				this.out[this.n++] = Math.max(-32768, Math.min(32767, Math.round(v * 32767)));
				if (this.n === CHUNK) {
					this.port.postMessage(this.out.buffer, [this.out.buffer]);
					this.out = new Int16Array(CHUNK);
					this.n = 0;
				}
			}
		}
		return true;
	}
}

registerProcessor('pcm-worklet', PcmWorklet);
