import os
import csv
from datetime import datetime
from googleapiclient.discovery import build

# ─── Configuració ─────────────────────────────────────────────────────────────
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
HASHTAGS        = ["català", "creadorscatalans", "contingutencatala", "mantincelcatala"]
MAX_CANALS      = 20
POSTS_ANALITZAR = 5
LLINDAR_CATALA  = 0.70

FITXER_LLISTA   = "dades/llista_creadors.csv"
FITXER_SUGGERIM = "dades/suggeriments.csv"

PARAULES_CATALA = [
    "en català", "en catala", "català", "catala", "valenciana", "valencians",
    "mallorquí", "mallorqui", "llengua catalana", "parlant català", "parlem català",
    "fem català", "cultura catalana", "país català"
]
PARAULES_CASTELLA = [
    "en español", "en castellano", "español", "castellano", "habla española",
    "hispanohablante", "hablo español"
]

# ─── Carregar base de dades de Llista ─────────────────────────────────────────
def carregar_llista():
    canals = set()
    if not os.path.exists(FITXER_LLISTA):
        return canals
    with open(FITXER_LLISTA, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("URL", "").strip().lower()
            nom = row.get("Nom", "").strip().lower()
            if url:
                canals.add(url)
            if nom:
                canals.add(nom)
    return canals

# ─── Detectar idioma d'un text ─────────────────────────────────────────────────
def detectar_idioma(text):
    text_lower = text.lower()
    for p in PARAULES_CASTELLA:
        if p in text_lower:
            return "castellà"
    for p in PARAULES_CATALA:
        if p in text_lower:
            return "català"
    return "indeterminat"

# ─── Analitzar els posts d'un canal ───────────────────────────────────────────
def analitzar_canal(youtube, channel_id, channel_title):
    try:
        res = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=POSTS_ANALITZAR,
            order="date",
            type="video"
        ).execute()

        videos = res.get("items", [])
        if not videos:
            return None

        primer = videos[0]["snippet"]
        text_primer = f"{primer.get('title','')} {primer.get('description','')}"
        idioma_primer = detectar_idioma(text_primer)

        if idioma_primer == "castellà":
            print(f"  x {channel_title}: 1r post en castella -> descarta")
            return None

        en_catala = 1 if idioma_primer == "català" else 0
        for video in videos[1:]:
            snippet = video["snippet"]
            text = f"{snippet.get('title','')} {snippet.get('description','')}"
            if detectar_idioma(text) == "català":
                en_catala += 1

        percentatge = en_catala / len(videos)
        compleix = percentatge >= LLINDAR_CATALA

        print(f"  {'OK' if compleix else 'x'} {channel_title}: {en_catala}/{len(videos)} en catala ({int(percentatge*100)}%) -> {'PASSA' if compleix else 'no passa'}")

        if compleix:
            return {
                "Nom":              channel_title,
                "Plataforma":       "YouTube",
                "URL":              f"https://youtube.com/channel/{channel_id}",
                "Posts analitzats": len(videos),
                "Posts en català":  en_catala,
                "% Català":         f"{int(percentatge*100)}%",
                "Data detecció":    datetime.today().strftime("%d/%m/%Y"),
                "Estat":            "Suggeriment pendent"
            }
    except Exception as e:
        print(f"  Error analitzant {channel_title}: {e}")
    return None

# ─── Cerca per hashtag ─────────────────────────────────────────────────────────
def cercar_canals(youtube, hashtag, llista_existent, analitzats):
    print(f"\nCercant #{hashtag}...")
    try:
        res = youtube.search().list(
            part="id,snippet",
            q=f"#{hashtag}",
            type="video",
            order="date",
            maxResults=50,
            relevanceLanguage="ca"
        ).execute()

        suggeriments = []
        for item in res.get("items", []):
            if len(analitzats) >= MAX_CANALS:
                break

            channel_id    = item["snippet"]["channelId"]
            channel_title = item["snippet"]["channelTitle"].strip()
            channel_url   = f"https://youtube.com/channel/{channel_id}"

            if channel_url.lower() in llista_existent or channel_title.lower() in llista_existent:
                print(f"  -> {channel_title}: ja existeix a Llista")
                continue

            if channel_id in analitzats:
                continue

            analitzats.add(channel_id)
            resultat = analitzar_canal(youtube, channel_id, channel_title)
            if resultat:
                suggeriments.append(resultat)

        return suggeriments
    except Exception as e:
        print(f"  Error cercant #{hashtag}: {e}")
        return []

# ─── Guardar suggeriments ──────────────────────────────────────────────────────
def guardar_suggeriments(nous):
    os.makedirs("dades", exist_ok=True)
    existents = []

    if os.path.exists(FITXER_SUGGERIM):
        with open(FITXER_SUGGERIM, newline="", encoding="utf-8") as f:
            existents = list(csv.DictReader(f))

    urls_existents = {r.get("URL", "").lower() for r in existents}
    realment_nous  = [s for s in nous if s["URL"].lower() not in urls_existents]

    if not realment_nous:
        print("\nCap suggeriment nou per afegir.")
        return 0

    tots  = existents + realment_nous
    camps = ["Nom", "Plataforma", "URL", "Posts analitzats", "Posts en català", "% Català", "Data detecció", "Estat"]

    with open(FITXER_SUGGERIM, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=camps)
        writer.writeheader()
        writer.writerows(tots)

    print(f"\n{len(realment_nous)} nou(s) suggeriment(s) afegit(s) al fitxer.")
    return len(realment_nous)

# ─── Principal ─────────────────────────────────────────────────────────────────
def main():
    print(f"{'─'*50}")
    print(f"Recerca de creadors - {datetime.today().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'─'*50}")

    youtube         = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    llista_existent = carregar_llista()
    print(f"Llista actual: {len(llista_existent)} entrades carregades")

    analitzats   = set()
    suggeriments = []

    for hashtag in HASHTAGS:
        if len(analitzats) >= MAX_CANALS:
            break
        nous = cercar_canals(youtube, hashtag, llista_existent, analitzats)
        suggeriments.extend(nous)

    total = guardar_suggeriments(suggeriments)
    print(f"\nResum: {len(analitzats)} canals analitzats, {total} suggeriments nous")
    print(f"{'─'*50}")

if __name__ == "__main__":
    main()
