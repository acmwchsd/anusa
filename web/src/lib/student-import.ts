// Bulk import: works out which student each picked file belongs to.

export interface StudentImportGroup {
	name: string;
	files: File[];
}

export function studentNameFromFile(file: File): string {
	const pathParts = (file.webkitRelativePath || '').split('/');
	const isInsideStudentFolder = pathParts.length >= 3;
	const rawName = isInsideStudentFolder ? pathParts[pathParts.length - 2] : file.name.replace(/\.[^.]+$/, '');
	const cleanedName = rawName
		.replace(/[_.]+/g, ' ')
		.replace(/[\s-]*\(?\d+\)?$/, '')
		.replace(/\s+/g, ' ')
		.trim();
	const isAllLowercase = cleanedName === cleanedName.toLowerCase();
	return isAllLowercase ? cleanedName.replace(/(^|\s)\S/g, (firstLetter) => firstLetter.toUpperCase()) : cleanedName;
}

const isImageFile = (file: File) => file.type.startsWith('image/') || /\.(jpe?g|png|webp|heic)$/i.test(file.name);

export function groupFilesByStudent(files: Iterable<File>): StudentImportGroup[] {
	const filesByStudentName: Record<string, File[]> = {};
	for (const file of files) {
		if (isImageFile(file)) (filesByStudentName[studentNameFromFile(file)] ??= []).push(file);
	}
	return Object.entries(filesByStudentName)
		.sort(([firstName], [secondName]) => firstName.localeCompare(secondName))
		.map(([name, studentFiles]) => ({ name, files: studentFiles }));
}
