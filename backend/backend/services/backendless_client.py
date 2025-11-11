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


def backendless_get(table: str, where: str = None):
    params = {"where": where} if where else {}
    r = requests.get(get_full_url(f"data/{table}"), params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()
