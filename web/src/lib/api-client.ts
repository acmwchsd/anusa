export interface ReferencePhoto {
	id: string;
	created_at: string;
	source: string;
}

export interface Person {
	id: string;
	name: string;
	created_at: string;
	samples: ReferencePhoto[];
}

export const MINIMUM_REFERENCE_PHOTOS = 3;

export const compareByName = (firstPerson: Person, secondPerson: Person) =>
	firstPerson.name.localeCompare(secondPerson.name);

export interface PhotoFace {
	index: number;
	bbox: [number, number, number, number];
	score: number;
	person_id: string | null;
	name: string | null;
	similarity: number | null;
	assigned: boolean;
}

export type PhotoTrigger = 'voice' | 'browser-voice' | 'key' | 'button' | 'api';

export interface Photo {
	id: string;
	taken_at: string;
	width: number;
	height: number;
	bytes: number;
	trigger: string;
	heard: string | null;
	url: string;
	faces: PhotoFace[];
	people: string[];
}

export interface Settings {
	match_threshold: number;
	keywords: string[];
	keyword_sensitivity: number;
	cooldown_s: number;
}

export interface SpeechStatus {
	url: string | null;
	available: boolean;
	model_version: string | null;
	error: string | null;
}

export interface HealthStatus {
	status: string;
	people: number;
	samples: number;
	photos: number;
	speech: SpeechStatus;
}

export interface AddReferencePhotosResult {
	added: { file: string; sample: ReferencePhoto; warning: string | null }[];
	rejected: { file: string; error: string }[];
	person: Person;
}

export type FaceLabel = { person_id?: string; name?: string } | null;

export class ApiError extends Error {
	constructor(
		public statusCode: number,
		message: string
	) {
		super(message);
	}
}

async function sendRequest<ResponseBody>(path: string, requestOptions?: RequestInit): Promise<ResponseBody> {
	const response = await fetch(path, requestOptions);
	if (!response.ok) {
		let errorMessage = `${response.status} ${response.statusText}`;
		try {
			errorMessage = (await response.json()).error ?? errorMessage;
		} catch {
			// The body is not JSON, so the status line is the best message available.
		}
		throw new ApiError(response.status, errorMessage);
	}
	return response.status === 204 ? (undefined as ResponseBody) : response.json();
}

const jsonRequest = (method: string, body: unknown): RequestInit => ({
	method,
	headers: { 'content-type': 'application/json' },
	body: JSON.stringify(body)
});

export const referencePhotoUrl = (personId: string, referencePhotoId: string) =>
	`/api/people/${personId}/samples/${referencePhotoId}/image`;

/** A person's first reference photo, used as their avatar. */
export const personAvatarUrl = (person: Person | undefined) =>
	person?.samples[0] ? referencePhotoUrl(person.id, person.samples[0].id) : null;

export const api = {
	getHealth: () => sendRequest<HealthStatus>('/api/health'),

	getSettings: () => sendRequest<Settings>('/api/settings'),
	saveSettings: (settings: Settings) => sendRequest<Settings>('/api/settings', jsonRequest('PUT', settings)),

	listPeople: () => sendRequest<Person[]>('/api/people'),
	createPerson: (name: string) => sendRequest<Person>('/api/people', jsonRequest('POST', { name })),
	renamePerson: (personId: string, newName: string) =>
		sendRequest<Person>(`/api/people/${personId}`, jsonRequest('PATCH', { name: newName })),
	deletePerson: (personId: string) => sendRequest<void>(`/api/people/${personId}`, { method: 'DELETE' }),

	addReferencePhotos: (personId: string, images: Blob[], source: 'upload' | 'camera') => {
		const formData = new FormData();
		formData.append('source', source);
		images.forEach((image, imageIndex) => {
			const filename = image instanceof File ? image.name : `${source}-${imageIndex + 1}.jpg`;
			formData.append('image', image, filename);
		});
		return sendRequest<AddReferencePhotosResult>(`/api/people/${personId}/samples`, {
			method: 'POST',
			body: formData
		});
	},
	deleteReferencePhoto: (personId: string, referencePhotoId: string) =>
		sendRequest<void>(`/api/people/${personId}/samples/${referencePhotoId}`, { method: 'DELETE' }),

	listPhotos: () => sendRequest<Photo[]>('/api/photos'),
	/** `captureRequestId` is set when the server asked for this photo and is waiting for it. */
	uploadPhoto: (photo: Blob, trigger: PhotoTrigger, heardText?: string, captureRequestId?: string) => {
		const formData = new FormData();
		formData.append('photo', photo, 'photo.jpg');
		formData.append('trigger', trigger);
		if (heardText) formData.append('heard', heardText);
		if (captureRequestId) formData.append('request_id', captureRequestId);
		return sendRequest<Photo>('/api/photos', { method: 'POST', body: formData });
	},
	deletePhoto: (photoId: string) => sendRequest<void>(`/api/photos/${photoId}`, { method: 'DELETE' }),
	labelFace: (photoId: string, faceIndex: number, faceLabel: FaceLabel) =>
		sendRequest<Photo>(`/api/photos/${photoId}/faces/${faceIndex}`, jsonRequest('PUT', faceLabel ?? {}))
};
