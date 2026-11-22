"""Texto da biblioteca: token, BM25, semelhança, corte de especificidade e forma da lição."""
import math
import re
import unicodedata
from collections import Counter

# Pares quase iguais ficam acima; assuntos diferentes ficam abaixo. O teste trava o valor.
DEDUP_SIM = 0.52
K1 = 1.2
B = 0.75
LESSON_LINES = 3

STOP = frozenset(
    "a o os as um uma uns umas de da do das dos e em no na nos nas por para com sem "
    "que se ou mas como mais quando faca porque nao sim este essa esse isso aqui "
    "the of and to for in on is it this that with from".split()
)
SHAPE = re.compile(r"(?is)^quando\s+\S[^,]*,\s*faça\s+\S[^,]*,\s*porque\s+\S.*$")
PATH_RX = re.compile(r"\b[\w.-]+(?:/[\w.-]+)+\b")
FILE_RX = re.compile(r"\b[\w.-]+\.(?:py|md|json|jsonl|txt|sh|yml|yaml)\b", re.I)
SHA_RX = re.compile(r"\b(?=[0-9a-fA-F]*\d)[0-9a-fA-F]{7,40}\b")
NUM_RX = re.compile(r"\d+")


def fold(text):
    text = (text or "").lower().replace("ç", "c")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def tokens(text):
    raw = re.findall(r"[a-z0-9]+", fold(text))
    return [tok for tok in raw if len(tok) >= 3 and tok not in STOP]


def lesson_lines(text):
    return [line for line in (text or "").splitlines() if line.strip()]


def lesson_shape_ok(text):
    lines = lesson_lines(text)
    if not lines or len(lines) > LESSON_LINES:
        return False
    return SHAPE.match(" ".join(lines).strip()) is not None


def bm25_scores(query, docs, k1=K1, b=B):
    """Pontos BM25 de `query` contra cada documento. Corpus vazio vale zero."""
    q = tokens(query)
    docs_t = [tokens(doc) for doc in docs]
    if not docs_t:
        return []
    n = len(docs_t)
    avgdl = sum(len(doc) for doc in docs_t) / float(n) or 1.0
    df = Counter()
    for doc in docs_t:
        for term in set(doc):
            df[term] += 1
    scores = []
    for doc in docs_t:
        tf = Counter(doc)
        dl = len(doc) or 1
        score = 0.0
        for term in q:
            freq = tf.get(term, 0)
            if not freq:
                continue
            seen = df.get(term, 0)
            idf = math.log(1.0 + (n - seen + 0.5) / (seen + 0.5))
            score += idf * (freq * (k1 + 1.0)) / (freq + k1 * (1.0 - b + b * dl / avgdl))
        scores.append(score)
    return scores


def similarity(a, b):
    """BM25 do par, normalizado pelo score do texto contra ele mesmo. 0 a 1."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    if Counter(ta) == Counter(tb):
        return 1.0
    left, right = bm25_scores(a, [a, b])
    if left <= 0:
        return 0.0
    return right / left


def blocked_by_not_for(not_for, query):
    """Sai se pelo menos metade dos termos de `not_for` aparece na consulta.

    `not_for` vazio não exclui. Um termo só exige esse termo.
    """
    terms = tokens(not_for)
    if not terms:
        return False
    query_terms = set(tokens(query))
    hits = sum(1 for term in terms if term in query_terms)
    return hits / float(len(terms)) >= 0.5


def strip_specifics(text, unit=None):
    """Tira caminho, nome de arquivo, id da unidade, sha e número. O resto fica."""
    text = PATH_RX.sub(" ", text or "")
    text = FILE_RX.sub(" ", text)
    if unit:
        text = re.sub(
            r"(?i)(?<![A-Za-z0-9])" + re.escape(unit) + r"(?![A-Za-z0-9])", " ", text)
    text = SHA_RX.sub(" ", text)
    text = NUM_RX.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",(?:\s*,)+", ",", text)
    return text.strip()


def blob(title, when_to_use, body):
    return "\n".join((title or "", when_to_use or "", body or ""))
