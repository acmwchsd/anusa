import re
from dataclasses import dataclass

SOUND_MATCH_EXTRA_STRICTNESS = 0.15
MAXIMUM_WORDS_PER_MATCH = 3
MINIMUM_SOUND_SKELETON_LENGTH = 4
MINIMUM_LENGTH_WITHOUT_SILENT_E = 4
SILENT_FIRST_LETTER_PAIRS = ("kn", "gn", "pn", "wr", "ps")


@dataclass
class KeywordMatch:
    keyword: str
    matched_by: str
    heard_text: str
    similarity: float

    def to_json(self) -> dict:
        return {"keyword": self.keyword, "by": self.matched_by, "heard": self.heard_text, "similarity": self.similarity}


def split_into_words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.lower())


def levenshtein_distance(first_text: str, second_text: str) -> int:
    previous_row = list(range(len(second_text) + 1))
    for first_index, first_character in enumerate(first_text):
        current_row = [first_index + 1]
        for second_index, second_character in enumerate(second_text):
            substitution_cost = previous_row[second_index] + (first_character != second_character)
            deletion_cost = previous_row[second_index + 1] + 1
            insertion_cost = current_row[second_index] + 1
            current_row.append(min(substitution_cost, deletion_cost, insertion_cost))
        previous_row = current_row
    return previous_row[-1]


def text_similarity(first_text: str, second_text: str) -> float:
    longest_length = max(len(first_text), len(second_text))
    if longest_length == 0:
        return 0.0
    return 1.0 - levenshtein_distance(first_text, second_text) / longest_length


def sound_skeleton(text: str) -> str:
    letters = [character for character in text.lower() if character.isascii() and character.isalpha()]
    starts_with_silent_letter = "".join(letters[:2]) in SILENT_FIRST_LETTER_PAIRS
    skeleton: list[str] = []

    def append_sound(sound_code: str) -> None:
        if not skeleton or skeleton[-1] != sound_code:
            skeleton.append(sound_code)

    letter_index = 1 if starts_with_silent_letter else 0
    while letter_index < len(letters):
        letter = letters[letter_index]
        next_letter = letters[letter_index + 1] if letter_index + 1 < len(letters) else ""
        is_softened = next_letter in ("e", "i", "y")
        if letter in "aeiouywh":
            pass
        elif letter in "cs" and next_letter == "h":
            append_sound("X")
            letter_index += 1
        elif letter == "t" and next_letter == "h":
            append_sound("0")
            letter_index += 1
        elif letter == "p" and next_letter == "h":
            append_sound("F")
            letter_index += 1
        elif letter == "g" and next_letter == "h":
            letter_index += 1
        elif letter == "c":
            append_sound("S" if is_softened else "K")
        elif letter == "g":
            append_sound("J" if is_softened else "G")
        elif letter == "q":
            append_sound("K")
        elif letter == "x":
            append_sound("K")
            append_sound("S")
        else:
            append_sound(letter.upper())
        letter_index += 1
    return "".join(skeleton)


def keyword_spellings(keyword: str) -> list[str]:
    joined_keyword = "".join(split_into_words(keyword))
    spellings = [joined_keyword]
    if joined_keyword.endswith("e") and len(joined_keyword) - 1 >= MINIMUM_LENGTH_WITHOUT_SILENT_E:
        spellings.append(joined_keyword[:-1])
    return spellings


def find_keyword(transcript: str, keywords: list[str], minimum_similarity: float) -> KeywordMatch | None:
    transcript_words = split_into_words(transcript)
    minimum_sound_similarity = min(minimum_similarity + SOUND_MATCH_EXTRA_STRICTNESS, 1.0)
    best_match: KeywordMatch | None = None

    for keyword in keywords:
        spellings = keyword_spellings(keyword)
        keyword_sound_skeleton = sound_skeleton(keyword)
        for words_in_window in range(1, MAXIMUM_WORDS_PER_MATCH + 1):
            for window_start in range(len(transcript_words) - words_in_window + 1):
                word_window = transcript_words[window_start : window_start + words_in_window]
                joined_window = "".join(word_window)

                comparisons = [
                    ("spelling", text_similarity(joined_window, spelling), minimum_similarity)
                    for spelling in spellings
                ]
                if len(keyword_sound_skeleton) >= MINIMUM_SOUND_SKELETON_LENGTH:
                    sound_similarity = text_similarity(sound_skeleton(joined_window), keyword_sound_skeleton)
                    comparisons.append(("sound", sound_similarity, minimum_sound_similarity))

                for matched_by, similarity, required_similarity in comparisons:
                    is_better_match = best_match is None or similarity > best_match.similarity
                    if similarity >= required_similarity and is_better_match:
                        best_match = KeywordMatch(
                            keyword=keyword,
                            matched_by=matched_by,
                            heard_text=" ".join(word_window),
                            similarity=similarity,
                        )
    return best_match
