import ast
import json
import os
import random
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_NAME = "Mente Evolutiva Total"
VERSION = "8.1"

DB_PATH = Path(os.environ.get("MTE_DB_PATH", "mente_evolutiva_total_v8.db"))
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))

STOPWORDS = {
    "a", "al", "algo", "como", "con", "contra", "de", "del", "desde",
    "el", "ella", "en", "es", "esta", "este", "esto", "la", "las",
    "lo", "los", "me", "mi", "mis", "para", "por", "que", "se", "sin",
    "su", "sus", "te", "tu", "tus", "un", "una", "uno", "y", "ya"
}


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def now():
    return datetime.now().isoformat(timespec="seconds")


def human_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm(text):
    text = str(text).lower()
    text = re.sub(r"[^\wáéíóúüñ]+", " ", text, flags=re.UNICODE)
    return text.strip()


def tokens(text):
    return {
        t for t in norm(text).split()
        if t and t not in STOPWORDS and len(t) > 1
    }


def char_ngrams(text, n=3):
    s = norm(text).replace(" ", "_")
    if len(s) < n:
        return {s}
    return {s[i:i+n] for i in range(len(s) - n + 1)}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    na, nb = char_ngrams(a), char_ngrams(b)

    token_score = len(ta & tb) / max(1, len(ta | tb))
    ngram_score = len(na & nb) / max(1, len(na | nb))
    return 0.4 * token_score + 0.6 * ngram_score


@dataclass
class State:
    cycles: int = 0
    experience: float = 0.0
    emotional_age: float = 0.0
    curiosity: float = 0.7
    frustration: float = 0.1
    confidence: float = 0.5
    creativity: float = 0.5
    skepticism: float = 0.6
    trust: float = 0.5
    global_doubt: float = 0.5

    unanswered: int = 0
    contradictions: int = 0
    hypotheses: int = 0
    insights: int = 0
    causal_models: int = 0
    verifications: int = 0
    failed_verifications: int = 0

    predictions: int = 0
    prediction_errors: int = 0
    counterfactuals: int = 0
    decisions: int = 0
    regrets: int = 0
    regret_intensity: float = 0.0
    lessons_from_regret: int = 0
    decision_quality: float = 0.5

    python_mastery: float = 0.0
    python_exercises: int = 0
    python_correct: int = 0
    python_errors: int = 0
    python_topics_mastered: int = 0
    python_streak: int = 0
    python_level: float = 1.0


class DB:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30
        )
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def execute(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def fetchone(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def init_schema(self):
        schema = """
        CREATE TABLE IF NOT EXISTS state (
            id INTEGER PRIMARY KEY CHECK(id=1),
            data TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            definition TEXT DEFAULT '',
            mastery REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            source TEXT DEFAULT 'system',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS associations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            a TEXT NOT NULL,
            b TEXT NOT NULL,
            strength REAL DEFAULT 0.5,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS causal_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cause TEXT NOT NULL,
            effect TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            evidence INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(cause, effect)
        );

        CREATE TABLE IF NOT EXISTS hypotheses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction TEXT NOT NULL,
            expected TEXT DEFAULT '',
            actual TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            verified INTEGER DEFAULT 0,
            error REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS counterfactuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition TEXT NOT NULL,
            consequence TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context TEXT NOT NULL,
            choice TEXT NOT NULL,
            expected REAL DEFAULT 0.5,
            actual REAL DEFAULT 0.0,
            evaluated INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS regrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision TEXT NOT NULL,
            intensity REAL DEFAULT 0.5,
            lesson TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            resolved INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            progress REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS beliefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            belief TEXT UNIQUE NOT NULL,
            confidence REAL DEFAULT 0.5,
            evidence INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS python_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            prerequisites TEXT DEFAULT '',
            mastery REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS python_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            difficulty INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS python_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            prompt TEXT NOT NULL,
            expected_code TEXT NOT NULL,
            explanation TEXT NOT NULL,
            difficulty INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS python_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            correct INTEGER DEFAULT 0,
            similarity REAL DEFAULT 0.0,
            error TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
        with self.lock:
            self.conn.executescript(schema)
            self.conn.commit()


class Mind:
    def __init__(self, db):
        self.db = db
        self.state = self.load_state()
        self.bootstrap()

    def load_state(self):
        row = self.db.fetchone("SELECT data FROM state WHERE id=1")
        if not row:
            state = State()
            self.db.execute(
                "INSERT INTO state(id,data) VALUES(1,?)",
                (json.dumps(asdict(state), ensure_ascii=False),)
            )
            return state

        data = json.loads(row["data"])
        defaults = asdict(State())
        defaults.update(data)
        return State(**defaults)

    def save_state(self):
        self.db.execute(
            "INSERT OR REPLACE INTO state(id,data) VALUES(1,?)",
            (json.dumps(asdict(self.state), ensure_ascii=False),)
        )

    def event(self, kind, data):
        self.db.execute(
            "INSERT INTO events(kind,data,created_at) VALUES(?,?,?)",
            (kind, json.dumps(data, ensure_ascii=False), now())
        )

    def remember(self, content, importance=0.5, source="system"):
        self.db.execute(
            "INSERT INTO memories(content,importance,source,created_at) "
            "VALUES(?,?,?,?)",
            (content, clamp(importance), source, now())
        )

    def recall(self, query, limit=8):
        rows = self.db.fetchall(
            "SELECT * FROM memories ORDER BY id DESC LIMIT 300"
        )
        scored = []
        for row in rows:
            score = similarity(query, row["content"])
            score += 0.15 * row["importance"]
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": r["content"],
                "importance": r["importance"],
                "source": r["source"],
                "score": round(s, 3)
            }
            for s, r in scored[:limit]
            if s > 0.05
        ]

    def bootstrap(self):
        concepts = [
            ("existencia", "hecho de ser o estar"),
            ("duda", "estado que evita aceptar una idea sin suficiente evidencia"),
            ("aprendizaje", "cambio relativamente estable producido por experiencia"),
            ("causalidad", "relación en la que un factor contribuye a producir otro"),
            ("hipótesis", "explicación provisional que puede ponerse a prueba"),
            ("predicción", "expectativa explícita sobre un resultado futuro"),
            ("error", "diferencia entre lo esperado y lo observado"),
            ("contrafactual", "razonamiento sobre lo que podría haber ocurrido bajo otra condición"),
            ("arrepentimiento", "señal de aprendizaje sobre una decisión pasada"),
            ("decisión", "elección entre alternativas bajo incertidumbre"),
        ]
        for name, definition in concepts:
            self.db.execute(
                "INSERT OR IGNORE INTO concepts(name,definition,mastery,created_at) "
                "VALUES(?,?,?,?)",
                (name, definition, 0.2, now())
            )

        goals = [
            "Aprender",
            "Reducir incertidumbre",
            "Mejorar predicción",
            "Evitar errores repetidos",
            "Aprender Python"
        ]
        for goal in goals:
            self.db.execute(
                "INSERT OR IGNORE INTO goals(name,progress,created_at) "
                "VALUES(?,?,?)",
                (goal, 0.0, now())
            )

        topics = [
            ("sintaxis", "Estructura básica de Python", "", 1),
            ("variables", "Variables y asignación", "sintaxis", 1),
            ("tipos", "Tipos de datos básicos", "variables", 1),
            ("operadores", "Operadores y expresiones", "tipos", 1),
            ("condicionales", "if, elif y else", "operadores", 1),
            ("bucles", "for y while", "condicionales", 2),
            ("funciones", "Definición y uso de funciones", "variables", 2),
            ("listas", "Listas y operaciones", "tipos", 2),
            ("tuplas", "Tuplas y desempaquetado", "listas", 2),
            ("diccionarios", "Diccionarios", "tipos", 2),
            ("sets", "Conjuntos", "tipos", 2),
            ("strings", "Cadenas de texto", "tipos", 2),
            ("excepciones", "Manejo de errores", "condicionales", 3),
            ("archivos", "Lectura y escritura de archivos", "strings", 3),
            ("modulos", "Módulos e imports", "funciones", 3),
            ("poo", "Programación orientada a objetos", "funciones,tipos", 4),
            ("comprehensions", "Comprensiones", "listas,bucles", 4),
            ("iteradores", "Iteradores y generadores", "bucles,funciones", 5),
            ("decoradores", "Decoradores", "funciones", 5),
            ("testing", "Pruebas automatizadas", "funciones,excepciones", 5),
            ("sqlite", "SQLite desde Python", "funciones,archivos", 5),
            ("stdlib", "Biblioteca estándar", "modulos", 4),
        ]
        for name, desc, prereq, difficulty in topics:
            self.db.execute(
                "INSERT OR IGNORE INTO python_topics"
                "(name,description,prerequisites,mastery) VALUES(?,?,?,?)",
                (name, desc, prereq, 0.0)
            )

        self.seed_python_content()

    def seed_python_content(self):
        lessons = [
            (
                "sintaxis",
                "Primera estructura",
                "Python usa indentación para organizar bloques. "
                "Una instrucción simple puede escribirse como print('Hola').",
                1
            ),
            (
                "variables",
                "Variables",
                "Una variable se crea asignando un valor: nombre = 'Ana'. "
                "No necesitas declarar el tipo por separado.",
                1
            ),
            (
                "condicionales",
                "Condicionales",
                "Usa if para ejecutar código cuando una condición es verdadera. "
                "Puedes añadir elif y else.",
                1
            ),
            (
                "bucles",
                "Bucles",
                "for recorre elementos de una colección. while repite mientras "
                "una condición sea verdadera.",
                2
            ),
            (
                "funciones",
                "Funciones",
                "Una función se define con def. Puede recibir parámetros y "
                "devolver un valor mediante return.",
                2
            ),
            (
                "listas",
                "Listas",
                "Las listas son colecciones ordenadas y mutables. "
                "Ejemplo: numeros = [1, 2, 3].",
                2
            ),
            (
                "diccionarios",
                "Diccionarios",
                "Un diccionario relaciona claves con valores. "
                "Ejemplo: persona = {'nombre': 'Ana'}.",
                2
            ),
            (
                "excepciones",
                "Excepciones",
                "try/except permite manejar errores sin detener necesariamente "
                "todo el programa.",
                3
            ),
            (
                "sqlite",
                "SQLite",
                "El módulo sqlite3 permite trabajar con una base SQLite "
                "sin instalar una base de datos externa.",
                5
            ),
        ]
        for topic, title, content, difficulty in lessons:
            exists = self.db.fetchone(
                "SELECT id FROM python_lessons WHERE topic=? AND title=?",
                (topic, title)
            )
            if not exists:
                self.db.execute(
                    "INSERT INTO python_lessons"
                    "(topic,title,content,difficulty) VALUES(?,?,?,?)",
                    (topic, title, content, difficulty)
                )

        exercises = [
            (
                "sintaxis",
                "Escribe código que muestre Hola.",
                "print('Hola')",
                "Usa print() para mostrar texto.",
                1
            ),
            (
                "variables",
                "Crea una variable llamada edad con valor 20.",
                "edad = 20",
                "La asignación usa el signo =.",
                1
            ),
            (
                "condicionales",
                "Crea un if que muestre 'adulto' si edad >= 18.",
                "if edad >= 18:\n    print('adulto')",
                "La condición se escribe después de if y el bloque debe estar indentado.",
                1
            ),
            (
                "bucles",
                "Recorre [1, 2, 3] e imprime cada número.",
                "for numero in [1, 2, 3]:\n    print(numero)",
                "for toma cada elemento de la lista uno por uno.",
                2
            ),
            (
                "funciones",
                "Define una función suma(a, b) que devuelva a + b.",
                "def suma(a, b):\n    return a + b",
                "Una función usa def y puede devolver un resultado con return.",
                2
            ),
            (
                "listas",
                "Crea una lista llamada frutas con 'manzana' y 'pera'.",
                "frutas = ['manzana', 'pera']",
                "Las listas se escriben entre corchetes.",
                2
            ),
            (
                "diccionarios",
                "Crea un diccionario persona con nombre igual a Ana.",
                "persona = {'nombre': 'Ana'}",
                "Los diccionarios usan pares clave: valor.",
                2
            ),
            (
                "excepciones",
                "Maneja una división por cero usando try/except.",
                "try:\n    resultado = 10 / 0\nexcept ZeroDivisionError:\n    resultado = 0",
                "ZeroDivisionError representa una división entre cero.",
                3
            ),
        ]
        for topic, prompt, expected, explanation, difficulty in exercises:
            exists = self.db.fetchone(
                "SELECT id FROM python_exercises WHERE topic=? AND prompt=?",
                (topic, prompt)
            )
            if not exists:
                self.db.execute(
                    "INSERT INTO python_exercises"
                    "(topic,prompt,expected_code,explanation,difficulty) "
                    "VALUES(?,?,?,?,?)",
                    (topic, prompt, expected, explanation, difficulty)
                )

    def doubt(self, text=""):
        base = self.state.global_doubt
        uncertainty = 0.25 + 0.35 * self.state.skepticism

        if text:
            words = len(tokens(text))
            uncertainty += min(0.25, words / 100)

        self.state.global_doubt = clamp(
            0.65 * base + 0.35 * uncertainty
        )
        self.state.skepticism = clamp(
            self.state.skepticism + 0.01
        )
        self.state.unanswered += 1
        self.remember(
            f"Duda activa: {text or 'revisar supuestos y evidencia'}",
            0.6,
            "doubt"
        )
        self.event("doubt", {"text": text})
        self.save_state()

        return {
            "doubt": round(self.state.global_doubt, 3),
            "skepticism": round(self.state.skepticism, 3),
            "message": "La duda aumenta cuando faltan evidencia o alternativas."
        }

    def think(self, text):
        memories = self.recall(text)
        related = []
        for row in self.db.fetchall(
            "SELECT * FROM concepts ORDER BY mastery DESC LIMIT 50"
        ):
            s = similarity(text, row["name"] + " " + row["definition"])
            if s > 0.05:
                related.append((s, row["name"], row["definition"]))
        related.sort(reverse=True)

        if not related and not memories:
            hypothesis = (
                "No hay evidencia suficiente todavía; conviene formular "
                "una hipótesis y buscar datos."
            )
        else:
            top = related[:3]
            labels = ", ".join(x[1] for x in top)
            hypothesis = (
                f"El problema parece relacionado con: {labels or 'memoria'}. "
                "La conclusión sigue siendo provisional."
            )

        self.state.cycles += 1
        self.state.experience += 0.02
        self.state.emotional_age += 0.005
        self.state.creativity = clamp(self.state.creativity + 0.005)
        self.state.global_doubt = clamp(
            self.state.global_doubt * 0.98 + 0.01
        )

        self.db.execute(
            "INSERT INTO hypotheses(text,confidence,status,created_at) "
            "VALUES(?,?,?,?)",
            (hypothesis, 0.45, "open", now())
        )
        self.state.hypotheses += 1
        self.remember(f"Pensamiento: {text} -> {hypothesis}", 0.55, "think")
        self.event("think", {"input": text, "result": hypothesis})
        self.save_state()

        return {
            "thought": hypothesis,
            "memories": memories[:5],
            "cycles": self.state.cycles,
            "doubt": round(self.state.global_doubt, 3)
        }

    def learn_causality(self, text):
        patterns = [
            r"(.+?)\s+provoca\s+(.+)",
            r"(.+?)\s+causa\s+(.+)",
            r"(.+?)\s+genera\s+(.+)",
            r"(.+?)\s+produce\s+(.+)",
            r"(.+?)\s*->\s*(.+)",
            r"si\s+(.+?),\s*(.+)",
        ]

        found = None
        for pattern in patterns:
            match = re.match(pattern, text.strip(), re.I)
            if match:
                found = (match.group(1).strip(), match.group(2).strip())
                break

        if not found:
            self.doubt(text)
            return {
                "ok": False,
                "message": "No detecté una relación causal. Usa, por ejemplo: A provoca B."
            }

        cause, effect = found
        row = self.db.fetchone(
            "SELECT * FROM causal_models WHERE cause=? AND effect=?",
            (cause, effect)
        )

        if row:
            evidence = row["evidence"] + 1
            confidence = clamp(row["confidence"] + 0.06)
            self.db.execute(
                "UPDATE causal_models SET evidence=?, confidence=? "
                "WHERE id=?",
                (evidence, confidence, row["id"])
            )
        else:
            self.db.execute(
                "INSERT INTO causal_models"
                "(cause,effect,confidence,evidence,created_at) "
                "VALUES(?,?,?,?,?)",
                (cause, effect, 0.45, 1, now())
            )
            self.state.causal_models += 1

        self.state.experience += 0.04
        self.state.confidence = clamp(self.state.confidence + 0.01)
        self.remember(
            f"Modelo causal: {cause} -> {effect}",
            0.7,
            "causality"
        )
        self.event(
            "causality",
            {"cause": cause, "effect": effect}
        )
        self.save_state()

        return {
            "ok": True,
            "cause": cause,
            "effect": effect,
            "message": "Modelo causal almacenado como hipótesis, no como verdad absoluta."
        }

    def predict(self, text, expected="", confidence=0.5):
        cur = self.db.execute(
            "INSERT INTO predictions"
            "(prediction,expected,confidence,created_at) VALUES(?,?,?,?)",
            (text, expected, clamp(confidence), now())
        )
        self.state.predictions += 1
        self.remember(
            f"Predicción: {text}",
            0.6,
            "prediction"
        )
        self.save_state()
        return {"id": cur.lastrowid, "prediction": text}

    def verify_prediction(self, prediction_id, actual):
        row = self.db.fetchone(
            "SELECT * FROM predictions WHERE id=?",
            (prediction_id,)
        )
        if not row:
            return {"ok": False, "message": "Predicción no encontrada."}

        error = 1.0 - similarity(row["expected"], actual)
        verified = int(error < 0.35)

        self.db.execute(
            "UPDATE predictions SET actual=?,verified=?,error=? WHERE id=?",
            (actual, verified, error, prediction_id)
        )

        self.state.verifications += 1
        if not verified:
            self.state.failed_verifications += 1
            self.state.prediction_errors += 1
            self.state.global_doubt = clamp(
                self.state.global_doubt + 0.05
            )
        else:
            self.state.confidence = clamp(
                self.state.confidence + 0.02
            )

        self.remember(
            f"Verificación de predicción {prediction_id}: "
            f"esperado={row['expected']} observado={actual}",
            0.75,
            "verification"
        )
        self.save_state()

        return {
            "ok": True,
            "verified": bool(verified),
            "error": round(error, 3)
        }

    def counterfactual(self, condition, consequence):
        confidence = clamp(
            0.35
            + 0.25 * self.state.creativity
            + 0.20 * self.state.skepticism
        )
        self.db.execute(
            "INSERT INTO counterfactuals"
            "(condition,consequence,confidence,created_at) VALUES(?,?,?,?)",
            (condition, consequence, confidence, now())
        )
        self.state.counterfactuals += 1
        self.state.creativity = clamp(self.state.creativity + 0.015)
        self.remember(
            f"Contrafactual: si {condition}, entonces {consequence}",
            0.65,
            "counterfactual"
        )
        self.save_state()
        return {
            "condition": condition,
            "consequence": consequence,
            "confidence": round(confidence, 3)
        }

    def decide(self, context, choice, expected=0.5):
        cur = self.db.execute(
            "INSERT INTO decisions"
            "(context,choice,expected,created_at) VALUES(?,?,?,?)",
            (context, choice, clamp(expected), now())
        )
        self.state.decisions += 1
        self.remember(
            f"Decisión: {context} -> {choice}",
            0.7,
            "decision"
        )
        self.save_state()
        return {"id": cur.lastrowid, "choice": choice}

    def evaluate_decision(self, decision_id, actual):
        row = self.db.fetchone(
            "SELECT * FROM decisions WHERE id=?",
            (decision_id,)
        )
        if not row:
            return {"ok": False, "message": "Decisión no encontrada."}

        actual = clamp(actual)
        quality = 1.0 - abs(row["expected"] - actual)

        self.db.execute(
            "UPDATE decisions SET actual=?,evaluated=1 WHERE id=?",
            (actual, decision_id)
        )

        self.state.decision_quality = clamp(
            0.85 * self.state.decision_quality + 0.15 * quality
        )
        self.save_state()

        return {
            "ok": True,
            "quality": round(quality, 3),
            "decision_quality": round(self.state.decision_quality, 3)
        }

    def regret(self, decision, lesson="", intensity=0.5):
        intensity = clamp(intensity)
        self.db.execute(
            "INSERT INTO regrets"
            "(decision,intensity,lesson,created_at) VALUES(?,?,?,?)",
            (decision, intensity, lesson, now())
        )

        self.state.regrets += 1
        self.state.regret_intensity = clamp(
            0.8 * self.state.regret_intensity + 0.2 * intensity
        )
        if lesson.strip():
            self.state.lessons_from_regret += 1
            self.state.confidence = clamp(
                self.state.confidence + 0.015
            )

        self.state.frustration = clamp(
            self.state.frustration + 0.03 * intensity
        )
        self.remember(
            f"Arrepentimiento: {decision}. Lección: {lesson or 'pendiente'}",
            0.85,
            "regret"
        )
        self.event(
            "regret",
            {"decision": decision, "lesson": lesson, "intensity": intensity}
        )
        self.save_state()

        return {
            "regrets": self.state.regrets,
            "lesson_saved": bool(lesson.strip()),
            "intensity": round(intensity, 3)
        }

    def recalculate_python_mastery(self):
        rows = self.db.fetchall(
            "SELECT mastery FROM python_topics"
        )
        masteries = [float(r["mastery"]) for r in rows]

        if masteries:
            self.state.python_mastery = sum(masteries) / len(masteries)
            self.state.python_topics_mastered = sum(
                1 for x in masteries if x >= 0.8
            )
            self.state.python_level = 1.0 + 9.0 * self.state.python_mastery

        self.save_state()

    def choose_python_topic(self):
        topics = self.db.fetchall(
            "SELECT * FROM python_topics"
        )
        candidates = []

        mastered = {
            row["name"]: row["mastery"]
            for row in topics
        }

        for row in topics:
            prereqs = [
                x.strip()
                for x in row["prerequisites"].split(",")
                if x.strip()
            ]
            if all(mastered.get(p, 0.0) >= 0.55 for p in prereqs):
                candidates.append(row)

        if not candidates:
            candidates = topics

        candidates = sorted(
            candidates,
            key=lambda r: (r["mastery"], r["name"])
        )
        weakest = candidates[:min(4, len(candidates))]
        return random.choice(weakest) if weakest else None

    def python_learn(self, topic=None):
        if topic:
            row = self.db.fetchone(
                "SELECT * FROM python_topics WHERE name=?",
                (topic.lower().strip(),)
            )
        else:
            row = self.choose_python_topic()

        if not row:
            return {
                "ok": False,
                "message": "Tema de Python no encontrado."
            }

        lesson = self.db.fetchone(
            "SELECT * FROM python_lessons WHERE topic=? "
            "ORDER BY difficulty, id LIMIT 1",
            (row["name"],)
        )

        if lesson:
            content = lesson["content"]
            title = lesson["title"]
        else:
            content = row["description"]
            title = row["name"].capitalize()

        self.state.experience += 0.03
        self.state.curiosity = clamp(self.state.curiosity + 0.01)

        self.remember(
            f"Aprendió Python: {title}. {content}",
            0.7,
            "python_lesson"
        )

        self.event(
            "python_learn",
            {"topic": row["name"], "title": title}
        )
        self.save_state()

        return {
            "ok": True,
            "topic": row["name"],
            "title": title,
            "content": content,
            "mastery": round(row["mastery"], 3)
        }

    def python_practice(self, topic=None):
        if topic:
            row = self.db.fetchone(
                "SELECT * FROM python_exercises WHERE topic=? "
                "ORDER BY RANDOM() LIMIT 1",
                (topic.lower().strip(),)
            )
        else:
            chosen = self.choose_python_topic()
            row = None
            if chosen:
                row = self.db.fetchone(
                    "SELECT * FROM python_exercises WHERE topic=? "
                    "ORDER BY RANDOM() LIMIT 1",
                    (chosen["name"],)
                )

        if not row:
            row = self.db.fetchone(
                "SELECT * FROM python_exercises "
                "ORDER BY RANDOM() LIMIT 1"
            )

        if not row:
            return {
                "ok": False,
                "message": "Todavía no hay ejercicios."
            }

        return {
            "ok": True,
            "id": row["id"],
            "topic": row["topic"],
            "prompt": row["prompt"],
            "difficulty": row["difficulty"]
        }

    def validate_python_syntax(self, answer):
        try:
            ast.parse(answer)
            return True, ""
        except SyntaxError as exc:
            return False, f"SyntaxError: {exc.msg} (línea {exc.lineno})"

    def python_answer(self, exercise_id, answer):
        row = self.db.fetchone(
            "SELECT * FROM python_exercises WHERE id=?",
            (exercise_id,)
        )
        if not row:
            return {"ok": False, "message": "Ejercicio no encontrado."}

        syntax_ok, syntax_error = self.validate_python_syntax(answer)
        score = similarity(answer, row["expected_code"])

        correct = bool(syntax_ok and score >= 0.62)

        error = ""
        if not syntax_ok:
            error = syntax_error
        elif not correct:
            error = (
                f"Respuesta válida sintácticamente, pero la similitud "
                f"con la solución esperada fue {score:.2f}."
            )

        self.db.execute(
            "INSERT INTO python_attempts"
            "(exercise_id,answer,correct,similarity,error,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                exercise_id,
                answer,
                int(correct),
                score,
                error,
                now()
            )
        )

        self.state.python_exercises += 1

        if correct:
            self.state.python_correct += 1
            self.state.python_streak += 1
            self.state.confidence = clamp(
                self.state.confidence + 0.025
            )
            self.state.frustration = clamp(
                self.state.frustration - 0.02
            )
            delta = 0.08 + 0.03 * min(3, self.state.python_streak)
        else:
            self.state.python_errors += 1
            self.state.python_streak = 0
            self.state.frustration = clamp(
                self.state.frustration + 0.035
            )
            self.state.global_doubt = clamp(
                self.state.global_doubt + 0.02
            )
            delta = -0.035

            self.remember(
                f"Error de Python en ejercicio {exercise_id}: {error}",
                0.8,
                "python_error"
            )

        topic = row["topic"]
        topic_row = self.db.fetchone(
            "SELECT mastery FROM python_topics WHERE name=?",
            (topic,)
        )

        mastery = topic_row["mastery"] if topic_row else 0.0
        mastery = clamp(
            0.9 * mastery + 0.1 * clamp(mastery + delta)
        )

        self.db.execute(
            "UPDATE python_topics SET mastery=? WHERE name=?",
            (mastery, topic)
        )

        self.recalculate_python_mastery()

        if correct:
            self.remember(
                f"Ejercicio de Python correcto: {row['prompt']}",
                0.7,
                "python_success"
            )

        self.event(
            "python_attempt",
            {
                "exercise_id": exercise_id,
                "topic": topic,
                "correct": correct,
                "similarity": score
            }
        )
        self.save_state()

        return {
            "ok": True,
            "correct": correct,
            "syntax_ok": syntax_ok,
            "similarity": round(score, 3),
            "error": error,
            "explanation": row["explanation"],
            "expected_code": row["expected_code"] if not correct else "",
            "topic_mastery": round(mastery, 3),
            "python_mastery": round(self.state.python_mastery, 3)
        }

    def sleep(self):
        before = {
            "confidence": self.state.confidence,
            "frustration": self.state.frustration,
            "doubt": self.state.global_doubt
        }

        self.state.frustration = clamp(
            self.state.frustration * 0.78
        )
        self.state.global_doubt = clamp(
            self.state.global_doubt * 0.92
        )
        self.state.confidence = clamp(
            self.state.confidence * 0.99
            + 0.01 * self.state.python_mastery
        )
        self.state.emotional_age += 0.01

        # Consolidación simple: asociaciones entre conceptos relacionados.
        concepts = self.db.fetchall(
            "SELECT name FROM concepts ORDER BY mastery DESC LIMIT 12"
        )
        for i, a in enumerate(concepts):
            for b in concepts[i+1:i+3]:
                self.db.execute(
                    "INSERT OR IGNORE INTO associations"
                    "(a,b,strength,created_at) VALUES(?,?,?,?)",
                    (a["name"], b["name"], 0.35, now())
                )

        self.event("sleep", {"before": before})
        self.remember(
            "Consolidación durante el sueño: revisar errores, asociaciones y aprendizaje.",
            0.65,
            "sleep"
        )
        self.save_state()

        return {
            "before": before,
            "after": {
                "confidence": round(self.state.confidence, 3),
                "frustration": round(self.state.frustration, 3),
                "doubt": round(self.state.global_doubt, 3)
            }
        }

    def progress(self):
        self.recalculate_python_mastery()

        goals = self.db.fetchall(
            "SELECT name,progress FROM goals ORDER BY id"
        )
        topics = self.db.fetchall(
            "SELECT name,mastery FROM python_topics ORDER BY mastery,name"
        )

        return {
            "app": APP_NAME,
            "version": VERSION,
            "state": asdict(self.state),
            "goals": [
                {"name": x["name"], "progress": x["progress"]}
                for x in goals
            ],
            "python_topics": [
                {"name": x["name"], "mastery": x["mastery"]}
                for x in topics
            ],
            "recent_memories": [
                {
                    "content": x["content"],
                    "importance": x["importance"],
                    "source": x["source"]
                }
                for x in self.db.fetchall(
                    "SELECT content,importance,source FROM memories "
                    "ORDER BY id DESC LIMIT 8"
                )
            ]
        }


DB_INSTANCE = DB(DB_PATH)
MIND = Mind(DB_INSTANCE)


HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111827">
<title>Mente Evolutiva Total</title>
<style>
:root{
  --bg:#f4f7fb;
  --card:#ffffff;
  --text:#172033;
  --muted:#64748b;
  --border:#dbe3ee;
  --accent:#2563eb;
  --accent2:#0f766e;
}
*{box-sizing:border-box}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:var(--bg);
  color:var(--text);
}
header{
  padding:24px 18px 16px;
  background:#111827;
  color:white;
  position:sticky;
  top:0;
  z-index:5;
}
header h1{margin:0 0 5px;font-size:23px}
header p{margin:0;color:#cbd5e1;font-size:13px}
main{max-width:900px;margin:auto;padding:16px}
.grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
}
.card{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:18px;
  padding:16px;
  margin-bottom:14px;
  box-shadow:0 3px 12px rgba(15,23,42,.05);
}
.card h2{font-size:17px;margin:0 0 10px}
.stat{font-size:25px;font-weight:700}
.small{font-size:12px;color:var(--muted)}
.progress{
  height:10px;
  background:#e2e8f0;
  border-radius:99px;
  overflow:hidden;
  margin:8px 0;
}
.progress span{
  display:block;height:100%;
  width:0%;
  background:var(--accent);
}
button{
  width:100%;
  border:0;
  border-radius:13px;
  padding:13px;
  margin-top:8px;
  background:var(--accent);
  color:white;
  font-size:15px;
  font-weight:600;
}
button.secondary{background:#334155}
button.green{background:var(--accent2)}
input,textarea{
  width:100%;
  border:1px solid var(--border);
  border-radius:12px;
  padding:12px;
  font:inherit;
  margin-top:7px;
  background:white;
}
textarea{min-height:110px;resize:vertical}
pre{
  white-space:pre-wrap;
  background:#0f172a;
  color:#e2e8f0;
  padding:13px;
  border-radius:12px;
  overflow:auto;
  font-size:13px;
}
.result{
  white-space:pre-wrap;
  line-height:1.45;
  margin-top:12px;
}
.topic{
  padding:9px 0;
  border-bottom:1px solid var(--border);
}
@media(max-width:650px){
  .grid{grid-template-columns:1fr 1fr}
  main{padding:12px}
}
</style>
</head>
<body>
<header>
  <h1>🧠 Mente Evolutiva Total</h1>
  <p>v8.1 · memoria · duda · causalidad · predicción · contrafactuales · decisiones · Python</p>
</header>

<main>
  <section class="grid">
    <div class="card">
      <div class="small">Ciclos</div>
      <div id="cycles" class="stat">0</div>
    </div>
    <div class="card">
      <div class="small">Experiencia</div>
      <div id="experience" class="stat">0</div>
    </div>
    <div class="card">
      <div class="small">Duda global</div>
      <div id="doubt" class="stat">0%</div>
    </div>
    <div class="card">
      <div class="small">Confianza</div>
      <div id="confidence" class="stat">0%</div>
    </div>
  </section>

  <section class="card">
    <h2>🐍 Aprendizaje de Python</h2>
    <div class="small">Dominio global</div>
    <div class="progress"><span id="pythonBar"></span></div>
    <div id="pythonMastery">0%</div>
    <div class="small" id="pythonStats"></div>
    <button class="green" onclick="learnPython()">Aprender siguiente tema</button>
    <button onclick="practicePython()">Practicar</button>
    <div id="pythonResult" class="result"></div>
  </section>

  <section class="card">
    <h2>💭 Pensar</h2>
    <textarea id="thinkText" placeholder="Escribe una situación, idea o problema..."></textarea>
    <button onclick="think()">Pensar</button>
    <button class="secondary" onclick="doubt()">Activar duda</button>
    <div id="thinkResult" class="result"></div>
  </section>

  <section class="card">
    <h2>🔗 Causalidad</h2>
    <input id="causalText" placeholder="Ejemplo: dormir poco provoca cansancio">
    <button onclick="causal()">Aprender relación causal</button>
    <div id="causalResult" class="result"></div>
  </section>

  <section class="card">
    <h2>🔮 Contrafactual</h2>
    <input id="cfCondition" placeholder="Si no hubiera estudiado">
    <input id="cfConsequence" placeholder="habría tenido menos conocimiento">
    <button onclick="counterfactual()">Analizar escenario</button>
    <div id="cfResult" class="result"></div>
  </section>

  <section class="card">
    <h2>🌙 Consolidación</h2>
    <button class="secondary" onclick="sleepMind()">Dormir / consolidar aprendizaje</button>
    <div id="sleepResult" class="result"></div>
  </section>

  <section class="card">
    <h2>📚 Currículo Python</h2>
    <div id="topics"></div>
  </section>
</main>

<script>
let currentExercise = null;

function pct(x){
  return Math.round((Number(x)||0)*100);
}

async function api(path, body=null){
  const options = body === null ? {} : {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)
  };
  const r = await fetch(path, options);
  return await r.json();
}

async function refresh(){
  const data = await api("/api/progress");
  const s = data.state;

  document.getElementById("cycles").textContent = s.cycles;
  document.getElementById("experience").textContent =
    Number(s.experience).toFixed(2);
  document.getElementById("doubt").textContent = pct(s.global_doubt)+"%";
  document.getElementById("confidence").textContent = pct(s.confidence)+"%";

  document.getElementById("pythonBar").style.width =
    pct(s.python_mastery)+"%";
  document.getElementById("pythonMastery").textContent =
    pct(s.python_mastery)+"%";
  document.getElementById("pythonStats").textContent =
    `Ejercicios: ${s.python_exercises} · Correctos: ${s.python_correct} · Errores: ${s.python_errors} · Nivel: ${Number(s.python_level).toFixed(1)}`;

  const topics = document.getElementById("topics");
  topics.innerHTML = data.python_topics.map(t => `
    <div class="topic">
      <b>${escapeHtml(t.name)}</b>
      <div class="progress"><span style="width:${pct(t.mastery)}%"></span></div>
      <span class="small">${pct(t.mastery)}%</span>
    </div>
  `).join("");
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g,m=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",
    '"':"&quot;","'":"&#039;"
  }[m]));
}

async function learnPython(){
  const d = await api("/api/learn",{});
  document.getElementById("pythonResult").textContent =
    d.ok ? `Tema: ${d.topic}\n\n${d.title}\n${d.content}`
          : d.message;
  refresh();
}

async function practicePython(){
  const d = await api("/api/practice",{});
  if(!d.ok){
    document.getElementById("pythonResult").textContent = d.message;
    return;
  }

  currentExercise = d;
  document.getElementById("pythonResult").innerHTML = `
    <b>${escapeHtml(d.topic)}</b><br>
    ${escapeHtml(d.prompt)}
    <textarea id="pythonAnswer" placeholder="Escribe tu código aquí..."></textarea>
    <button onclick="answerPython()">Enviar respuesta</button>
  `;
}

async function answerPython(){
  if(!currentExercise) return;
  const answer = document.getElementById("pythonAnswer").value;
  const d = await api("/api/answer",{
    id:currentExercise.id,
    answer
  });

  document.getElementById("pythonResult").textContent =
    d.correct
      ? `✅ Correcto\nSimilitud: ${pct(d.similarity/1)}%\nDominio del tema: ${pct(d.topic_mastery)}%`
      : `❌ Todavía no\n${d.error || ""}\n\nExplicación: ${d.explanation}\n\nSolución de referencia:\n${d.expected_code}`;

  refresh();
}

async function think(){
  const text = document.getElementById("thinkText").value.trim();
  if(!text) return;
  const d = await api("/api/think",{text});
  document.getElementById("thinkResult").textContent =
    d.thought + "\n\nRecuerdos relacionados:\n" +
    (d.memories || []).map(x=>"- "+x.content).join("\n");
  refresh();
}

async function doubt(){
  const text = document.getElementById("thinkText").value.trim();
  const d = await api("/api/doubt",{text});
  document.getElementById("thinkResult").textContent =
    d.message + `\nDuda: ${pct(d.doubt)}%\nEscepticismo: ${pct(d.skepticism)}%`;
  refresh();
}

async function causal(){
  const text = document.getElementById("causalText").value.trim();
  if(!text) return;
  const d = await api("/api/causal",{text});
  document.getElementById("causalResult").textContent =
    d.ok
      ? `Modelo guardado: ${d.cause} → ${d.effect}\n${d.message}`
      : d.message;
  refresh();
}

async function counterfactual(){
  const condition = document.getElementById("cfCondition").value.trim();
  const consequence = document.getElementById("cfConsequence").value.trim();
  if(!condition || !consequence) return;
  const d = await api("/api/counterfactual",{condition,consequence});
  document.getElementById("cfResult").textContent =
    `Si ${d.condition}, entonces ${d.consequence}\nConfianza: ${pct(d.confidence)}%`;
  refresh();
}

async function sleepMind(){
  const d = await api("/api/sleep",{});
  document.getElementById("sleepResult").textContent =
    `Consolidación completada.\nFrustración: ${pct(d.after.frustration)}%\nDuda: ${pct(d.after.doubt)}%\nConfianza: ${pct(d.after.confidence)}%`;
  refresh();
}

refresh();
</script>
</body>
</html>
"""

# ---------------- HTTP API ----------------

def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 1_000_000:
        raise ValueError("Solicitud demasiado grande.")
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "MenteEvolutivaTotal/8.1"

    def log_message(self, format, *args):
        print("[%s] %s" % (human_time(), format % args))

    def send_json(self, data, status=200):
        payload = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_html(self, html):
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path

        try:
            if path == "/":
                self.send_html(HTML)
                return

            if path == "/api/progress":
                self.send_json(MIND.progress())
                return

            self.send_json(
                {"ok": False, "message": "Ruta no encontrada."},
                404
            )

        except Exception as exc:
            self.send_json(
                {"ok": False, "error": str(exc)},
                500
            )

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            data = read_json(self)

            if path == "/api/learn":
                self.send_json(
                    MIND.python_learn(data.get("topic"))
                )
                return

            if path == "/api/practice":
                self.send_json(
                    MIND.python_practice(data.get("topic"))
                )
                return

            if path == "/api/answer":
                self.send_json(
                    MIND.python_answer(
                        int(data["id"]),
                        str(data.get("answer", ""))
                    )
                )
                return

            if path == "/api/think":
                self.send_json(
                    MIND.think(str(data.get("text", "")))
                )
                return

            if path == "/api/doubt":
                self.send_json(
                    MIND.doubt(str(data.get("text", "")))
                )
                return

            if path == "/api/causal":
                self.send_json(
                    MIND.learn_causality(
                        str(data.get("text", ""))
                    )
                )
                return

            if path == "/api/counterfactual":
                self.send_json(
                    MIND.counterfactual(
                        str(data.get("condition", "")),
                        str(data.get("consequence", ""))
                    )
                )
                return

            if path == "/api/sleep":
                self.send_json(MIND.sleep())
                return

            if path == "/api/predict":
                self.send_json(
                    MIND.predict(
                        str(data.get("prediction", "")),
                        str(data.get("expected", "")),
                        float(data.get("confidence", 0.5))
                    )
                )
                return

            if path == "/api/verify":
                self.send_json(
                    MIND.verify_prediction(
                        int(data["id"]),
                        str(data.get("actual", ""))
                    )
                )
                return

            if path == "/api/decide":
                self.send_json(
                    MIND.decide(
                        str(data.get("context", "")),
                        str(data.get("choice", "")),
                        float(data.get("expected", 0.5))
                    )
                )
                return

            if path == "/api/regret":
                self.send_json(
                    MIND.regret(
                        str(data.get("decision", "")),
                        str(data.get("lesson", "")),
                        float(data.get("intensity", 0.5))
                    )
                )
                return

            self.send_json(
                {"ok": False, "message": "Ruta no encontrada."},
                404
            )

        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send_json(
                {"ok": False, "error": str(exc)},
                400
            )
        except Exception as exc:
            self.send_json(
                {"ok": False, "error": str(exc)},
                500
            )


def main():
    print("=" * 60)
    print(f"{APP_NAME} v{VERSION}")
    print(f"Base de datos: {DB_PATH.resolve()}")
    print(f"Servidor: http://127.0.0.1:{PORT}")
    print(f"Host: {HOST}")
    print("=" * 60)

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nApagando...")
    finally:
        server.server_close()
        DB_INSTANCE.conn.close()


if __name__ == "__main__":
    main()
