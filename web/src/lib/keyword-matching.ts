export interface KeywordMatch {
	keyword: string;
	by: 'spelling' | 'sound';
	heard: string;
	similarity: number;
}

const SOUND_MATCH_EXTRA_STRICTNESS = 0.15;
const MAXIMUM_WORDS_PER_MATCH = 3;
const MINIMUM_SOUND_SKELETON_LENGTH = 4;
const MINIMUM_LENGTH_WITHOUT_SILENT_E = 4;

export const splitIntoWords = (text: string) =>
	text
		.toLowerCase()
		.split(/[^\p{L}\p{N}]+/u)
		.filter(Boolean);

export function levenshteinDistance(firstText: string, secondText: string): number {
	let previousRow = Array.from({ length: secondText.length + 1 }, (_, columnIndex) => columnIndex);
	for (let firstIndex = 0; firstIndex < firstText.length; firstIndex++) {
		const currentRow = [firstIndex + 1];
		for (let secondIndex = 0; secondIndex < secondText.length; secondIndex++) {
			const substitutionCost = previousRow[secondIndex] + (firstText[firstIndex] === secondText[secondIndex] ? 0 : 1);
			const deletionCost = previousRow[secondIndex + 1] + 1;
			const insertionCost = currentRow[secondIndex] + 1;
			currentRow.push(Math.min(substitutionCost, deletionCost, insertionCost));
		}
		previousRow = currentRow;
	}
	return previousRow[secondText.length];
}

export function textSimilarity(firstText: string, secondText: string): number {
	const longestLength = Math.max(firstText.length, secondText.length);
	return longestLength === 0 ? 0 : 1 - levenshteinDistance(firstText, secondText) / longestLength;
}

export function soundSkeleton(text: string): string {
	const letters = text.toLowerCase().replace(/[^a-z]/g, '');
	const startsWithSilentLetter = /^(kn|gn|pn|wr|ps)/.test(letters);
	let skeleton = '';
	const appendSound = (soundCode: string) => {
		if (!skeleton.endsWith(soundCode)) skeleton += soundCode;
	};

	for (let letterIndex = startsWithSilentLetter ? 1 : 0; letterIndex < letters.length; letterIndex++) {
		const letter = letters[letterIndex];
		const nextLetter = letters[letterIndex + 1];
		const isSoftened = nextLetter === 'e' || nextLetter === 'i' || nextLetter === 'y';
		if ('aeiouywh'.includes(letter)) continue;
		if ((letter === 'c' || letter === 's') && nextLetter === 'h') {
			appendSound('X');
			letterIndex++;
		} else if (letter === 't' && nextLetter === 'h') {
			appendSound('0');
			letterIndex++;
		} else if (letter === 'p' && nextLetter === 'h') {
			appendSound('F');
			letterIndex++;
		} else if (letter === 'g' && nextLetter === 'h') {
			letterIndex++;
		} else if (letter === 'c') {
			appendSound(isSoftened ? 'S' : 'K');
		} else if (letter === 'g') {
			appendSound(isSoftened ? 'J' : 'G');
		} else if (letter === 'q') {
			appendSound('K');
		} else if (letter === 'x') {
			appendSound('K');
			appendSound('S');
		} else {
			appendSound(letter.toUpperCase());
		}
	}
	return skeleton;
}

/** The keyword as written, plus without a silent final "e" (techpreneure -> techpreneur). */
export function keywordSpellings(keyword: string): string[] {
	const joinedKeyword = splitIntoWords(keyword).join('');
	const canDropSilentE = joinedKeyword.endsWith('e') && joinedKeyword.length - 1 >= MINIMUM_LENGTH_WITHOUT_SILENT_E;
	return canDropSilentE ? [joinedKeyword, joinedKeyword.slice(0, -1)] : [joinedKeyword];
}

export function findKeyword(transcript: string, keywords: string[], minimumSimilarity: number): KeywordMatch | null {
	const transcriptWords = splitIntoWords(transcript);
	const minimumSoundSimilarity = Math.min(minimumSimilarity + SOUND_MATCH_EXTRA_STRICTNESS, 1);
	let bestMatch: KeywordMatch | null = null;

	const considerMatch = (
		keyword: string,
		matchedBy: KeywordMatch['by'],
		wordWindow: string[],
		similarity: number,
		requiredSimilarity: number
	) => {
		if (similarity >= requiredSimilarity && (!bestMatch || similarity > bestMatch.similarity)) {
			bestMatch = { keyword, by: matchedBy, heard: wordWindow.join(' '), similarity };
		}
	};

	for (const keyword of keywords) {
		const spellings = keywordSpellings(keyword);
		const keywordSoundSkeleton = soundSkeleton(keyword);
		for (let wordsInWindow = 1; wordsInWindow <= MAXIMUM_WORDS_PER_MATCH; wordsInWindow++) {
			for (let windowStart = 0; windowStart + wordsInWindow <= transcriptWords.length; windowStart++) {
				const wordWindow = transcriptWords.slice(windowStart, windowStart + wordsInWindow);
				const joinedWindow = wordWindow.join('');
				for (const spelling of spellings) {
					considerMatch(keyword, 'spelling', wordWindow, textSimilarity(joinedWindow, spelling), minimumSimilarity);
				}
				if (keywordSoundSkeleton.length >= MINIMUM_SOUND_SKELETON_LENGTH) {
					const soundSimilarity = textSimilarity(soundSkeleton(joinedWindow), keywordSoundSkeleton);
					considerMatch(keyword, 'sound', wordWindow, soundSimilarity, minimumSoundSimilarity);
				}
			}
		}
	}
	return bestMatch;
}
