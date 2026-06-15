from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple
import math
import pickle
import re
import unicodedata

import torch
import torch.nn.functional as F
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "saved_model.pt"
DATA_DIR = BASE_DIR / "model" / "data"
DATASET_DIR = DATA_DIR / "dataset"
MAX_COUNT_FILES = 100
MAX_COUNT_CHARS = 200000

app = FastAPI(title="Asistente de Redacción")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class CorrectionRequest(BaseModel):
    text: str

class CorrectionSuggestion(BaseModel):
    original: str
    corrected: str
    explanation: str

class CorrectionResponse(BaseModel):
    corrected_text: str
    suggestions: List[CorrectionSuggestion]
    next_suggestions: List[str]


class SimpleRNN(torch.nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int = 128, hidden_dim: int = 256):
        super().__init__()
        self.embedding = torch.nn.Embedding(vocab_size, embed_dim)
        self.rnn = torch.nn.GRU(embed_dim, hidden_dim, batch_first=True)
        self.fc = torch.nn.Linear(hidden_dim, vocab_size)

    def forward(self, x: torch.Tensor, hidden=None) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.embedding(x)
        output, hidden = self.rnn(x, hidden)
        return self.fc(output), hidden


def load_training_model():
    if not MODEL_PATH.exists():
        return None, None, None

    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    vocab = checkpoint["vocab"]
    char2idx = {ch: i for i, ch in enumerate(vocab)}
    idx2char = {i: ch for i, ch in enumerate(vocab)}

    state_dict = checkpoint["model_state"]
    embed_dim = state_dict["embedding.weight"].shape[1]
    hidden_dim = state_dict["rnn.weight_hh_l0"].shape[1]

    model = SimpleRNN(vocab_size=len(vocab), embed_dim=embed_dim, hidden_dim=hidden_dim)
    model.load_state_dict(state_dict)
    model.eval()
    return model, char2idx, idx2char


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text)

COMMON_MOJIBAKE = {
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã±": "ñ",
    "Ã": "Á",
    "Ã‰": "É",
    "Ã": "Í",
    "Ã“": "Ó",
    "Ãš": "Ú",
    "Ã‘": "Ñ",
}

WORD_RE = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+$")


def fix_mojibake(text: str) -> str:
    for bad, good in COMMON_MOJIBAKE.items():
        text = text.replace(bad, good)
    return text

BAD_PHRASE_PATTERNS = [
    "nonfiltered",
    "doc",
    "endofarticle",
    "dbindex",
    "processed",
    "id",
    "http",
    "www",
    "jpg",
    "png",
    "cc",
    "�",
]

STOP_WORDS = {
    "a",
    "y",
    "o",
    "de",
    "la",
    "el",
    "en",
    "al",
    "lo",
    "un",
    "se",
    "es",
    "del",
    "por",
    "para",
    "con",
    "sin",
    "las",
    "los",
    "su",
    "sus",
    "una",
    "unos",
    "unas",
}

BAD_PHRASE_PAIRS = {
    "del de",
    "de de",
    "a de",
    "con de",
    "o de",
    "y de",
    "del la",
    "del el",
    "de c",
    "a c",
    "c nonfiltered",
}


def phrase_candidate_valid(phrase: str) -> bool:
    phrase = phrase.lower().strip()
    if any(token in phrase for token in BAD_PHRASE_PATTERNS):
        return False
    if re.search(r"\d", phrase):
        return False
    if re.search(r"[^A-Za-zÁÉÍÓÚáéíóúÜüÑñ ]", phrase):
        return False
    words = phrase.split()
    if len(words) < 2:
        return False
    if len(words) > 7:
        return False
    if words[-1] in STOP_WORDS and len(words) > 2:
        return False
    if any(pair in phrase for pair in BAD_PHRASE_PAIRS):
        return False
    if any(len(w) == 1 and w not in STOP_WORDS for w in words):
        return False
    if len(words) >= 3 and words[-2] in STOP_WORDS and words[-1] in STOP_WORDS:
        return False
    if len(words) >= 3 and words[0] in STOP_WORDS and words[1] in STOP_WORDS:
        return False
    if phrase.count(" ") >= 3 and any(len(w) <= 2 for w in words[-2:]):
        return False
    return True


def strip_accents(word: str) -> str:
    normalized = unicodedata.normalize("NFD", word)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped


def score_phrase(phrase: str) -> float:
    if MODEL is None or CHAR2IDX is None:
        return 0.0
    return score_sequence(phrase)


CACHE_PATH = BASE_DIR / "model" / "corpus_cache.pkl"


CACHE_PATH = BASE_DIR / "model" / "corpus_cache.pkl"


def read_file_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw.decode(encoding)
        except Exception:
            continue
        text = normalize_text(text)
        if "�" in text and encoding == "utf-8":
            text = fix_mojibake(text)
        return text
    return normalize_text(raw.decode("utf-8", errors="replace"))


def build_corpus_counts() -> Tuple[Dict[str, int], Dict[str, Counter], Dict[Tuple[str, str], Counter], Dict[Tuple[str, str], Counter], Dict[str, Counter], Counter]:
    word_freq: Dict[str, int] = {}
    bigram_freq: Dict[str, Counter] = defaultdict(Counter)
    trigram_freq: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    phrase_bigram_freq: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    phrase_unigram_freq: Dict[str, Counter] = defaultdict(Counter)
    global_phrase_freq: Counter = Counter()

    if DATASET_DIR.exists():
        paths = sorted([p for p in DATASET_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store"])
    else:
        paths = sorted([p for p in DATA_DIR.glob("*.txt") if p.is_file() and p.name != ".DS_Store"])

    if MAX_COUNT_FILES and len(paths) > MAX_COUNT_FILES:
        paths = paths[:MAX_COUNT_FILES]

    total_chars = 0
    for path in paths:
        try:
            text = read_file_text(path).lower()
        except Exception:
            continue

        words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+", text)
        for word in words:
            if len(word) < 1:
                continue
            word_freq[word] = word_freq.get(word, 0) + 1

        for i, word in enumerate(words):
            if i >= 1:
                bigram_freq[words[i - 1]][word] += 1
            if i >= 2:
                trigram_freq[(words[i - 2], words[i - 1])][word] += 1
            if i >= 3:
                phrase_bigram_freq[(words[i - 3], words[i - 2])][" ".join(words[i - 1 : i + 1])] += 1
            if i >= 2:
                phrase_unigram_freq[words[i - 2]][" ".join(words[i - 1 : i + 2])] += 1
            if i >= 1:
                global_phrase_freq[" ".join(words[i - 1 : i + 2])] += 1

        total_chars += len(text)
        if MAX_COUNT_CHARS and total_chars >= MAX_COUNT_CHARS:
            break

    return word_freq, bigram_freq, trigram_freq, phrase_bigram_freq, phrase_unigram_freq, global_phrase_freq


def dump_corpus_cache(path: Path = CACHE_PATH) -> Tuple[Dict[str, int], Dict[str, Counter], Dict[Tuple[str, str], Counter], Dict[Tuple[str, str], Counter], Dict[str, Counter], Counter]:
    counts = build_corpus_counts()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(counts, f, protocol=pickle.HIGHEST_PROTOCOL)
    return counts


def load_corpus_cache(path: Path = CACHE_PATH) -> Tuple[Dict[str, int], Dict[str, Counter], Dict[Tuple[str, str], Counter], Dict[Tuple[str, str], Counter], Dict[str, Counter], Counter]:
    if path.exists():
        try:
            with path.open("rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return build_corpus_counts()


dictionary, BIGRAM_FREQ, TRIGRAM_FREQ, PHRASE_BIGRAM_FREQ, PHRASE_UNIGRAM_FREQ, GLOBAL_PHRASE_FREQ = load_corpus_cache()
GLOBAL_PHRASE_FREQ_COMMON = GLOBAL_PHRASE_FREQ.most_common(2000)
GLOBAL_PHRASE_FREQ_VALID_COMMON = [(phrase, count) for phrase, count in GLOBAL_PHRASE_FREQ_COMMON if phrase_candidate_valid(phrase)]
MODEL, CHAR2IDX, IDX2CHAR = load_training_model()
UNK_INDEX = CHAR2IDX.get("<unk>") if CHAR2IDX else 0
GLOBAL_WORDS_BY_FREQ = [word for word, _ in sorted(dictionary.items(), key=lambda item: -item[1])]
ACCENT_VARIANTS: Dict[str, Counter] = defaultdict(Counter)
for word, count in dictionary.items():
    base = strip_accents(word)
    if base != word:
        ACCENT_VARIANTS[base][word] += count

ACCENT_MAP = {
    "a": "á",
    "e": "é",
    "i": "í",
    "o": "ó",
    "u": "ú",
    "n": "ñ",
}


def score_sequence(sequence: str) -> float:
    if MODEL is None or CHAR2IDX is None:
        return 0.0
    indices = [CHAR2IDX.get(ch, UNK_INDEX) for ch in sequence]
    if len(indices) < 2:
        return 0.0
    x = torch.tensor(indices[:-1], dtype=torch.long).unsqueeze(0)
    target = torch.tensor(indices[1:], dtype=torch.long).unsqueeze(0)
    with torch.no_grad():
        logits, _ = MODEL(x)
        log_probs = F.log_softmax(logits, dim=-1)
        selected = log_probs.gather(-1, target.unsqueeze(-1)).squeeze(-1)
        return float(selected.sum().item())


def preserve_case(original: str, corrected: str) -> str:
    if original.isupper():
        return corrected.upper()
    if original[0].isupper():
        return corrected[0].upper() + corrected[1:]
    return corrected


def generate_accent_candidates(word: str) -> List[str]:
    candidates = set()
    for i, ch in enumerate(word):
        if ch.lower() in ACCENT_MAP and ch == ch.lower():
            candidate = word[:i] + ACCENT_MAP[ch] + word[i + 1 :]
            candidates.add(candidate)
    return list(candidates)


def generate_duplicate_reduction_candidates(word: str) -> List[str]:
    cleaned = re.sub(r"(.)\1+", r"\1", word)
    return [cleaned] if cleaned != word else []


def edits1(word: str) -> List[str]:
    letters = "abcdefghijklmnopqrstuvwxyzáéíóúüñ"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = [L + R[1:] for L, R in splits if R]
    transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
    replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
    inserts = [L + c + R for L, R in splits for c in letters]
    return list({*deletes, *transposes, *replaces, *inserts})


def choose_best_candidate(original: str, candidates: List[str]) -> str:
    best = original
    best_score = dictionary.get(original.lower(), 0)
    if MODEL is not None:
        best_score += score_sequence(original.lower()) / 10.0
    for candidate in candidates:
        score = dictionary.get(candidate.lower(), 0)
        if MODEL is not None:
            score += score_sequence(candidate.lower()) / 10.0
        if score > best_score:
            best_score = score
            best = candidate
    return best


def correct_token(token: str) -> Tuple[str, bool]:
    lower = token.lower()
    if lower in dictionary:
        return token, False

    accent_candidates = [c for c in generate_accent_candidates(lower) if c in dictionary]
    duplicate_candidates = [c for c in generate_duplicate_reduction_candidates(lower) if c in dictionary]
    edit_candidates = [c for c in edits1(lower) if c in dictionary]

    accent_variants = ACCENT_VARIANTS.get(strip_accents(lower), Counter())
    accent_candidates += [w for w, _ in accent_variants.most_common(5) if w in dictionary]

    candidates = accent_candidates + duplicate_candidates + edit_candidates
    if candidates:
        best = choose_best_candidate(lower, candidates)
        return preserve_case(token, best), best.lower() != lower

    return token, False


def score_next_word_with_context(context_text: str, next_word: str) -> float:
    if MODEL is None or CHAR2IDX is None:
        return 0.0

    context = normalize_text(context_text).lower()
    indices = [CHAR2IDX.get(ch, UNK_INDEX) for ch in context if ch in CHAR2IDX or True]
    if len(indices) > 512:
        indices = indices[-512:]

    with torch.no_grad():
        if indices:
            x = torch.tensor(indices, dtype=torch.long).unsqueeze(0)
            logits, hidden = MODEL(x)
            current_logits = logits[0, -1]
        else:
            current_logits = None
            hidden = None

        score = 0.0
        for ch in normalize_text(next_word).lower():
            idx = CHAR2IDX.get(ch, UNK_INDEX)
            if current_logits is None:
                current_logits = torch.zeros((len(CHAR2IDX),), dtype=torch.float)
            probs = F.log_softmax(current_logits, dim=-1)
            score += float(probs[idx])
            x = torch.tensor([[idx]], dtype=torch.long)
            logits, hidden = MODEL(x, hidden)
            current_logits = logits[0, -1]

    return score


def get_prefix_completions(context_words: List[str], prefix: str, limit: int = 80) -> List[str]:
    prefix = prefix.lower()
    candidates: Counter = Counter()

    if len(context_words) >= 2:
        for phrase, count in PHRASE_BIGRAM_FREQ.get((context_words[-2], context_words[-1]), Counter()).items():
            if phrase.startswith(prefix) and phrase_candidate_valid(phrase):
                candidates[phrase] += count * 12
    if len(context_words) >= 1:
        for phrase, count in PHRASE_UNIGRAM_FREQ.get(context_words[-1], Counter()).items():
            if phrase.startswith(prefix) and phrase_candidate_valid(phrase):
                candidates[phrase] += count * 8

    for phrase, count in GLOBAL_PHRASE_FREQ_VALID_COMMON:
        if phrase.startswith(prefix):
            candidates[phrase] += max(1, count // 2)

    scored = []
    for phrase, count in candidates.most_common(limit * 5):
        score = math.log1p(count)
        scored.append((phrase, score))

    if not scored:
        scored = [
            (phrase, math.log1p(count))
            for phrase, count in GLOBAL_PHRASE_FREQ_VALID_COMMON[: limit * 2]
        ]

    scored = [item for item in scored if item[1] > -20]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [phrase for phrase, _ in scored[:limit]]


def get_next_phrase_candidates(context_words: List[str], prefix: str = "", limit: int = 80) -> List[str]:
    prefix = prefix.lower()
    candidates: Counter = Counter()

    if len(context_words) >= 2:
        for phrase, count in PHRASE_BIGRAM_FREQ.get((context_words[-2], context_words[-1]), Counter()).items():
            if phrase_candidate_valid(phrase):
                candidates[phrase] += count * 15
    if len(context_words) >= 1:
        for phrase, count in PHRASE_UNIGRAM_FREQ.get(context_words[-1], Counter()).items():
            if phrase_candidate_valid(phrase):
                candidates[phrase] += count * 7

    for phrase, count in GLOBAL_PHRASE_FREQ_VALID_COMMON:
        candidates[phrase] += max(1, count // 4)

    scored = []
    for phrase, count in candidates.most_common(limit * 5):
        score = math.log1p(count)
        scored.append((phrase, score))

    if prefix:
        scored = [(phrase, score) for phrase, score in scored if phrase.startswith(prefix)]
        if not scored:
            for phrase, count in GLOBAL_PHRASE_FREQ_VALID_COMMON:
                if phrase.startswith(prefix):
                    scored.append((phrase, math.log1p(count)))
                    if len(scored) >= limit * 4:
                        break

    if not scored:
        scored = [
            (phrase, math.log1p(count))
            for phrase, count in GLOBAL_PHRASE_FREQ_VALID_COMMON[: limit * 2]
        ]

    scored = [item for item in scored if item[1] > -20]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [phrase for phrase, _ in scored[:limit]]


@lru_cache(maxsize=512)
def get_next_suggestions(text: str, limit: int = 12) -> List[str]:
    text = normalize_text(text)
    has_trailing_space = len(text) > 0 and text[-1].isspace()
    prefix_match = re.search(r"([A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+)$", text)
    prefix = prefix_match.group(1).lower() if prefix_match else ""
    prefix_start = prefix_match.start() if prefix_match else len(text)
    context_text = text[:prefix_start] if prefix_match else text
    context_words = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+", context_text)]

    suggestions: List[str] = []
    if prefix and not has_trailing_space:
        suggestions.extend(get_prefix_completions(context_words, prefix, limit=limit * 2))
        if prefix in dictionary and len(prefix) > 1:
            suggestions.extend(get_next_phrase_candidates(context_words + [prefix], "", limit=limit * 2))
    else:
        suggestions.extend(get_next_phrase_candidates(context_words, "", limit=limit * 2))

    unique = []
    seen = set()
    for candidate in suggestions:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
        if len(unique) >= limit:
            break

    if len(unique) < limit and prefix:
        for phrase, _ in GLOBAL_PHRASE_FREQ_COMMON:
            if phrase.startswith(prefix) and phrase not in seen and phrase_candidate_valid(phrase):
                unique.append(phrase)
                seen.add(phrase)
                if len(unique) >= limit:
                    break

    if len(unique) < limit:
        for phrase, _ in GLOBAL_PHRASE_FREQ_COMMON:
            if phrase not in seen and phrase_candidate_valid(phrase):
                unique.append(phrase)
                seen.add(phrase)
                if len(unique) >= limit:
                    break

    return unique


def correct_text(text: str) -> Dict[str, object]:
    text = normalize_text(text)
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+|[^A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+", text)
    corrected_tokens = []
    suggestions = []

    for token in tokens:
        if WORD_RE.fullmatch(token):
            corrected, changed = correct_token(token)
            corrected_tokens.append(corrected)
            if changed:
                suggestions.append({
                    "original": token,
                    "corrected": corrected,
                    "explanation": "Sugerencia de corrección basada en el corpus y el asistente de redacción",
                })
        else:
            corrected_tokens.append(token)

    next_suggestions = get_next_suggestions(text)

    return {
        "corrected_text": "".join(corrected_tokens),
        "suggestions": suggestions,
        "next_suggestions": next_suggestions,
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "backend": "corrector"}


@app.post("/correct", response_model=CorrectionResponse)
def correct_text_endpoint(request: CorrectionRequest):
    result = correct_text(request.text)
    return CorrectionResponse(**result)
