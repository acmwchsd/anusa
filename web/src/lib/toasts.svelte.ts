export interface Toast {
	id: number;
	kind: 'info' | 'success' | 'error';
	title: string;
	detail?: string;
	imageUrl?: string;
}

const DEFAULT_TOAST_DURATION_MS = 4500;
const ERROR_TOAST_DURATION_MS = 7000;

let lastToastId = 0;
export const activeToasts: Toast[] = $state([]);

export function showToast(toast: Omit<Toast, 'id'>, durationMs = DEFAULT_TOAST_DURATION_MS) {
	const toastId = ++lastToastId;
	activeToasts.push({ ...toast, id: toastId });
	setTimeout(() => dismissToast(toastId), durationMs);
}

export function dismissToast(toastId: number) {
	const toastIndex = activeToasts.findIndex((toast) => toast.id === toastId);
	if (toastIndex >= 0) activeToasts.splice(toastIndex, 1);
}

export const showErrorToast = (error: unknown, title = 'Something went wrong') =>
	showToast(
		{ kind: 'error', title, detail: error instanceof Error ? error.message : String(error) },
		ERROR_TOAST_DURATION_MS
	);
