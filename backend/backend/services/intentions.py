from typing import Optional

import re
import spacy
import statistics
import unicodedata

# Cargar modelo pequeño de español
print("Loading spaCy ...")
nlp = spacy.load("es_core_news_md")
print("... spaCy loaded")

INTENT_EXAMPLES = {
    "nueva_recomendacion": [
        "recomiéndame una película",
        "quiero ver algo nuevo",
        "sugiéreme una película",
        "busca películas de terror",
        "busca películas de acción",
        "busca películas de amor",
        "busca películas de Pixar",
        "busca películas de Disney",
        "busca películas de comedia",
        "busca películas de ciencia ficción",
        "busca películas de drama",
        "dame una recomendación",
        "quiero descubrir una película diferente",
        "qué película me recomiendas hoy"
    ],
    "ver_recomendaciones": [
        "muéstrame las recomendaciones",
        "quiero ver las sugerencias",
        "enséñame mis recomendaciones anteriores",
        "lista de recomendaciones",
        "quiero revisar mis recomendaciones",
        "muestra las películas sugeridas",
        "ver recomendaciones guardadas"
    ],
    "calificar_recomendaciones": [
        "quiero calificar las recomendaciones",
        "quiero evaluar las sugerencias",
        "quiero poner calificación a las películas recomendadas",
        "quiero revisar y calificar las películas",
        "deseo evaluar las recomendaciones del sistema",
        "quiero asignar estrellas a las recomendaciones",
        "quiero dar mi opinión sobre las recomendaciones"
    ],
    "buscar_similares": [
        "muéstrame películas parecidas a Inception",
        "quiero algo similar a Titanic",
        "películas como Matrix",
        "quiero ver algo parecido a Avatar",
        "recomiéndame algo del estilo de Shrek",
        "busca películas parecidas a Harry Potter",
        "dame opciones similares a El Señor de los Anillos"
    ],
    "ver_tendencias": [
        "qué películas están de moda",
        "muéstrame los estrenos de esta semana",
        "quiero ver las más populares",
        "dime las películas del momento",
        "enséñame las películas más vistas",
        "cuáles son los estrenos recientes",
        "muestra lo que está en tendencia"
    ],
}


def detect_intention(mensaje: str) -> dict:
    """
    Determina la intención del usuario según palabras clave simples.
    Retorna un diccionario con 'intencion' y 'parametros' (si aplica).
    """
    # Normalizar texto: quitar acentos, pasar a minúsculas
    texto = unicodedata.normalize("NFD", mensaje)
    texto = texto.encode("ascii", "ignore").decode("utf-8").lower()

    # --- Intención 1: nueva recomendación ---
    patrones_recomendacion = [
        r"recomienda", r"recomiendame", r"quiero ver", r"sugiere", r"pel[ií]cula[s]?"
    ]
    if any(re.search(p, texto) for p in patrones_recomendacion):
        # extraer posible tema o palabra clave
        palabras = texto.split()
        # detectar después de “de” o “sobre”
        consulta = None
        if "de" in palabras:
            idx = palabras.index("de")
            consulta = " ".join(palabras[idx + 1 :])
        elif "sobre" in palabras:
            idx = palabras.index("sobre")
            consulta = " ".join(palabras[idx + 1 :])
        print(f"\nConsulta: {consulta}\n")
        return {"intencion": "nueva_recomendacion", "consulta": consulta}

    # --- Intención 2: ver recomendaciones previas ---
    patrones_consulta = [
        r"muestrame", r"ensename", r"ver", r"consulta", r"recomendaciones"
    ]
    if any(re.search(p, texto) for p in patrones_consulta):
        # intentar capturar el término de búsqueda
        palabras = texto.split()
        consulta = None
        if "de" in palabras:
            idx = palabras.index("de")
            consulta = " ".join(palabras[idx + 1 :])
        elif "sobre" in palabras:
            idx = palabras.index("sobre")
            consulta = " ".join(palabras[idx + 1 :])
        return {"intencion": "ver_recomendaciones", "consulta": consulta}

    # --- Intención no implementada ---
    return {"intencion": "no_implementada", "consulta": None}


def detect_intention_spacy_sm(texto: str):
    doc = nlp(texto.lower())

    # Verbos clave
    verbos = [token.lemma_ for token in doc if token.pos_ == "VERB"]
    sustantivos = [token.lemma_ for token in doc if token.pos_ != "VERB"]

    print(f"v: {verbos}")
    print(f"s: {sustantivos}")

    # --- Intención: pedir recomendación ---
    if any(v in ["recomendar", "querer", "sugerir", "buscar"] for v in verbos) and any(
        s in ["película", "cine", "film", "historia"] for s in sustantivos
    ):
        consulta = None
        for token in doc:
            if token.text in ["de", "sobre"]:
                consulta = " ".join([t.text for t in token.subtree if t != token])
        print(f"\nConsulta: {consulta}\n")
        return {"intencion": "nueva_recomendacion", "consulta": consulta}

    # --- Intención: ver recomendaciones ---
    if any(v in ["ver", "mostrar", "consultar", "enseñar", "listar"] for v in verbos):
        consulta = None
        for token in doc:
            if token.text in ["de", "sobre"]:
                consulta = " ".join([t.text for t in token.subtree if t != token])
        return {"intencion": "ver_recomendaciones", "consulta": consulta}

    # --- Otro caso ---
    return {"intencion": "no_implementada", "consulta": None}



    if not t: return None
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else None


# ───────────────────────────────
# Utilidades lingüísticas
# ───────────────────────────────
def _extract_after_prep(doc):
    """
    Devuelve el texto después de la última preposición relevante
    ('de', 'sobre', 'acerca', 'por', etc.)
    """
    preps = {"a", "de", "sobre", "acerca", "por"}
    last_prep_idx = -1

    for i, token in enumerate(doc):
        if token.text.lower() in preps or token.dep_ == "prep":
            last_prep_idx = i

    if last_prep_idx == -1 or last_prep_idx == len(doc) - 1:
        return None

    after_tokens = [t.text for t in doc[last_prep_idx + 1:] if not t.is_punct]
    phrase = " ".join(after_tokens).strip()

    if not phrase or len(phrase.split()) == 0:
        return None
    return phrase


def _choose_nounchunk_by_similarity(doc, kandid):
    """Elige el noun_chunk más representativo por similitud semántica."""
    if not kandid:
        return None
    best = None
    best_sim = -1.0
    for chunk in kandid:
        txt = chunk.text.strip()
        if len(txt) < 2:
            continue
        sim = doc.similarity(nlp(txt))
        if sim > best_sim:
            best_sim = sim
            best = txt
    return best


def _clean_topic(t: Optional[str]) -> Optional[str]:
    """Limpia espacios o caracteres redundantes."""
    if not t:
        return None
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else None


def merge_named_entities(doc):
    """Combina entidades compuestas (ej. 'Toy Story') en un solo token virtual."""
    spans = list(doc.ents)
    with doc.retokenize() as retokenizer:
        for span in spans:
            if span.label_ in {"WORK_OF_ART", "ORG", "PERSON", "MISC"}:
                retokenizer.merge(span)
    return doc


def detect_intention_spacy_old(texto: str, umbral: float = 0.55):
    """
    Retorna dict:
      {
        'intencion': <str>,
        'similitud': <float>,
        'consulta': <str | None>
      }

    Usa comparación semántica promedio para intención,
    y heurísticas lingüísticas para extraer tema (consulta).
    """
    doc = nlp(texto)
    doc = merge_named_entities(doc)
    mejor_intencion = "no_implementada"
    mejor_sim = 0.0

    # 1 Comparar por promedio de similitud por intención
    for intencion, ejemplos in INTENT_EXAMPLES.items():
        sims = [doc.similarity(nlp(e)) for e in ejemplos]
        sim_prom = sum(sims) / len(sims)
        if sim_prom > mejor_sim and sim_prom > umbral:
            mejor_sim = sim_prom
            mejor_intencion = intencion

    # 2 Intentar extraer tema explícito (frase tras preposición)
    consulta = _extract_after_prep(doc)
    if consulta:
        return {
            "intencion": mejor_intencion,
            "similitud": round(mejor_sim, 2),
            "consulta": _clean_topic(consulta),
        }

    # 3 Intentar con entidades nombradas
    ents = [ent.text for ent in doc.ents if ent.label_ in {"PER", "PERSON", "ORG", "WORK_OF_ART", "MISC"}]
    if ents:
        return {
            "intencion": mejor_intencion,
            "similitud": round(mejor_sim, 2),
            "consulta": _clean_topic(ents[0]),
        }

    # 4 Intentar con noun chunks
    noun_chunks = list(doc.noun_chunks)
    tema_nc = _choose_nounchunk_by_similarity(doc, noun_chunks)
    if tema_nc:
        return {
            "intencion": mejor_intencion,
            "similitud": round(mejor_sim, 2),
            "consulta": _clean_topic(tema_nc),
        }

    # 5 Fallback: sustantivo raíz
    sustantivos = [tok.lemma_ for tok in doc if tok.pos_ == "NOUN"]
    if sustantivos:
        return {
            "intencion": mejor_intencion,
            "similitud": round(mejor_sim, 2),
            "consulta": sustantivos[0],
        }

    # 6 Si no se encuentra tema
    return {
        "intencion": mejor_intencion,
        "similitud": round(mejor_sim, 2),
        "consulta": None,
    }


def detect_intention_spacy(texto: str):
    doc = nlp(texto)
    sims_globales = []

    mejor_intencion = "no_implementada"
    mejor_sim = 0.0

    # 1. Calcular todas las similitudes
    for intencion, ejemplos in INTENT_EXAMPLES.items():
        for ejemplo in ejemplos:
            sim = doc.similarity(nlp(ejemplo))
            sims_globales.append((intencion, sim))
            if sim > mejor_sim:
                mejor_sim = sim
                mejor_intencion = intencion

    # 2. Calcular media y desviación estándar global
    valores = [s for _, s in sims_globales]
    media = statistics.mean(valores)
    std = statistics.pstdev(valores)
    z_score = (mejor_sim - media) / std if std > 0 else 0

    # 3. Definir criterio adaptativo
    # (si el mejor resultado está al menos 0.5 desviaciones por arriba de la media)
    if z_score < 0.5:
        mejor_intencion = "no_implementada"

    return {
        "intencion": mejor_intencion,
        "similitud": round(mejor_sim, 2),
        "z_score": round(z_score, 2),
        "media": round(media, 2),
        "consulta": _extract_after_prep(doc)
    }
