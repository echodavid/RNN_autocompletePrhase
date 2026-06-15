const API_URL = "http://127.0.0.1:8001/correct";
const inputText = document.getElementById("inputText");
const ghostText = document.getElementById("ghostText");

let latestNextSuggestions = [];
let selectedSuggestionIndex = 0;
let debounceTimer = null;
const DEBOUNCE_MS = 220;

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderGhostText() {
  const text = inputText.value;
  if (!text) {
    ghostText.innerHTML = "";
    return;
  }

  const active = latestNextSuggestions[selectedSuggestionIndex] || latestNextSuggestions[0] || "";
  const boundary = getCurrentWordBoundary();

  if (active && boundary) {
    const beforeWord = text.slice(0, boundary.start);
    const currentWord = boundary.word;
    const afterCursor = text.slice(boundary.end);
    const lowerActive = active.toLowerCase();
    const lowerCurrent = currentWord.toLowerCase();

    if (lowerActive.startsWith(lowerCurrent)) {
      let suggestion = active.slice(currentWord.length);
      const displaySuggestion = suggestion.replace(/^\s+/, "");
      ghostText.innerHTML =
        `<span class="ghost-typed">${escapeHtml(beforeWord + currentWord)}</span>` +
        `<span class="ghost-suggestion">${escapeHtml(displaySuggestion)}</span>` +
        `<span class="ghost-typed">${escapeHtml(afterCursor)}</span>`;
      return;
    }
  }

  if (active && active.toLowerCase().startsWith(text.toLowerCase())) {
    let suggestion = active.slice(text.length);
    const displaySuggestion = suggestion.replace(/^\s+/, "");
    ghostText.innerHTML =
      `<span class="ghost-typed">${escapeHtml(text)}</span>` +
      `<span class="ghost-suggestion">${escapeHtml(displaySuggestion)}</span>`;
    return;
  }

  ghostText.innerHTML = `<span class="ghost-typed">${escapeHtml(text)}</span>`;
}

async function fetchCorrection(text) {
  if (!text) {
    latestNextSuggestions = [];
    renderGhostText();
    return;
  }

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      throw new Error(`Error en la API: ${response.status}`);
    }

    const data = await response.json();
    latestNextSuggestions = data.next_suggestions || [];
    selectedSuggestionIndex = 0;
    renderGhostText();
  } catch (error) {
    latestNextSuggestions = [];
    renderGhostText();
  }
}

function scheduleCorrection() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    fetchCorrection(inputText.value);
  }, DEBOUNCE_MS);
  renderGhostText();
}

function getCurrentWordBoundary() {
  const pos = inputText.selectionStart;
  const text = inputText.value;
  const before = text.slice(0, pos);
  const match = before.match(/([A-Za-zÁÉÍÓÚáéíóúÜüÑñ]+)$/);
  if (!match) return null;
  return {
    word: match[1],
    start: pos - match[1].length,
    end: pos,
  };
}

function applySuggestion(suggestion) {
  const boundary = getCurrentWordBoundary();
  if (!boundary) return;

  const fullText = inputText.value;
  const beforeCursor = fullText.slice(0, boundary.end);
  const afterCursor = fullText.slice(boundary.end);
  const beforeWords = beforeCursor.trimEnd().split(/\s+/);
  const suggestionWords = suggestion.trim().split(/\s+/);

  let overlap = 0;
  const maxOverlap = Math.min(beforeWords.length, suggestionWords.length);
  for (let k = maxOverlap; k > 0; k -= 1) {
    const tail = beforeWords.slice(-k).join(" ");
    const head = suggestionWords.slice(0, k).join(" ");
    if (tail.toLowerCase() === head.toLowerCase()) {
      overlap = k;
      break;
    }
  }

  let newText;
  if (overlap > 0) {
    const prefix = beforeWords.slice(0, beforeWords.length - overlap).join(" ");
    const separator = prefix.length > 0 ? " " : "";
    newText = prefix + separator + suggestion + afterCursor;
  } else {
    const prefix = fullText.slice(0, boundary.start);
    newText = prefix + suggestion + afterCursor;
  }

  inputText.value = newText;
  const cursorPosition = newText.length - afterCursor.length;
  inputText.setSelectionRange(cursorPosition, cursorPosition);
  fetchCorrection(inputText.value);
}


inputText.addEventListener("input", scheduleCorrection);
inputText.addEventListener("blur", () => fetchCorrection(inputText.value));
inputText.addEventListener("scroll", () => {
  ghostText.scrollTop = inputText.scrollTop;
  ghostText.scrollLeft = inputText.scrollLeft;
});

inputText.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    if (latestNextSuggestions.length === 0 || selectedSuggestionIndex < 0) return;
    event.preventDefault();

    const suggestion = latestNextSuggestions[selectedSuggestionIndex];
    applySuggestion(suggestion);
    return;
  }

  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    if (latestNextSuggestions.length === 0) return;
    event.preventDefault();

    const delta = event.key === "ArrowDown" ? 1 : -1;
    selectedSuggestionIndex = Math.min(
      Math.max(selectedSuggestionIndex + delta, 0),
      latestNextSuggestions.length - 1
    );
    renderGhostText();
  }
});

fetchCorrection(inputText.value);
