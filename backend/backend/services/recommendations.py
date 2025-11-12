import time
import requests
import os
from dotenv import load_dotenv
from .backendless_client import backendless_post, backendless_get

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"

def get_tmdb_params(extra: dict = None):
    base = {"api_key": TMDB_API_KEY, "language": "es-MX", "include_adult": "false"}
    if extra:
        base.update(extra)
    return base


# =====================================================
# ============ Funciones auxiliares TMDB ==============
# =====================================================

def search_tmdb_movies(query: str, max_results: int = 5):
    """Busca películas en TMDB usando texto libre (query)."""
    r = requests.get(f"{TMDB_BASE}/search/movie", params=get_tmdb_params({"query": query}))
    data = r.json()
    if not data.get("results"):
        return []
    return data["results"][:max_results]


def search_tmdb_by_keyword(keyword: str, max_results: int = 5):
    """Busca películas en TMDB por keyword (temática)."""
    # Primero busca el ID de la keyword
    r_kw = requests.get(f"{TMDB_BASE}/search/keyword", params=get_tmdb_params({"query": keyword}))
    data_kw = r_kw.json()

    if not data_kw.get("results"):
        return []

    keyword_id = data_kw["results"][0]["id"]

    # Luego busca películas con esa keyword
    r = requests.get(f"{TMDB_BASE}/discover/movie", params=get_tmdb_params({"with_keywords": keyword_id}))
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


# =====================================================
# =============== Películas similares =================
# =====================================================
def get_similar_movies(titulo: str, max_results: int = 5):
    """
    Busca una película por título en TMDB y devuelve otras similares.
    """
    # Paso 1: Buscar ID de la película base
    search_url = f"{TMDB_BASE}/search/movie"
    r = requests.get(search_url, params=get_tmdb_params({"page": 1, "query": titulo}))
    r.raise_for_status()
    data = r.json()

    if not data.get("results"):
        return {"mensaje": f"No encontré películas similares a '{titulo}'.", "detalles": []}

    base_movie = data["results"][0]
    base_id = base_movie["id"]

    # Paso 2: Obtener similares
    sim_url = f"{TMDB_BASE}/movie/{base_id}/similar"
    r2 = requests.get(sim_url, params=get_tmdb_params({"page": 1}))
    r2.raise_for_status()
    sim_data = r2.json()

    results = sim_data.get("results", [])[:max_results]

    if not results:
        return {"mensaje": f"No se encontraron películas similares a '{titulo}'.", "detalles": []}

    # Paso 3: Estructurar resultado
    timestamp = int(time.time() * 1000)
    rec_payload = {
        "consulta": f"Similares a {titulo}",
        "fuente_datos": "TMDB",
        "num_resultados": len(results),
        "fecha_creacion": timestamp,
        "mensaje_resultado": f"Películas similares a '{titulo}'",
    }
    recomendacion = backendless_post("recomendaciones", rec_payload)

    detalles = []
    for idx, movie in enumerate(results, start=1):
        sinopsis = (movie.get("overview") or "").strip()[:250]
        peli_payload = {
            "mdb_id": str(movie.get("id")),
            "titulo": movie.get("title"),
            "fecha_estreno": movie.get("release_date", ""),
            "sinopsis": sinopsis,
        }

        peli = backendless_post("peliculas", peli_payload)
        detalle = {
            "recomendacionId": recomendacion.get("objectId"),
            "peliculaId": peli.get("objectId"),
            "razon_recomendacion": f"Similar a '{titulo}'",
            "orden": idx,
            "fecha_creacion": timestamp,
        }
        backendless_post("detalleRecomendaciones", detalle)
        detalle["pelicula"] = peli
        detalles.append(detalle)

    return {
        "mensaje": f"Películas similares a '{titulo}' encontradas",
        "recomendacion": recomendacion,
        "detalles": detalles,
    }


# =====================================================
# =============== Películas Populares =================
# =====================================================
def get_trending_movies(tipo: str = "popular", max_results: int = 5):
    """
    Devuelve películas populares o estrenos recientes desde TMDB.
    tipo = "popular" o "estrenos"
    """
    if tipo == "estrenos":
        endpoint = f"{TMDB_BASE}/movie/now_playing"
        titulo_rec = "Estrenos recientes"
    else:
        endpoint = f"{TMDB_BASE}/trending/movie/day"
        titulo_rec = "Películas populares"

    r = requests.get(endpoint, params=get_tmdb_params({"page": 1}))
    r.raise_for_status()
    data = r.json()

    results = data.get("results", [])[:max_results]
    if not results:
        return {"mensaje": f"No se encontraron {titulo_rec.lower()}.", "detalles": []}

    # Crear registro principal
    timestamp = int(time.time() * 1000)
    rec_payload = {
        "consulta": titulo_rec,
        "fuente_datos": f"TMDB",
        "num_resultados": len(results),
        "fecha_creacion": timestamp,
        "mensaje_resultado": titulo_rec,
    }
    recomendacion = backendless_post("recomendaciones", rec_payload)

    detalles = []
    for idx, movie in enumerate(results, start=1):
        sinopsis = (movie.get("overview") or "").strip()[:250]
        peli_payload = {
            "mdb_id": str(movie.get("id")),
            "titulo": movie.get("title"),
            "fecha_estreno": movie.get("release_date", ""),
            "sinopsis": sinopsis,
        }
        peli = backendless_post("peliculas", peli_payload)
        detalle = {
            "recomendacionId": recomendacion.get("objectId"),
            "peliculaId": peli.get("objectId"),
            "razon_recomendacion": f"{titulo_rec}",
            "orden": idx,
            "fecha_creacion": timestamp,
        }
        backendless_post("detalleRecomendaciones", detalle)
        detalle["pelicula"] = peli
        detalles.append(detalle)

    return {
        "mensaje": f"{titulo_rec} encontradas",
        "recomendacion": recomendacion,
        "detalles": detalles,
    }
