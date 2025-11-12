from fastapi import Body, FastAPI, Query
from fastapi import HTTPException
from pydantic import BaseModel
from services.backendless_client import backendless_get, backendless_patch
from services.recommendations import create_recommendation, get_similar_movies, get_trending_movies
from services.intentions import detect_intention_spacy

import unicodedata

app = FastAPI(title="Movie Recommender API", version="0.1")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== MODELO DE ENTRADA DE CONSULTA ======
class RecomendacionRequest(BaseModel):
    consulta: str

class GatewayIn(BaseModel):
    utterance: str
    tipo_busqueda: str | None = "texto"  # "texto" | "keyword"


@app.get("/")
def root():
    return {"status": "ok", "message": "Movie Recommender API running"}


@app.post("/recomendacion", status_code=201)
def recomendar(payload: RecomendacionRequest = Body(...)):
    """
    Genera recomendaciones basadas en texto y guarda resultados en Backendless.
    El campo usuario_id es opcional.
    """
    result = create_recommendation(
        consulta=payload.consulta
    )
    return result


@app.get("/recomendacion")
def listar_recomendaciones(q: str = Query(None, description="Texto a buscar en razón de recomendación")):
    """
    Devuelve todas las recomendaciones cuyo campo razon_recomendacion contiene el texto indicado.
    Incluye la información completa de la película asociada.
    No distingue mayúsculas ni acentos.
    """
    # Normalizamos el texto para eliminar acentos y pasar a minúsculas
    if q:
        q_normalizado = (
            unicodedata.normalize("NFD", q)
            .encode("ascii", "ignore")
            .decode("utf-8")
            .lower()
        )
    else:
        q_normalizado = ""

    # Obtenemos todos los registros de detalleRecomendaciones
    detalles = backendless_get("detalleRecomendaciones")

    if not isinstance(detalles, list):
        return {"mensaje": "Error en la consulta", "detalles": []}

    resultados = []
    for item in detalles:
        razon = item.get("razon_recomendacion", "")
        razon_normalizada = (
            unicodedata.normalize("NFD", razon)
            .encode("ascii", "ignore")
            .decode("utf-8")
            .lower()
        )

        # Filtrado de coincidencia
        if q_normalizado in razon_normalizada:
            pelicula_id = item.get("peliculaId")
            pelicula = None

            # Si hay película asociada, obtenerla desde Backendless
            if pelicula_id:
                pelicula = backendless_get(f"peliculas/{pelicula_id}")
                if isinstance(pelicula, dict) and pelicula.get("objectId"):
                    # Reducir solo a los campos que queremos exponer
                    pelicula = {
                        "objectId": pelicula.get("objectId"),
                        "titulo": pelicula.get("titulo"),
                        "mdb_id": pelicula.get("mdb_id"),
                        "sinopsis": pelicula.get("sinopsis"),
                        "fecha_estreno": pelicula.get("fecha_estreno"),
                    }

            # Agregar al resultado final
            item_con_pelicula = item.copy()
            item_con_pelicula["pelicula"] = pelicula
            resultados.append(item_con_pelicula)

    return {
        "mensaje": f"Se encontraron {len(resultados)} resultados que coinciden con '{q}'",
        "detalles": resultados
    }


@app.get("/intention")
def chat_endpoint(q: str = Query(None, description="Texto a buscar en razón de recomendación")):
    """
    Simula una interacción tipo chatbot:
    - Si el usuario quiere una nueva recomendación, la genera.
    - Si quiere consultar recomendaciones, las busca.
    - Si no coincide, devuelve un mensaje genérico.
    """

    # Normalizamos el texto para eliminar acentos y pasar a minúsculas
    if q:
        q_normalizado = (
            unicodedata.normalize("NFD", q)
            .encode("ascii", "ignore")
            .decode("utf-8")
            .lower()
        )
    else:
        q_normalizado = ""

    analisis = detect_intention_spacy(q_normalizado)
    intencion = analisis["intencion"]
    consulta = analisis["consulta"]

    return {
        "resultado": "Intención identificada",
        "tipo": intencion,
        "consulta": consulta
    }


@app.get("/evaluar")
def obtener_detalle_para_evaluar():
    """
    Retorna el primer detalle de recomendación sin evaluación asignada,
    incluyendo la información de la película.
    """
    query = "evaluacion is null"
    order = "fecha_creacion asc"
    params = {"where": query, "sortBy": order}
    detalles = backendless_get("detalleRecomendaciones", params)

    if not detalles:
        return {"mensaje": "No hay recomendaciones pendientes por evaluar"}

    detalle = detalles[0]
    pelicula = backendless_get("peliculas", {"where": f"objectId='{detalle['peliculaId']}'"})

    if pelicula and isinstance(pelicula, list):
        detalle["pelicula"] = pelicula[0]

    return detalle


@app.patch("/evaluar/{detalle_id}")
def actualizar_evaluacion(detalle_id: str, evaluacion: int = Query(..., ge=0, le=5)):
    """
    Actualiza la evaluación de un detalle de recomendación.
    """
    payload = {"evaluacion": evaluacion}
    backendless_patch("detalleRecomendaciones", detalle_id, payload)
    return {"mensaje": f"Evaluación registrada ({evaluacion} estrellas)."}


@app.post("/gateway")
def gateway(payload: GatewayIn):
    """
    Recibe texto del usuario, detecta intención y ejecuta la acción
    (crear recomendación, listar o calificar). Si no soportada, 422.
    """
    # 1) Normalizar texto y detectar intención
    texto = (
        unicodedata.normalize("NFD", payload.utterance)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )
    analisis = detect_intention_spacy(texto)
    intent = (analisis.get("intencion") or "").strip()
    consulta = (analisis.get("consulta") or "").strip()
    print(f"\nAnálisis: {analisis}\n")

    # 2) Enrutar por intención
    # ------------------------------------------------------------
    if intent == "nueva_recomendacion":
        return create_recommendation(consulta=consulta)

    # ------------------------------------------------------------
    if intent == "ver_recomendaciones":
        detalles = backendless_get("detalleRecomendaciones")
        if not isinstance(detalles, list):
            raise HTTPException(status_code=500, detail="Error al consultar detalleRecomendaciones")

        resultados = []
        for item in detalles:
            pelicula_id = item.get("peliculaId")
            pelicula = None
            if pelicula_id:
                peli = backendless_get(f"peliculas/{pelicula_id}")
                if isinstance(peli, dict) and peli.get("objectId"):
                    pelicula = {
                        "objectId": peli.get("objectId"),
                        "titulo": peli.get("titulo"),
                        "mdb_id": peli.get("mdb_id"),
                        "sinopsis": peli.get("sinopsis"),
                        "fecha_estreno": peli.get("fecha_estreno"),
                    }
            item_out = item.copy()
            item_out["pelicula"] = pelicula
            resultados.append(item_out)

        return {
            "mensaje": f"Se encontraron {len(resultados)} resultados",
            "detalles": resultados
        }

    # ------------------------------------------------------------
    if intent == "calificar_recomendaciones":
        # Buscar la recomendación pendiente más antigua
        query = "evaluacion is null"
        order = "fecha_creacion asc"
        params = {"where": query, "sortBy": order}
        detalles = backendless_get("detalleRecomendaciones", params)

        if not detalles:
            return {"mensaje": "No hay recomendaciones pendientes por evaluar."}

        detalle = detalles[0]
        pelicula = backendless_get("peliculas", {"where": f"objectId='{detalle['peliculaId']}'"})
        if pelicula and isinstance(pelicula, list):
            detalle["pelicula"] = pelicula[0]

        return {
            "mensaje": "Evaluación pendiente",
            "detalle": detalle
        }

    # ------------------------------------------------------------
    if intent == "buscar_similares":
        return get_similar_movies(consulta)

    # ------------------------------------------------------------
    if intent == "ver_tendencias":
        # Puedes decidir el tipo dinámicamente si el usuario menciona "estreno"
        tipo = "estrenos" if "estreno" in payload.utterance.lower() else "popular"
        return get_trending_movies(tipo)


    # ------------------------------------------------------------
    raise HTTPException(status_code=422, detail=f"Operación no soportada: {intent}")


