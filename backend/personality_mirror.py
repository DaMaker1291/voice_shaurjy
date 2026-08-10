"""
Personality Mirror — learns the user's unique vocabulary, tone, sentence patterns,
common phrases, and communication style, then mirrors them back to create
a deeply personalized interaction that feels like talking to someone who truly
understands the user.
"""
import json
import re
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from typing import Optional

DB_DIR = Path(__file__).parent / "user_data"
MIRROR_DB = DB_DIR / "personality_mirror.db"


class PersonalityMirror:
    """Learns and mirrors user's unique communication fingerprint."""

    def __init__(self, user_id: str = "local", db_path: Optional[Path] = None):
        self.user_id = user_id
        self._db_path = db_path or MIRROR_DB
        self._local = threading.Lock()
        self._init_db()
        self._load()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS vocab (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    word TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE(user_id, word)
                );
                CREATE TABLE IF NOT EXISTS phrases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    phrase TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    context_hint TEXT DEFAULT '',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE(user_id, phrase)
                );
                CREATE TABLE IF NOT EXISTS sentence_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    avg_length REAL DEFAULT 10.0,
                    formality_score REAL DEFAULT 0.5,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE(user_id, pattern)
                );
                CREATE TABLE IF NOT EXISTS tone_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    avg_sentence_length REAL DEFAULT 15.0,
                    vocab_richness REAL DEFAULT 0.5,
                    formality REAL DEFAULT 0.5,
                    emotion_positive REAL DEFAULT 0.5,
                    emotion_negative REAL DEFAULT 0.1,
                    emotion_neutral REAL DEFAULT 0.4,
                    question_frequency REAL DEFAULT 0.1,
                    exclamation_frequency REAL DEFAULT 0.05,
                emoji_frequency REAL DEFAULT 0.0,
                    total_messages INTEGER DEFAULT 0,
                    last_updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS writing_style (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    style_feature TEXT NOT NULL,
                    value REAL DEFAULT 0.0,
                    samples TEXT DEFAULT '[]',
                    UNIQUE(user_id, style_feature)
                );
                CREATE INDEX IF NOT EXISTS idx_vocab_user ON vocab(user_id);
                CREATE INDEX IF NOT EXISTS idx_phrases_user ON phrases(user_id);
                CREATE INDEX IF NOT EXISTS idx_patterns_user ON sentence_patterns(user_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _load(self):
        conn = sqlite3.connect(str(self._db_path))
        try:
            row = conn.execute(
                "SELECT * FROM tone_profile WHERE user_id = ?", (self.user_id,)
            ).fetchone()
            if row:
                self._tone = {
                    "avg_sentence_length": row[1],
                    "vocab_richness": row[2],
                    "formality": row[3],
                    "emotion_positive": row[4],
                    "emotion_negative": row[5],
                    "emotion_neutral": row[6],
                    "question_frequency": row[7],
                    "exclamation_frequency": row[8],
                    "emoji_frequency": row[9],
                    "total_messages": row[10],
                }
            else:
                self._tone = {
                    "avg_sentence_length": 15.0,
                    "vocab_richness": 0.5,
                    "formality": 0.5,
                    "emotion_positive": 0.5,
                    "emotion_negative": 0.1,
                    "emotion_neutral": 0.4,
                    "question_frequency": 0.1,
                    "exclamation_frequency": 0.05,
                    "emoji_frequency": 0.0,
                    "total_messages": 0,
                }
                conn.execute(
                    "INSERT OR IGNORE INTO tone_profile (user_id, last_updated) VALUES (?, ?)",
                    (self.user_id, datetime.now().isoformat())
                )
                conn.commit()
        finally:
            conn.close()

    def observe_text(self, text: str):
        """Observe a piece of user text and update all profiles."""
        if not text or len(text.strip()) < 2:
            return
        with self._local:
            self._learn_vocab(text)
            self._learn_phrases(text)
            self._learn_sentence_patterns(text)
            self._update_tone_profile(text)
            self._learn_writing_style(text)

    def _learn_vocab(self, text: str):
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
        now = datetime.now().isoformat()
        conn = sqlite3.connect(str(self._db_path))
        try:
            for w in set(words):
                conn.execute(
                    """INSERT INTO vocab (user_id, word, frequency, first_seen, last_seen)
                       VALUES (?, ?, 1, ?, ?)
                       ON CONFLICT(user_id, word) DO UPDATE SET
                           frequency = frequency + 1,
                           last_seen = ?""",
                    (self.user_id, w.lower(), now, now, now)
                )
            conn.commit()
        finally:
            conn.close()

    def _learn_phrases(self, text: str):
        """Extract common bigrams and trigrams."""
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        now = datetime.now().isoformat()
        phrases = []
        for i in range(len(words) - 1):
            phrases.append(" ".join(words[i:i+2]))
        for i in range(len(words) - 2):
            phrases.append(" ".join(words[i:i+3]))

        conn = sqlite3.connect(str(self._db_path))
        try:
            for p in set(phrases):
                conn.execute(
                    """INSERT INTO phrases (user_id, phrase, frequency, first_seen, last_seen)
                       VALUES (?, ?, 1, ?, ?)
                       ON CONFLICT(user_id, phrase) DO UPDATE SET
                           frequency = frequency + 1,
                           last_seen = ?""",
                    (self.user_id, p, now, now, now)
                )
            conn.commit()
        finally:
            conn.close()

    def _learn_sentence_patterns(self, text: str):
        sentences = re.split(r'[.!?]+', text)
        now = datetime.now().isoformat()
        conn = sqlite3.connect(str(self._db_path))
        try:
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 5:
                    continue
                # Create pattern by replacing specific words with placeholders
                pattern = re.sub(r'\b[A-Z][a-z]+\b', '<NAME>', sent)
                pattern = re.sub(r'\b\d+\b', '<NUM>', pattern)
                pattern = re.sub(r'\b[a-zA-Z]{8,}\b', '<LONGWORD>', pattern)
                words = sent.split()
                avg_len = sum(len(w) for w in words) / max(len(words), 1)
                formal = self._calc_formality(sent)

                existing = conn.execute(
                    "SELECT frequency, avg_length, formality_score FROM sentence_patterns WHERE user_id=? AND pattern=?",
                    (self.user_id, pattern)
                ).fetchone()
                if existing:
                    new_freq = existing[0] + 1
                    new_avg = (existing[1] * existing[0] + avg_len) / new_freq
                    new_formal = (existing[2] * existing[0] + formal) / new_freq
                    conn.execute(
                        "UPDATE sentence_patterns SET frequency=?, avg_length=?, formality_score=?, last_seen=? WHERE user_id=? AND pattern=?",
                        (new_freq, new_avg, new_formal, now, self.user_id, pattern)
                    )
                else:
                    conn.execute(
                        "INSERT INTO sentence_patterns (user_id, pattern, frequency, avg_length, formality_score, first_seen, last_seen) VALUES (?, ?, 1, ?, ?, ?, ?)",
                        (self.user_id, pattern, avg_len, formal, now, now)
                    )
            conn.commit()
        finally:
            conn.close()

    def _calc_formality(self, text: str) -> float:
        text_lower = text.lower()
        formal_markers = ["please", "kindly", "would", "could", "shall", "however",
                          "therefore", "furthermore", "appreciate", "regards",
                          "sincerely", "respectfully", "nevertheless", "accordingly"]
        casual_markers = ["hey", "yo", "sup", "cool", "awesome", "lol", "idk",
                          "btw", "thx", "np", "gonna", "wanna", "gotta", "nah",
                          "yeah", "yep", "nope", "okay", "ok"]
        formal_count = sum(1 for m in formal_markers if m in text_lower)
        casual_count = sum(1 for m in casual_markers if m in text_lower)
        total = formal_count + casual_count
        if total == 0:
            return 0.5
        return formal_count / total

    def _update_tone_profile(self, text: str):
        sentences = re.split(r'[.!?]+', text)
        questions = sum(1 for s in sentences if '?' in s)
        exclamations = sum(1 for s in sentences if '!' in s)
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        words = text.split()
        avg_len = sum(len(w) for w in words) / max(len(words), 1) if words else 15

        # Sentiment
        positive_words = {"love", "amazing", "great", "awesome", "happy", "wonderful",
                          "beautiful", "excellent", "fantastic", "good", "nice", "best",
                          "perfect", "thanks", "thank", "yes", "yeah", "please"}
        negative_words = {"hate", "terrible", "awful", "bad", "worst", "horrible",
                          "sad", "angry", "frustrated", "annoyed", "no", "nope",
                          "not", "never", "wrong", "broken", "useless"}
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        total_sent = pos_count + neg_count or 1

        conn = sqlite3.connect(str(self._db_path))
        try:
            t = self._tone
            t["total_messages"] += 1
            n = t["total_messages"]
            # Running average
            t["avg_sentence_length"] = (t["avg_sentence_length"] * (n-1) + avg_len) / n
            t["question_frequency"] = (t["question_frequency"] * (n-1) + (questions / max(len(sentences), 1))) / n
            t["exclamation_frequency"] = (t["exclamation_frequency"] * (n-1) + (exclamations / max(len(sentences), 1))) / n
            t["emoji_frequency"] = (t["emoji_frequency"] * (n-1) + (emoji_count / max(len(words), 1))) / n
            t["emotion_positive"] = (t["emotion_positive"] * (n-1) + (pos_count / total_sent)) / n
            t["emotion_negative"] = (t["emotion_negative"] * (n-1) + (neg_count / total_sent)) / n
            t["emotion_neutral"] = max(0.0, 1.0 - t["emotion_positive"] - t["emotion_negative"])

            # Vocab richness: unique words / total words
            unique_words = len(set(w.lower() for w in words if len(w) > 2))
            t["vocab_richness"] = (t["vocab_richness"] * (n-1) + (unique_words / max(len(words), 1))) / n
            t["formality"] = (t["formality"] * (n-1) + self._calc_formality(text)) / n

            conn.execute(
                """UPDATE tone_profile SET
                   avg_sentence_length=?, vocab_richness=?, formality=?,
                   emotion_positive=?, emotion_negative=?, emotion_neutral=?,
                   question_frequency=?, exclamation_frequency=?, emoji_frequency=?,
                   total_messages=?, last_updated=?
                   WHERE user_id=?""",
                (t["avg_sentence_length"], t["vocab_richness"], t["formality"],
                 t["emotion_positive"], t["emotion_negative"], t["emotion_neutral"],
                 t["question_frequency"], t["exclamation_frequency"], t["emoji_frequency"],
                 t["total_messages"], datetime.now().isoformat(), self.user_id)
            )
            conn.commit()
        finally:
            conn.close()

    def _learn_writing_style(self, text: str):
        """Learn micro-style features like capitalization, punctuation patterns."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            features = {}
            # Capitalization style
            sentences = re.split(r'[.!?]+\s*', text)
            lower_starts = sum(1 for s in sentences if s and s[0].islower())
            if sentences:
                features["lowercase_sentence_start"] = lower_starts / len(sentences)

            # Punctuation spacing
            if re.search(r'\w+\s+\w+', text):
                features["uses_spaces_after_punctuation"] = 1.0

            # Contraction usage
            contractions = re.findall(r"\b\w+'(?:re|ve|ll|d|m|s|t)\b", text.lower())
            features["contraction_frequency"] = len(contractions) / max(len(text.split()), 1)

            # Abbreviation usage
            abbrevs = re.findall(r'\b[A-Z]{2,}\b', text)
            features["abbreviation_frequency"] = len(abbrevs) / max(len(text.split()), 1)

            # Em-dash / hyphen usage
            dashes = text.count("--") + text.count(" – ")
            features["dash_frequency"] = dashes / max(len(text.split()), 1)

            for feature, value in features.items():
                conn.execute(
                    """INSERT INTO writing_style (user_id, style_feature, value, samples, last_updated)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(user_id, style_feature) DO UPDATE SET
                           value = (value * 0.9 + ? * 0.1), samples = ?""",
                    (self.user_id, feature, value, json.dumps([text[:100]]),
                     datetime.now().isoformat(), value, json.dumps([text[:100]]))
                )
            conn.commit()
        finally:
            conn.close()

    def get_user_fingerprint(self) -> dict:
        """Return the complete user communication fingerprint."""
        t = self._tone
        conn = sqlite3.connect(str(self._db_path))
        try:
            top_words = conn.execute(
                "SELECT word, frequency FROM vocab WHERE user_id=? ORDER BY frequency DESC LIMIT 30",
                (self.user_id,)
            ).fetchall()
            top_phrases = conn.execute(
                "SELECT phrase, frequency FROM phrases WHERE user_id=? ORDER BY frequency DESC LIMIT 10",
                (self.user_id,)
            ).fetchall()
            top_patterns = conn.execute(
                "SELECT pattern, frequency FROM sentence_patterns WHERE user_id=? ORDER BY frequency DESC LIMIT 5",
                (self.user_id,)
            ).fetchall()
            style_features = conn.execute(
                "SELECT style_feature, value FROM writing_style WHERE user_id=?",
                (self.user_id,)
            ).fetchall()
        finally:
            conn.close()

        return {
            "tone": {
                "avg_sentence_length": round(t["avg_sentence_length"], 1),
                "vocab_richness": round(t["vocab_richness"], 2),
                "formality": round(t["formality"], 2),
                "emotion_balance": {
                    "positive": round(t["emotion_positive"], 2),
                    "negative": round(t["emotion_negative"], 2),
                    "neutral": round(t["emotion_neutral"], 2),
                },
                "question_frequency": round(t["question_frequency"], 3),
                "exclamation_frequency": round(t["exclamation_frequency"], 3),
                "emoji_frequency": round(t["emoji_frequency"], 3),
                "total_messages": t["total_messages"],
            },
            "top_vocab": [{"word": w[0], "freq": w[1]} for w in top_words[:15]],
            "top_phrases": [{"phrase": p[0], "freq": p[1]} for p in top_phrases[:5]],
            "common_patterns": [{"pattern": p[0], "freq": p[1]} for p in top_patterns[:3]],
            "style_features": {sf[0]: round(sf[1], 3) for sf in style_features},
        }

    def get_mirror_context(self) -> str:
        """Build a prompt context that tells the LLM how to mirror the user."""
        fp = self.get_user_fingerprint()
        t = fp["tone"]
        lines = ["\n===== USER PERSONALITY MIRROR ====="]

        # Tone description
        if t["formality"] < 0.3:
            lines.append("User communicates casually. Mirror with casual, friendly language.")
        elif t["formality"] > 0.7:
            lines.append("User communicates formally. Mirror with professional, polished language.")
        else:
            lines.append("User communicates in a balanced, neutral style.")

        if t["avg_sentence_length"] < 10:
            lines.append("User prefers very short, concise sentences.")
        elif t["avg_sentence_length"] > 25:
            lines.append("User tends to write longer, detailed sentences.")

        if t["emotion_balance"]["positive"] > 0.4:
            lines.append("User is generally positive and enthusiastic.")
        if t["emotion_balance"]["negative"] > 0.3:
            lines.append("User expresses frustration/dissatisfaction often — respond with empathy.")
        if t["question_frequency"] > 0.2:
            lines.append("User asks many questions — provide thorough, informative answers.")
        if t["exclamation_frequency"] > 0.1:
            lines.append("User is expressive — match their energy level.")
        if t["emoji_frequency"] > 0.02:
            lines.append("User uses emojis — feel free to use them appropriately.")

        if t["vocab_richness"] > 0.7:
            lines.append("User has a rich vocabulary — use varied, sophisticated language.")
        elif t["vocab_richness"] < 0.3:
            lines.append("User prefers simple, everyday language.")

        # Top phrases the user uses
        if fp["top_phrases"]:
            user_phrases = [p["phrase"] for p in fp["top_phrases"][:3]]
            lines.append(f"Common user phrases: {', '.join(user_phrases)}")

        # Style features
        sf = fp.get("style_features", {})
        if sf.get("lowercase_sentence_start", 0) > 0.3:
            lines.append("User often starts sentences lowercase — match this casual style.")

        lines.append("===== END USER PERSONALITY MIRROR =====")
        return "\n".join(lines)

    def get_mirror_instruction(self) -> str:
        """Get a concise instruction for the LLM on how to adapt its response."""
        fp = self.get_user_fingerprint()
        t = fp["tone"]
        instructions = ["Adapt your response to match the user's communication style:"]

        if t["formality"] < 0.3:
            instructions.append("- Use casual, conversational language")
        elif t["formality"] > 0.7:
            instructions.append("- Use formal, professional language")

        if t["avg_sentence_length"] < 12:
            instructions.append("- Keep sentences short and punchy")
        elif t["avg_sentence_length"] > 22:
            instructions.append("- Feel free to use detailed, flowing sentences")

        if t["vocab_richness"] < 0.3:
            instructions.append("- Use simple, everyday words")
        elif t["vocab_richness"] > 0.7:
            instructions.append("- Use sophisticated vocabulary")

        if t["emoji_frequency"] > 0.02:
            instructions.append("- Appropriate to use emojis")

        if t["exclamation_frequency"] > 0.1:
            instructions.append("- Match the user's energetic tone")

        return "\n".join(instructions)

    def get_stats(self) -> dict:
        fp = self.get_user_fingerprint()
        conn = sqlite3.connect(str(self._db_path))
        try:
            total_vocab = conn.execute(
                "SELECT COUNT(*) FROM vocab WHERE user_id=?", (self.user_id,)
            ).fetchone()[0]
            total_phrases = conn.execute(
                "SELECT COUNT(*) FROM phrases WHERE user_id=?", (self.user_id,)
            ).fetchone()[0]
            total_patterns = conn.execute(
                "SELECT COUNT(*) FROM sentence_patterns WHERE user_id=?", (self.user_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        return {
            "vocab_size": total_vocab,
            "phrases_learned": total_phrases,
            "patterns_learned": total_patterns,
            "messages_analyzed": fp["tone"]["total_messages"],
            "tone": fp["tone"],
        }


# ── Singleton ──────────────────────────────────────────────────────
_mirror_store: dict[str, PersonalityMirror] = {}

def get_mirror(user_id: str = "local") -> PersonalityMirror:
    if user_id not in _mirror_store:
        _mirror_store[user_id] = PersonalityMirror(user_id)
    return _mirror_store[user_id]