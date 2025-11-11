import time
import requests
import os
from dotenv import load_dotenv
from .backendless_client import backendless_post, backendless_get

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"


# =====================================================
# ============ Funciones auxiliares TMDB ==============
# =====================================================

def search_tmdb_movies(query: str, max_results: int = 5):
    """Busca películas en TMDB usando texto libre (query)."""
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "es-MX",
        "include_adult": "false",
        "page": 1
    }
    r = requests.get(f"{TMDB_BASE}/search/movie", params=params)
    data = r.json()
    if not data.get("results"):
        return []
    return data["results"][:max_results]


def search_tmdb_by_keyword(keyword: str, max_results: int = 5):
    """Busca películas en TMDB por keyword (temática)."""
    # Primero busca el ID de la keyword
    params_kw = {"api_key": TMDB_API_KEY, "query": keyword}
    r_kw = requests.get(f"{TMDB_BASE}/search/keyword", params=params_kw)
    data_kw = r_kw.json()

    if not data_kw.get("results"):
        return []

    keyword_id = data_kw["results"][0]["id"]

    # Luego busca películas con esa keyword
    params = {
        "api_key": TMDB_API_KEY,
        "with_keywords": keyword_id,
        "language": "es-MX",
        "include_adult": "false"
    }
    r = requests.get(f"{TMDB_BASE}/discover/movie", params=params)
    data = r.json()

    if not data.get("results"):
        return []

    return data["results"][:max_results]


def find_movie_in_backendless(tmdb_id):
    """Busca si una película ya existe en Backendless usando el campo mdb_id."""
    data = backendless_get("peliculas", f"mdb_id='{tmdb_id}'")
    if isinstance(data, list) and data:
        return data[0]
    return None


def create_movie_in_backendless(movie):
    """Crea una nueva película en Backendless."""
    max_size = 256
    sinopsis = movie.get("overview", "")
    if len(sinopsis) > max_size:
        sinopsis = sinopsis[:max_size - 3].rstrip() + "..."
    
    payload = {
        "mdb_id": str(movie.get("id")),
        "titulo": movie.get("title"),
        "fecha_estreno": movie.get("release_date", "") if movie.get("release_date") else None,
        "sinopsis": sinopsis
    }
    return backendless_post("peliculas", payload)


# =====================================================
# =============== Crear Recomendación =================
# =====================================================
def create_recommendation(consulta: str, tipo_busqueda: str = "texto", max_results: int = 5):
    """
    Crea una recomendación completa en Backendless con base en TMDB.
    tipo_busqueda: "texto" o "keyword"
    """
    if tipo_busqueda == "keyword":
        movies = search_tmdb_by_keyword(consulta, max_results)
    else:
        movies = search_tmdb_movies(consulta, max_results)

    timestamp = int(time.time() * 1000)

    # Caso: sin resultados
    if not movies:
        payload = {
            "consulta": consulta,
            "fuente_datos": "TMDB",
            "num_resultados": 0,
            "fecha_creacion": timestamp,
            "mensaje_resultado": "No se encontraron resultados"
        }
        recomendacion = backendless_post("recomendaciones", payload)
        return {
            "mensaje": "Sin resultados",
            "recomendacion": recomendacion,
            "detalles": []
        }

    # Crear recomendación principal
    rec_payload = {
        "consulta": consulta,
        "fuente_datos": "TMDB",
        "num_resultados": len(movies),
        "fecha_creacion": timestamp,
        "mensaje_resultado": "Búsqueda exitosa"
    }
    recomendacion = backendless_post("recomendaciones", rec_payload)
    rec_id = recomendacion.get("objectId")

    # Crear detalles con información completa de película
    detalles = []
    for idx, movie in enumerate(movies, start=1):
        tmdb_id = str(movie["id"])

        # Buscar o crear la película en Backendless
        pelicula = find_movie_in_backendless(tmdb_id)
        if not pelicula:
            pelicula = create_movie_in_backendless(movie)

        # Crear el detalle de recomendación
        detalle_payload = {
            "recomendacionId": rec_id,
            "peliculaId": pelicula.get("objectId"),
            "razon_recomendacion": f"Coincide con '{consulta}'",
            "orden": idx,
            "fecha_creacion": timestamp
        }

        backendless_post("detalleRecomendaciones", detalle_payload)

        # Estructura enriquecida que se devolverá al cliente
        detalle_info = {
            "pelicula": {
                "objectId": pelicula.get("objectId"),
                "titulo": pelicula.get("titulo"),
                "mdb_id": pelicula.get("mdb_id"),
                "sinopsis": pelicula.get("sinopsis"),
                "fecha_estreno": pelicula.get("fecha_estreno")
            },
            "razon_recomendacion": detalle_payload["razon_recomendacion"],
            "orden": detalle_payload["orden"],
            "fecha_creacion": detalle_payload["fecha_creacion"]
        }

        detalles.append(detalle_info)

    # Respuesta completa con estructura deseada
    return {
        "mensaje": "Recomendación creada correctamente",
        "recomendacion": recomendacion,
        "detalles": detalles
    }

