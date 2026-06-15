const express = require("express");
const cors = require("cors");
const path = require("path");
const fs = require("fs");

const app = express();
const port = 8001;
const DATA_DIR = path.resolve(__dirname, "../model/data");
const DATASET_DIR = path.join(DATA_DIR, "dataset");
const WORD_RE = /[A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+/g;
const ACCENT_MAP = {
  a: "á",
  e: "é",
  i: "í",
  o: "ó",
  u: "ú",
  n: "ñ",
};

app.use(cors());
app.use(express.json());
app.options("*", cors());

app.get("/favicon.ico", (req, res) => {
  res.sendStatus(204);
});

function getAllFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return getAllFiles(fullPath);
    return fullPath;
  });
}

function buildWordFreq() {
  const files = getAllFiles(DATASET_DIR).filter((file) => path.basename(file) !== ".DS_Store");
  if (!files.length) {
    const rootFiles = fs.readdirSync(DATA_DIR)
      .filter((name) => name !== ".DS_Store")
      .map((name) => path.join(DATA_DIR, name));
    files.push(...rootFiles);
  }

  const freq = {};
  files.forEach((file) => {
    try {
      const raw = fs.readFileSync(file, "utf8");
      const words = raw.toLowerCase().match(WORD_RE) || [];
      words.forEach((word) => {
        if (word.length < 2) return;
        freq[word] = (freq[word] || 0) + 1;
      });
    } catch (err) {
      console.warn(`No se pudo leer ${file}: ${err.message}`);
    }
  });
  return freq;
}

function generateAccentCandidates(word) {
  const candidates = new Set();
  [...word].forEach((chr, idx) => {
    const lower = chr.toLowerCase();
    if (ACCENT_MAP[lower] && lower === chr) {
      const next = [...word];
      next[idx] = ACCENT_MAP[lower];
      candidates.add(next.join(""));
    }
  });
  return Array.from(candidates);
}

function edits1(word) {
  const letters = "abcdefghijklmnopqrstuvwxyzáéíóúüñ";
  const splits = [];
  for (let i = 0; i <= word.length; i += 1) {
    splits.push([word.slice(0, i), word.slice(i)]);
  }

  const deletes = splits
    .filter(([a, b]) => b)
    .map(([a, b]) => a + b.slice(1));
  const transposes = splits
    .filter(([a, b]) => b.length > 1)
    .map(([a, b]) => a + b[1] + b[0] + b.slice(2));
  const replaces = splits
    .filter(([a, b]) => b)
    .flatMap(([a, b]) => letters.split("").map((l) => a + l + b.slice(1)));
  const inserts = splits.flatMap(([a, b]) => letters.split("").map((l) => a + l + b));

  return Array.from(new Set([...deletes, ...transposes, ...replaces, ...inserts]));
}

const dictionary = (() => {
  const freq = buildWordFreq();
  const words = new Set(Object.keys(freq));
  return { freq, words };
})();

function preserveCase(original, corrected) {
  if (original === original.toUpperCase()) return corrected.toUpperCase();
  if (original[0] === original[0].toUpperCase()) return corrected[0].toUpperCase() + corrected.slice(1);
  return corrected;
}

function chooseBestWord(original, candidates) {
  let best = original;
  let bestScore = dictionary.freq[original] || 0;
  candidates.forEach((candidate) => {
    const score = dictionary.freq[candidate] || 0;
    if (score > bestScore) {
      bestScore = score;
      best = candidate;
    }
  });
  return best;
}

function correctToken(token) {
  const lower = token.toLowerCase();
  if (dictionary.words.has(lower)) {
    return token;
  }

  const accentCandidates = generateAccentCandidates(lower).filter((w) => dictionary.words.has(w));
  if (accentCandidates.length) {
    return preserveCase(token, chooseBestWord(lower, accentCandidates));
  }

  const editCandidates = edits1(lower).filter((w) => dictionary.words.has(w));
  if (editCandidates.length) {
    return preserveCase(token, chooseBestWord(lower, editCandidates));
  }

  return token;
}

function correctText(text) {
  const tokens = text.split(/([A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+)/g);
  const correctedTokens = [];
  const suggestions = [];

  tokens.forEach((token) => {
    if (!token.match(WORD_RE)) {
      correctedTokens.push(token);
      return;
    }
    const corrected = correctToken(token);
    correctedTokens.push(corrected);
    if (corrected !== token) {
      suggestions.push({
        original: token,
        corrected,
        explanation: "Corrección basada en el corpus de entrenamiento",
      });
    }
  });

  return { corrected_text: correctedTokens.join(""), suggestions };
}

app.post("/correct", (req, res) => {
  const { text } = req.body;
  if (typeof text !== "string") {
    return res.status(400).json({ error: "El campo 'text' es obligatorio" });
  }

  const result = correctText(text);
  res.json(result);
});

app.get("/", (req, res) => {
  res.send("API del asistente de redacción está en línea.");
});

app.listen(port, "127.0.0.1", () => {
  console.log(`Backend iniciado en http://127.0.0.1:${port}`);
});
