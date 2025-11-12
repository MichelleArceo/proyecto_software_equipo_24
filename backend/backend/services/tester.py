import spacy
nlp = spacy.load("es_core_news_md")

doc1 = nlp("muestra lo que está en tendencia")
ejemplos = ["qué películas están de moda", "muéstrame los estrenos de esta semana", "quiero ver las más populares"]

for e in ejemplos:
    sim = doc1.similarity(nlp(e))
    print(f"{e} → {sim:.2f}")