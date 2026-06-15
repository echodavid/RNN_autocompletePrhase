import argparse
import sys
import unicodedata
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import IterableDataset, DataLoader

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATASET_DIR = DATA_DIR / "dataset"
CORPUS_PATH = DATA_DIR / "spanish_corpus.txt"
MODEL_PATH = BASE_DIR / "saved_model.pt"

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


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fix_mojibake(text: str) -> str:
    for bad, good in COMMON_MOJIBAKE.items():
        text = text.replace(bad, good)
    return text


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


class TextStreamDataset(IterableDataset):
    def __init__(self, files, char2idx, seq_len=32, step=4, max_chars=None):
        self.files = files
        self.char2idx = char2idx
        self.seq_len = seq_len
        self.step = step
        self.max_chars = max_chars

    def __iter__(self):
        buffer = ""
        total_chars = 0
        for path in self.files:
            text = read_file_text(path).lower()
            for line in text.splitlines(keepends=True):
                buffer += line
                while len(buffer) >= self.seq_len + 1:
                    x = [self.char2idx.get(ch, 0) for ch in buffer[: self.seq_len]]
                    y = [self.char2idx.get(ch, 0) for ch in buffer[1 : self.seq_len + 1]]
                    yield torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long)
                    buffer = buffer[self.step :]
                    total_chars += self.step
                    if self.max_chars and total_chars >= self.max_chars:
                        return
            buffer = buffer[-self.seq_len :]
            if self.max_chars and total_chars >= self.max_chars:
                return


class SimpleRNN(nn.Module):
    def __init__(self, vocab_size, embed_dim=128, hidden_dim=256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.rnn = nn.GRU(embed_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        x = self.embedding(x)
        output, hidden = self.rnn(x, hidden)
        return self.fc(output), hidden


def set_memory_limit(max_gb):
    if max_gb is None:
        return

    if sys.platform.startswith("darwin"):
        print("Atención: macOS puede no respetar RLIMIT_AS. Ajusta batch-size/seq-len para reducir RAM.")

    try:
        import resource

        bytes_limit = int(max_gb * 1024**3)
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard == resource.RLIM_INFINITY:
            new_soft = bytes_limit
        else:
            new_soft = min(bytes_limit, hard)
        resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))
        if hasattr(resource, "RLIMIT_DATA"):
            soft2, hard2 = resource.getrlimit(resource.RLIMIT_DATA)
            new_soft2 = min(bytes_limit, hard2) if hard2 != resource.RLIM_INFINITY else bytes_limit
            resource.setrlimit(resource.RLIMIT_DATA, (new_soft2, hard2))
        print(f"Límite de memoria configurado en {max_gb} GB (soft={new_soft})")
    except Exception as exc:
        print("No se pudo aplicar límite de memoria:", exc)


def get_text_files(max_files=None):
    files = []
    if DATASET_DIR.exists() and DATASET_DIR.is_dir():
        files = sorted(
            [p for p in DATASET_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store"]
        )
        if files:
            print(f"Encontrados {len(files)} archivos en {DATASET_DIR}")
    elif CORPUS_PATH.exists():
        files = [CORPUS_PATH]
    else:
        files = sorted(DATA_DIR.glob("*.txt"))

    if max_files and len(files) > max_files:
        print(f"Limitando a los primeros {max_files} archivos de los {len(files)} disponibles")
        files = files[:max_files]

    return files


def build_vocab(files, max_chars=None):
    vocab = set()
    total_chars = 0
    for path in files:
        text = read_file_text(path)
        for line in text.splitlines(keepends=True):
            vocab.update(line.lower())
            total_chars += len(line)
            if max_chars and total_chars >= max_chars:
                break
        if max_chars and total_chars >= max_chars:
            break

    if not vocab:
        vocab = {" ", "\n"}

    if "<unk>" not in vocab:
        vocab.add("<unk>")
    sorted_vocab = ["<unk>"] + sorted(c for c in vocab if c != "<unk>")
    return sorted_vocab


def split_files(files, validation_ratio):
    if len(files) < 2 or validation_ratio <= 0.0:
        return files, []
    split = max(1, int(len(files) * (1.0 - validation_ratio)))
    return files[:split], files[split:]


def parse_args():
    parser = argparse.ArgumentParser(description="Entrenamiento de asistente de redacción con corpus en data/dataset")
    parser.add_argument("--batch-size", type=int, default=8, help="Tamaño de batch para entrenamiento")
    parser.add_argument("--seq-len", type=int, default=32, help="Longitud de secuencia por muestra")
    parser.add_argument("--epochs", type=int, default=3, help="Número de épocas")
    parser.add_argument("--embed-dim", type=int, default=128, help="Dimensión de embedding")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Dimensión de la RNN")
    parser.add_argument("--step", type=int, default=8, help="Paso entre secuencias de entrenamiento para reducir muestras")
    parser.add_argument("--max-memory-gb", type=float, default=10.0, help="Límite de memoria virtual en GB (Unix) para evitar que muera el proceso")
    parser.add_argument("--validation-ratio", type=float, default=0.1, help="Porcentaje de archivos usados para validación")
    parser.add_argument("--max-files", type=int, default=10, help="Número máximo de archivos a usar del directorio data/dataset")
    parser.add_argument("--max-chars", type=int, default=150000, help="Número máximo total de caracteres a procesar para vocabulario y entrenamiento")
    return parser.parse_args()


def train(args):
    set_memory_limit(args.max_memory_gb)

    files = get_text_files(max_files=args.max_files)
    if not files:
        CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        sample_text = (
            "hola como estas\n"
            "hola como estás\n"
            "estoy bien gracias\n"
            "me gusta programar en python\n"
            "la ortografia es importante\n"
            "cómo estás hoy\n"
        )
        CORPUS_PATH.write_text(sample_text, encoding="utf-8")
        files = [CORPUS_PATH]
        print(f"No se encontró corpus. Se creó un ejemplo en {CORPUS_PATH}.")

    train_files, val_files = split_files(files, args.validation_ratio)
    if val_files:
        print(f"Entrenando con {len(train_files)} archivos y validando con {len(val_files)} archivos.")
    else:
        print(f"Entrenando con {len(train_files)} archivos.")

    vocab = build_vocab(train_files, max_chars=args.max_chars)
    char2idx = {ch: i for i, ch in enumerate(vocab)}
    print(f"Tamaño del vocabulario: {len(vocab)}")

    train_dataset = TextStreamDataset(
        train_files,
        char2idx,
        seq_len=args.seq_len,
        step=args.step,
        max_chars=args.max_chars,
    )
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, num_workers=0)

    val_loader = None
    if val_files:
        val_dataset = TextStreamDataset(
            val_files,
            char2idx,
            seq_len=args.seq_len,
            step=args.step,
            max_chars=args.max_chars,
        )
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Usando dispositivo: {device}")

    torch.set_num_threads(1)
    model = SimpleRNN(vocab_size=len(vocab), embed_dim=args.embed_dim, hidden_dim=args.hidden_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        train_batches = 0
        for batch_idx, (x, y) in enumerate(train_loader, start=1):
            x = x.to(device)
            y = y.to(device)
            optimizer.zero_grad()
            logits, _ = model(x)
            loss = criterion(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            train_batches += 1

            if batch_idx % 50 == 0:
                print(f"Epoch {epoch}, batch {batch_idx}, loss={loss.item():.4f}")

        if train_batches == 0:
            raise RuntimeError("No se generaron batches de entrenamiento. Verifica el corpus y seq_len.")

        print(f"Epoch {epoch}: train_loss={train_loss / train_batches:.4f} ({train_batches} batches)")

        if val_loader is not None:
            model.eval()
            val_loss = 0.0
            val_batches = 0
            with torch.no_grad():
                for x, y in val_loader:
                    x = x.to(device)
                    y = y.to(device)
                    logits, _ = model(x)
                    loss = criterion(logits.view(-1, logits.size(-1)), y.view(-1))
                    val_loss += loss.item()
                    val_batches += 1
            if val_batches > 0:
                print(f"Epoch {epoch}: val_loss={val_loss / val_batches:.4f} ({val_batches} batches)")

    torch.save({"model_state": model.state_dict(), "vocab": vocab}, MODEL_PATH)
    print(f"Modelo guardado en {MODEL_PATH}")


if __name__ == "__main__":
    args = parse_args()
    train(args)
