from typing import Optional

import re
import spacy
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
        "busca películas de terror"
    ],
    "ver_recomendaciones": [
        "muéstrame las recomendaciones",
        "quiero ver las sugerencias",
        "enséñame mis recomendaciones anteriores",
        "lista de recomendaciones"
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
        return {"intencion": "nueva_recomendacion", "consulta": consulta or "popular"}

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
        return {"intencion": "nueva_recomendacion", "consulta": consulta or "popular"}

    # --- Intención: ver recomendaciones ---
    if any(v in ["ver", "mostrar", "consultar", "enseñar", "listar"] for v in verbos):
        consulta = None
        for token in doc:
            if token.text in ["de", "sobre"]:
                consulta = " ".join([t.text for t in token.subtree if t != token])
        return {"intencion": "ver_recomendaciones", "consulta": consulta}

    # --- Otro caso ---
    return {"intencion": "no_implementada", "consulta": None}


# util: extraer texto de la subtree tras una preposición (de, sobre, acerca de...)
def _extract_after_prep(doc):
    """
    Devuelve el texto que aparece después de la última preposición relevante
    ('de', 'sobre', 'acerca', 'por', etc.). Si no encuentra nada, retorna None.
    """
    preps = {"de", "sobre", "acerca", "por"}
    last_prep_idx = -1

    # Buscar la última ocurrencia de una preposición relevante
    for i, token in enumerate(doc):
        if token.text.lower() in preps or token.dep_ == "prep":
            last_prep_idx = i

    # Si no se encontró ninguna preposición, salir
    if last_prep_idx == -1 or last_prep_idx == len(doc) - 1:
        return None

    # Tomar todos los tokens después de la última preposición
    after_tokens = [t.text for t in doc[last_prep_idx + 1:] if not t.is_punct]
    phrase = " ".join(after_tokens).strip()

    # Evitar resultados triviales o vacíos
    if not phrase or len(phrase.split()) == 0:
        return None

    return phrase


# util: elegir mejor noun_chunk por heurística y similitud
def _choose_nounchunk_by_similarity(doc, kandid):
    # kandid: lista de noun_chunks (spans)
    if not kandid:
        return None
    best = None
    best_sim = -1.0
    for chunk in kandid:
        # omitimos chunks muy cortos o de stopwords
        txt = chunk.text.strip()
        if len(txt) < 2:
            continue
        sim = doc.similarity(nlp(txt))
        if sim > best_sim:
            best_sim = sim
            best = txt
    return best


# util: limpiar resultado (quitar espacios sobrantes)
def _clean_topic(t: Optional[str]) -> Optional[str]:
    if not t: return None
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else None


def detect_intention_spacy(texto: str, umbral: float = 0.72):
    """
    Retorna dict: { 'intencion': <str>, 'similitud': <float>, 'tema': <str|None'> }
    Usa comparacion semántica para intención y varias heurísticas para extraer tema.
    """
    doc = nlp(texto)
    # 1) detectar intención por similitud con ejemplos
    mejor_intencion = "no_implementada"
    mejor_sim = 0.0
    for intencion, ejemplos in INTENT_EXAMPLES.items():
        for ejemplo in ejemplos:
            sim = doc.similarity(nlp(ejemplo))
            if sim > mejor_sim and sim > umbral:
                mejor_sim = sim
                mejor_intencion = intencion

    # 2) intentar extraer tema explícito (frase tras 'de', 'sobre', 'acerca', etc.)
    consulta = _extract_after_prep(doc)
    if consulta:
        consulta = _clean_topic(consulta)
        return {"intencion": mejor_intencion, "similitud": round(mejor_sim, 2), "consulta": consulta}

    # 3) intentar con entidades nombradas (PERSON, NORP, ORG, WORK_OF_ART, etc.)
    ents = [ent.text for ent in doc.ents if ent.label_ in {"PER", "PERSON", "ORG", "WORK_OF_ART", "MISC"}]
    if ents:
        # tomar la primera entidad razonable
        return {"intencion": mejor_intencion, "similitud": round(mejor_sim, 2), "consulta": _clean_topic(ents[0])}

    # 4) noun chunks: elegir chunk más representativo por similitud
    noun_chunks = list(doc.noun_chunks)
    tema_nc = _choose_nounchunk_by_similarity(doc, noun_chunks)
    if tema_nc:
        return {"intencion": mejor_intencion, "similitud": round(mejor_sim, 2), "consulta": _clean_topic(tema_nc)}

    # 5) fallback: tomar el sustantivo raíz (si existe)
    sustantivos = [tok.lemma_ for tok in doc if tok.pos_ == "NOUN"]
    if sustantivos:
        return {"intencion": mejor_intencion, "similitud": round(mejor_sim, 2), "consulta": sustantivos[0]}

    # 6) si no hay nada, devolver None en tema
    return {"intencion": mejor_intencion, "similitud": round(mejor_sim, 2), "consulta": None}


