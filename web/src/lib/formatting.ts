import type { Photo } from '#lib/api-client.ts';

/** pluralize(1, 'photo') -> "1 photo", pluralize(3, 'photo') -> "3 photos" */
export const pluralize = (count: number, noun: string) => `${count} ${noun}${count === 1 ? '' : 's'}`;

export const errorMessage = (error: unknown) => (error instanceof Error ? error.message : String(error));

/** "Today 9:41 AM", or "3 Oct 9:41 AM" for any other day. */
export function formatTakenAt(isoTimestamp: string): string {
	const takenAt = new Date(isoTimestamp);
	const isToday = new Date().toDateString() === takenAt.toDateString();
	const timeOfDay = takenAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	if (isToday) return `Today ${timeOfDay}`;
	return `${takenAt.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${timeOfDay}`;
}

export function describePhotoTrigger(photo: Photo): string {
	if (photo.trigger.includes('voice')) return photo.heard ? `Voice “${photo.heard}”` : 'Voice';
	if (photo.trigger === 'api') return 'API';
	return photo.trigger === 'key' ? 'Space' : 'Button';
}
