"""
JARVIS Phase 2 — RNN/LSTM Behavior Learning Engine
====================================================
Temporal sequence learning system that:
  - Learns user command sequences with LSTM
  - Predicts next likely commands
  - Detects daily routine patterns
  - Models session behavior
  - Predicts app launches, work schedules, repeated workflows

Architecture:
    Input sequence of N commands (encoded as integers)
    → Embedding layer
    → LSTM/GRU layers (stacked)
    → Linear head
    → Predicted next command distribution

Usage:
    from core.phase2.rnn_engine import BehaviorRNN
    rnn = BehaviorRNN()
    rnn.record_event("open_vscode")
    rnn.record_event("ask_ai_question")
    pred = rnn.predict_next()   # → {"command": "search_web", "confidence": 0.82}
    rnn.train_on_history()
"""

import asyncio
import json
import logging
import math
import sqlite3
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("jarvis.phase2.rnn_engine")

ROOT     = Path(__file__).resolve().parent.parent.parent
DB_DIR   = ROOT / "database"
MODELS   = ROOT / "models"
DB_DIR.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

BEHAVIOR_DB   = DB_DIR / "behavior.db"
RNN_MODEL_PATH = MODELS / "behavior_rnn.pth"

SEQ_LEN       = 20   # context window for prediction
MIN_VOCAB     = 3    # minimum unique events before training
MIN_SEQUENCES = 10   # minimum sequences before first train


# ─── Event Database ─────────────────────────────────────────────────────────────
def _init_behavior_db(db_path: Path = BEHAVIOR_DB):
    with sqlite3.connect(db_path) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event     TEXT NOT NULL,
            context   TEXT DEFAULT '',
            hour      INTEGER,
            weekday   INTEGER
        );
        CREATE TABLE IF NOT EXISTS sequences (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence  TEXT NOT NULL,
            created   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vocab (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
        """)


# ─── Vocabulary ─────────────────────────────────────────────────────────────────
class Vocabulary:
    """Maps event strings ↔ integer tokens. Thread-safe."""

    PAD = 0
    UNK = 1
    EOS = 2
    _SPECIALS = 3

    def __init__(self, db_path: Path = BEHAVIOR_DB):
        self.db_path = db_path
        self._lock   = threading.Lock()
        self._token2id: Dict[str, int] = {"<PAD>": 0, "<UNK>": 1, "<EOS>": 2}
        self._id2token: Dict[int, str] = {0: "<PAD>", 1: "<UNK>", 2: "<EOS>"}
        self._load()

    def _load(self):
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute("SELECT id, token FROM vocab ORDER BY id").fetchall()
            for row_id, token in rows:
                idx = row_id + self._SPECIALS - 1
                self._token2id[token] = idx
                self._id2token[idx]   = token
        except Exception:
            pass

    def add(self, token: str) -> int:
        with self._lock:
            if token in self._token2id:
                return self._token2id[token]
            try:
                with sqlite3.connect(self.db_path) as c:
                    c.execute("INSERT OR IGNORE INTO vocab (token) VALUES (?)", (token,))
                    row_id = c.execute("SELECT id FROM vocab WHERE token=?", (token,)).fetchone()[0]
                idx = row_id + self._SPECIALS - 1
                self._token2id[token] = idx
                self._id2token[idx]   = token
                return idx
            except Exception as e:
                logger.error(f"[RNN] Vocab add error: {e}")
                return self.UNK

    def encode(self, token: str) -> int:
        return self._token2id.get(token, self.UNK)

    def decode(self, idx: int) -> str:
        return self._id2token.get(idx, "<UNK>")

    def __len__(self):
        return len(self._token2id)


# ─── LSTM Model ─────────────────────────────────────────────────────────────────
def _build_rnn_model(vocab_size: int, embed_dim: int = 64, hidden: int = 128, layers: int = 2):
    """Build a small LSTM-based sequence predictor."""
    try:
        import torch.nn as nn

        class BehaviorLSTM(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed   = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
                self.lstm    = nn.LSTM(embed_dim, hidden, num_layers=layers,
                                       batch_first=True, dropout=0.3 if layers > 1 else 0.0)
                self.dropout = nn.Dropout(0.3)
                self.head    = nn.Linear(hidden, vocab_size)

            def forward(self, x):
                emb = self.dropout(self.embed(x))
                out, _ = self.lstm(emb)
                logits = self.head(self.dropout(out[:, -1, :]))
                return logits

        return BehaviorLSTM()
    except ImportError:
        return None


# ─── Behavior RNN ────────────────────────────────────────────────────────────────
class BehaviorRNN:
    """
    LSTM-based user behavior learner and predictor.
    Learns from JARVIS command history stored in SQLite.
    """

    def __init__(self, config: dict = None, db_path: Path = BEHAVIOR_DB):
        self.config       = config or {}
        self.db_path      = db_path
        self.vocab        = Vocabulary(db_path)
        self._model       = None
        self._device      = "cpu"
        self._lock        = threading.Lock()
        self._recent      = deque(maxlen=SEQ_LEN * 2)  # live session buffer
        self._is_training = False

        _init_behavior_db(db_path)
        self._detect_device()

    def _detect_device(self):
        try:
            import torch
            if torch.cuda.is_available():
                self._device = "cuda"
        except ImportError:
            pass

    # ── Event Recording ────────────────────────────────────────────────────────
    def record_event(self, event: str, context: str = ""):
        """
        Record a user interaction event.
        Call this whenever JARVIS processes a command.
        """
        now = datetime.now()
        self.vocab.add(event)
        self._recent.append(event)

        try:
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    "INSERT INTO events (timestamp, event, context, hour, weekday) VALUES (?,?,?,?,?)",
                    (now.isoformat(), event, context, now.hour, now.weekday()),
                )
        except Exception as e:
            logger.error(f"[RNN] Event record error: {e}")

    def record_command(self, command: str, result_type: str = ""):
        """Convenience wrapper: normalizes a command string and records it."""
        # Normalize: lowercase, replace spaces with underscores
        event = command.lower().strip().replace(" ", "_")[:64]
        self.record_event(event, context=result_type)

    # ── Prediction ─────────────────────────────────────────────────────────────
    def predict_next(self, context_events: Optional[List[str]] = None, top_k: int = 5) -> Dict:
        """
        Predict the most likely next event(s).

        Args:
            context_events: Recent events to use as context.
                            Defaults to the last SEQ_LEN events in session buffer.
            top_k: Number of predictions to return.

        Returns:
            dict with "predictions" list [{command, confidence}, ...]
        """
        # Fallback: frequency-based prediction if model not trained yet
        if self._model is None:
            return self._frequency_predict(context_events, top_k)

        try:
            import torch

            ctx = list(context_events or self._recent)
            if not ctx:
                return self._frequency_predict(None, top_k)

            ctx = ctx[-SEQ_LEN:]
            ids = [self.vocab.encode(e) for e in ctx]
            # Pad to SEQ_LEN
            padded = [0] * (SEQ_LEN - len(ids)) + ids

            tensor = torch.tensor([padded], dtype=torch.long, device=self._device)

            self._model.eval()
            with torch.no_grad():
                logits = self._model(tensor)[0]
                probs  = torch.softmax(logits, dim=0)
                top    = torch.topk(probs, min(top_k, len(self.vocab)))

            results = []
            for prob, idx in zip(top.values.cpu().numpy(), top.indices.cpu().numpy()):
                token = self.vocab.decode(int(idx))
                if token not in ("<PAD>", "<UNK>", "<EOS>"):
                    results.append({
                        "command":    token,
                        "confidence": round(float(prob), 3),
                    })

            return {
                "predictions":  results,
                "top_command":  results[0]["command"] if results else None,
                "method":       "lstm",
                "context_len":  len(ctx),
            }
        except Exception as e:
            logger.error(f"[RNN] Prediction error: {e}")
            return self._frequency_predict(context_events, top_k)

    def _frequency_predict(self, context: Optional[List[str]], top_k: int) -> Dict:
        """Simple n-gram frequency fallback when LSTM not available."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT event FROM events ORDER BY id DESC LIMIT 500"
                ).fetchall()
            events = [r[0] for r in rows]
            if len(events) < 2:
                return {"predictions": [], "method": "insufficient_data"}

            # Bigram: what usually follows the last event?
            last = (context or list(self._recent) or [""])[-1]
            bigrams = defaultdict(Counter)
            for a, b in zip(events[1:], events[:-1]):
                bigrams[b][a] += 1

            next_counts = bigrams.get(last, Counter())
            if not next_counts:
                # Fall back to global frequency
                counter = Counter(events)
            else:
                counter = next_counts

            top = counter.most_common(top_k)
            total = sum(c for _, c in top)
            results = [
                {"command": cmd, "confidence": round(cnt / max(total, 1), 3)}
                for cmd, cnt in top
                if cmd not in ("<PAD>", "<UNK>", "<EOS>")
            ]
            return {
                "predictions":  results,
                "top_command":  results[0]["command"] if results else None,
                "method":       "frequency_bigram",
                "context":      last,
            }
        except Exception as e:
            return {"predictions": [], "error": str(e)}

    # ── Training ───────────────────────────────────────────────────────────────
    async def train_on_history(
        self,
        epochs: int = 30,
        batch_size: int = 64,
        seq_len: int = SEQ_LEN,
        progress_cb=None,
    ) -> Dict:
        """
        Train LSTM on recorded event history.
        Should be called periodically (e.g., every 30 min or 1000 events).
        """
        if self._is_training:
            return {"status": "already_training"}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._train_sync, epochs, batch_size, seq_len, progress_cb
        )

    def _train_sync(self, epochs, batch_size, seq_len, progress_cb) -> Dict:
        self._is_training = True
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset

            # Load event history
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute("SELECT event FROM events ORDER BY id").fetchall()
            events = [r[0] for r in rows]

            if len(events) < MIN_SEQUENCES + seq_len:
                return {
                    "status": "insufficient_data",
                    "events": len(events),
                    "needed": MIN_SEQUENCES + seq_len,
                }

            # Encode
            ids = [self.vocab.encode(e) for e in events]
            vocab_size = len(self.vocab)

            if vocab_size < MIN_VOCAB + Vocabulary._SPECIALS:
                return {"status": "vocab_too_small", "vocab_size": vocab_size}

            # Build sequences
            X, Y = [], []
            for i in range(len(ids) - seq_len):
                X.append(ids[i : i + seq_len])
                Y.append(ids[i + seq_len])

            X = torch.tensor(X, dtype=torch.long)
            Y = torch.tensor(Y, dtype=torch.long)

            dataset    = TensorDataset(X, Y)
            split      = max(1, int(len(dataset) * 0.1))
            train_ds   = torch.utils.data.Subset(dataset, range(len(dataset) - split))
            val_ds     = torch.utils.data.Subset(dataset, range(len(dataset) - split, len(dataset)))
            train_ld   = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
            val_ld     = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)

            device = torch.device(self._device)
            model  = _build_rnn_model(vocab_size)
            if model is None:
                return {"error": "PyTorch not installed"}

            model  = model.to(device)
            optim_ = optim.Adam(model.parameters(), lr=1e-3)
            sched  = optim.lr_scheduler.ReduceLROnPlateau(optim_, patience=3, factor=0.5)
            crit   = nn.CrossEntropyLoss(ignore_index=Vocabulary.PAD)

            history = []
            best_loss = float("inf")

            for epoch in range(epochs):
                model.train()
                total_loss = 0.0
                for xb, yb in train_ld:
                    xb, yb = xb.to(device), yb.to(device)
                    optim_.zero_grad()
                    logits = model(xb)
                    loss   = crit(logits, yb)
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optim_.step()
                    total_loss += loss.item()

                model.eval()
                val_loss = 0.0
                correct  = 0
                total    = 0
                with torch.no_grad():
                    for xb, yb in val_ld:
                        xb, yb = xb.to(device), yb.to(device)
                        logits = model(xb)
                        val_loss += crit(logits, yb).item()
                        preds = logits.argmax(dim=1)
                        correct += (preds == yb).sum().item()
                        total   += yb.size(0)

                avg_train = total_loss / max(len(train_ld), 1)
                avg_val   = val_loss / max(len(val_ld), 1)
                acc       = 100.0 * correct / max(total, 1)
                sched.step(avg_val)

                ep_rec = {"epoch": epoch+1, "train_loss": round(avg_train, 4),
                          "val_loss": round(avg_val, 4), "accuracy": round(acc, 2)}
                history.append(ep_rec)
                logger.info(f"[RNN] Epoch {epoch+1}/{epochs} train_loss={avg_train:.4f} "
                            f"val_loss={avg_val:.4f} acc={acc:.1f}%")

                if avg_val < best_loss:
                    best_loss = avg_val
                    torch.save({
                        "model_state": model.state_dict(),
                        "vocab_size":  vocab_size,
                        "seq_len":     seq_len,
                        "epoch":       epoch + 1,
                        "best_loss":   best_loss,
                        "history":     history,
                    }, RNN_MODEL_PATH)

                if progress_cb:
                    try:
                        progress_cb(ep_rec)
                    except Exception:
                        pass

            # Load best weights into live model
            self._load_model()
            return {
                "status":     "trained",
                "epochs":     epochs,
                "events":     len(events),
                "vocab_size": vocab_size,
                "best_loss":  round(best_loss, 4),
                "history":    history,
            }
        except Exception as e:
            logger.error(f"[RNN] Training error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
        finally:
            self._is_training = False

    def _load_model(self):
        """Load saved LSTM weights into memory."""
        if not RNN_MODEL_PATH.exists():
            return
        try:
            import torch
            ckpt       = torch.load(RNN_MODEL_PATH, map_location=self._device)
            vocab_size = ckpt["vocab_size"]
            model      = _build_rnn_model(vocab_size)
            model.load_state_dict(ckpt["model_state"])
            model.eval().to(torch.device(self._device))
            with self._lock:
                self._model = model
            logger.info(f"[RNN] Model loaded (vocab={vocab_size}, device={self._device})")
        except Exception as e:
            logger.error(f"[RNN] Model load failed: {e}")

    def load_if_exists(self):
        """Load model from disk if checkpoint exists."""
        if RNN_MODEL_PATH.exists():
            self._load_model()

    # ── Routine Analysis ───────────────────────────────────────────────────────
    def get_routine_patterns(self) -> Dict:
        """
        Analyze recorded events to extract user routine patterns.
        Returns hour-of-day distributions and top commands per time slot.
        """
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT event, hour, weekday FROM events ORDER BY id DESC LIMIT 2000"
                ).fetchall()

            if not rows:
                return {"patterns": {}, "message": "No data yet"}

            by_hour    = defaultdict(Counter)
            by_weekday = defaultdict(Counter)
            global_ctr = Counter()

            for event, hour, weekday in rows:
                by_hour[hour][event]       += 1
                by_weekday[weekday][event] += 1
                global_ctr[event]          += 1

            # Summarize top event per hour
            hour_summary = {}
            for hour in range(24):
                top = by_hour[hour].most_common(3)
                if top:
                    hour_summary[f"{hour:02d}:00"] = [
                        {"command": cmd, "count": cnt} for cmd, cnt in top
                    ]

            weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            weekday_summary = {
                weekday_names[wd]: [
                    {"command": cmd, "count": cnt}
                    for cmd, cnt in by_weekday[wd].most_common(5)
                ]
                for wd in range(7)
                if by_weekday[wd]
            }

            return {
                "total_events":    len(rows),
                "unique_commands": len(global_ctr),
                "top_commands":    [{"command": c, "count": n} for c, n in global_ctr.most_common(10)],
                "by_hour":         hour_summary,
                "by_weekday":      weekday_summary,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_session_summary(self) -> Dict:
        """Summary of current session (since app start)."""
        session_events = list(self._recent)
        ctr = Counter(session_events)
        return {
            "session_events":  len(session_events),
            "unique_commands": len(ctr),
            "top_commands":    [{"command": c, "count": n} for c, n in ctr.most_common(5)],
            "last_events":     session_events[-10:],
            "model_ready":     self._model is not None,
        }

    def predict_now(self) -> Dict:
        """
        Context-aware prediction: uses current time to suggest likely actions.
        Combines LSTM prediction with time-based heuristics.
        """
        now  = datetime.now()
        lstm = self.predict_next(top_k=3)

        # Time-based hint
        hour_hint = ""
        if 8 <= now.hour <= 10:
            hour_hint = "morning_start"
        elif 12 <= now.hour <= 14:
            hour_hint = "lunch_break"
        elif 18 <= now.hour <= 22:
            hour_hint = "evening_session"

        return {
            "lstm_predictions": lstm.get("predictions", []),
            "top_command":      lstm.get("top_command"),
            "hour_hint":        hour_hint,
            "current_time":     now.strftime("%H:%M"),
            "weekday":          now.strftime("%A"),
        }

    def get_stats(self) -> Dict:
        """Database statistics."""
        try:
            with sqlite3.connect(self.db_path) as c:
                total   = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                unique  = c.execute("SELECT COUNT(DISTINCT event) FROM events").fetchone()[0]
                oldest  = c.execute("SELECT MIN(timestamp) FROM events").fetchone()[0]
                newest  = c.execute("SELECT MAX(timestamp) FROM events").fetchone()[0]
            return {
                "total_events":    total,
                "unique_commands": unique,
                "oldest":          oldest,
                "newest":          newest,
                "vocab_size":      len(self.vocab),
                "model_trained":   RNN_MODEL_PATH.exists(),
                "session_events":  len(self._recent),
            }
        except Exception as e:
            return {"error": str(e)}
