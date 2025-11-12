import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.backendless.com"
APP_ID = os.getenv("BACKENDLESS_APP_ID")
REST_API_KEY = os.getenv("BACKENDLESS_REST_API_KEY")

HEADERS = {"Content-Type": "application/json; charset=utf-8"}


def get_full_url(path: str) -> str:
    return f"{BASE_URL}/{APP_ID}/{REST_API_KEY}/{path}"


def backendless_post(table: str, payload: dict):
    r = requests.post(get_full_url(f"data/{table}"), json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def backendless_get(table: str, where: str | dict | None = None):
    """
    Realiza una consulta GET a Backendless.
    Puede recibir:
      - una cadena 'where' (por ejemplo: "campo='valor'")
      - un diccionario con parámetros (por ejemplo: {"where": "campo='valor'", "sortBy": "fecha desc"})
      - una ruta directa (por ejemplo: "peliculas/1234-5678")
    """
    # Si el nombre contiene '/', asumimos que es una ruta directa (GET /data/{tabla}/{id})
    if "/" in table:
        url = get_full_url(f"data/{table}")
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json()

    # Si 'where' es cadena -> la convertimos en params dict
    if isinstance(where, str):
        params = {"where": where}
    # Si 'where' ya es un dict (puede incluir sortBy, pageSize, etc.)
    elif isinstance(where, dict):
        params = where
    else:
        params = {}

    # Hacer la llamada con query params
    url = get_full_url(f"data/{table}")
    r = requests.get(url, params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def backendless_patch(table: str, object_id: str, payload: dict):
    url = get_full_url(f"data/{table}/{object_id}")
    r = requests.put(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()

