import random
import re

import pandas as pd
import requests
import streamlit as st

# --- Language bootstrap. This has to happen before set_page_config (Streamlit's first
#     command rule), so it only needs the page title, not the full UI text bank below. ---
if "language" not in st.session_state:
    st.session_state.language = "English"
LANG = "es" if st.session_state.language == "Español" else "en"

PAGE_TITLES = {"en": "The Growing Faith App", "es": "La App de Fe Creciente"}
st.set_page_config(page_title=PAGE_TITLES[LANG], page_icon="🌱", layout="centered")

# Custom avatar for assistant chat bubbles -- overrides Streamlit's default robot icon.
ASSISTANT_AVATAR = "✝️"

# --- Testament classification (computed from the reference, not stored in the CSV) ---
OT_BOOKS = {
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges", "ruth",
    "1 samuel", "2 samuel", "1 kings", "2 kings", "1 chronicles", "2 chronicles", "ezra",
    "nehemiah", "esther", "job", "psalm", "psalms", "proverbs", "ecclesiastes",
    "song of solomon", "isaiah", "jeremiah", "lamentations", "ezekiel", "daniel", "hosea",
    "joel", "amos", "obadiah", "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai",
    "zechariah", "malachi",
}
NT_BOOKS = {
    "matthew", "mark", "luke", "john", "acts", "romans", "1 corinthians", "2 corinthians",
    "galatians", "ephesians", "philippians", "colossians", "1 thessalonians",
    "2 thessalonians", "1 timothy", "2 timothy", "titus", "philemon", "hebrews", "james",
    "1 peter", "2 peter", "1 john", "2 john", "3 john", "jude", "revelation",
}

# --- English book name -> (USX code for the Spanish API, Spanish display name).
#     Needed to fetch Reina-Valera 1909 text and to show localized references/book
#     names when the app is running in Spanish. ---
BOOK_INFO = {
    "genesis": ("GEN", "Génesis"), "exodus": ("EXO", "Éxodo"), "leviticus": ("LEV", "Levítico"),
    "numbers": ("NUM", "Números"), "deuteronomy": ("DEU", "Deuteronomio"), "joshua": ("JOS", "Josué"),
    "judges": ("JDG", "Jueces"), "ruth": ("RUT", "Rut"), "1 samuel": ("1SA", "1 Samuel"),
    "2 samuel": ("2SA", "2 Samuel"), "1 kings": ("1KI", "1 Reyes"), "2 kings": ("2KI", "2 Reyes"),
    "1 chronicles": ("1CH", "1 Crónicas"), "2 chronicles": ("2CH", "2 Crónicas"), "ezra": ("EZR", "Esdras"),
    "nehemiah": ("NEH", "Nehemías"), "esther": ("EST", "Ester"), "job": ("JOB", "Job"),
    "psalm": ("PSA", "Salmos"), "psalms": ("PSA", "Salmos"), "proverbs": ("PRO", "Proverbios"),
    "ecclesiastes": ("ECC", "Eclesiastés"), "song of solomon": ("SNG", "Cantar de los Cantares"),
    "isaiah": ("ISA", "Isaías"), "jeremiah": ("JER", "Jeremías"), "lamentations": ("LAM", "Lamentaciones"),
    "ezekiel": ("EZK", "Ezequiel"), "daniel": ("DAN", "Daniel"), "hosea": ("HOS", "Oseas"),
    "joel": ("JOL", "Joel"), "amos": ("AMO", "Amós"), "obadiah": ("OBA", "Abdías"),
    "jonah": ("JON", "Jonás"), "micah": ("MIC", "Miqueas"), "nahum": ("NAM", "Nahum"),
    "habakkuk": ("HAB", "Habacuc"), "zephaniah": ("ZEP", "Sofonías"), "haggai": ("HAG", "Hageo"),
    "zechariah": ("ZEC", "Zacarías"), "malachi": ("MAL", "Malaquías"),
    "matthew": ("MAT", "Mateo"), "mark": ("MRK", "Marcos"), "luke": ("LUK", "Lucas"),
    "john": ("JHN", "Juan"), "acts": ("ACT", "Hechos"), "romans": ("ROM", "Romanos"),
    "1 corinthians": ("1CO", "1 Corintios"), "2 corinthians": ("2CO", "2 Corintios"),
    "galatians": ("GAL", "Gálatas"), "ephesians": ("EPH", "Efesios"), "philippians": ("PHP", "Filipenses"),
    "colossians": ("COL", "Colosenses"), "1 thessalonians": ("1TH", "1 Tesalonicenses"),
    "2 thessalonians": ("2TH", "2 Tesalonicenses"), "1 timothy": ("1TI", "1 Timoteo"),
    "2 timothy": ("2TI", "2 Timoteo"), "titus": ("TIT", "Tito"), "philemon": ("PHM", "Filemón"),
    "hebrews": ("HEB", "Hebreos"), "james": ("JAS", "Santiago"), "1 peter": ("1PE", "1 Pedro"),
    "2 peter": ("2PE", "2 Pedro"), "1 john": ("1JN", "1 Juan"), "2 john": ("2JN", "2 Juan"),
    "3 john": ("3JN", "3 Juan"), "jude": ("JUD", "Judas"), "revelation": ("REV", "Apocalipsis"),
}


def book_from_reference(reference: str) -> str:
    return re.sub(r"\s\d+(:\d+(-\d+)?)?$", "", reference).strip()


def classify_testament(reference: str) -> str:
    book = book_from_reference(reference).lower()
    if book in OT_BOOKS:
        return "Old Testament"
    if book in NT_BOOKS:
        return "New Testament"
    return "Unknown"


def parse_reference(reference: str):
    match = re.match(r"^(.*?)\s(\d+):(\d+)(?:-(\d+))?$", reference)
    if not match:
        return None
    book, chapter, start, end = match.groups()
    return book, int(chapter), int(start), int(end) if end else int(start)


def localize_reference(reference: str, lang: str) -> str:
    """Swaps in the Spanish book name for display, e.g. 'Matthew 11:28' -> 'Mateo 11:28'.
    The canonical reference string used for CSV joins, API calls, and session_state stays
    English everywhere else -- this is a display-only transform."""
    if lang != "es":
        return reference
    book = book_from_reference(reference)
    info = BOOK_INFO.get(book.lower())
    if not info:
        return reference
    suffix = reference[len(book):]
    return f"{info[1]}{suffix}"


@st.cache_data
def load_reference_data():
    data = pd.read_csv("verses.csv")
    data["testament"] = data["reference"].apply(classify_testament)
    return data


# --- English verse text: World English Bible (WEB), free + public domain, via bible-api.com ---
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def fetch_verse_text_en(reference: str, translation: str = "web"):
    try:
        resp = requests.get(
            f"https://bible-api.com/{reference}",
            params={"translation": translation},
            timeout=6,
        )
        resp.raise_for_status()
        text = resp.json().get("text", "")
        return re.sub(r"\s+", " ", text).strip() or None
    except Exception:
        return None


def fetch_context_en(reference: str, margin: int = 10):
    """Widens out to `margin` verses before/after, shrinking automatically if that
    range spills past the start/end of the chapter."""
    parsed = parse_reference(reference)
    if not parsed:
        return fetch_verse_text_en(reference), reference
    book, chapter, start, end = parsed
    for m in range(margin, -1, -1):
        ctx_start = max(1, start - m)
        ctx_end = end + m
        ctx_ref = (
            f"{book} {chapter}:{ctx_start}-{ctx_end}"
            if ctx_end > ctx_start
            else f"{book} {chapter}:{ctx_start}"
        )
        text = fetch_verse_text_en(ctx_ref)
        if text:
            return text, ctx_ref
    return None, reference


# --- Spanish verse text: Reina-Valera 1909 (RV1909), free + public domain, via
#     bible.helloao.org. Whole chapters are cached, so a verse range or a wide
#     surrounding-context lookup never needs more than one request. ---
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def fetch_chapter_es(book_code: str, chapter: int):
    try:
        resp = requests.get(
            f"https://bible.helloao.org/api/spa_r09/{book_code}/{chapter}.json",
            timeout=8,
        )
        resp.raise_for_status()
        verses = {}
        for item in resp.json()["chapter"]["content"]:
            if item.get("type") == "verse":
                verses[item["number"]] = " ".join(
                    part for part in item["content"] if isinstance(part, str)
                )
        return verses or None
    except Exception:
        return None


def fetch_verse_text_es(reference: str):
    parsed = parse_reference(reference)
    if not parsed:
        return None
    book, chapter, start, end = parsed
    info = BOOK_INFO.get(book.lower())
    if not info:
        return None
    verses = fetch_chapter_es(info[0], chapter)
    if not verses:
        return None
    text = " ".join(verses[n] for n in range(start, end + 1) if n in verses)
    return text.strip() or None


def fetch_context_es(reference: str, margin: int = 10):
    parsed = parse_reference(reference)
    if not parsed:
        return None, reference
    book, chapter, start, end = parsed
    info = BOOK_INFO.get(book.lower())
    if not info:
        return None, reference
    verses = fetch_chapter_es(info[0], chapter)
    if not verses:
        return None, reference
    max_verse = max(verses.keys())
    ctx_start = max(1, start - margin)
    ctx_end = min(max_verse, end + margin)
    text = " ".join(verses[n] for n in range(ctx_start, ctx_end + 1) if n in verses)
    ctx_ref = (
        f"{book} {chapter}:{ctx_start}-{ctx_end}"
        if ctx_end > ctx_start
        else f"{book} {chapter}:{ctx_start}"
    )
    return (text.strip() or None), ctx_ref


def fetch_verse_text(reference: str, lang: str):
    return fetch_verse_text_es(reference) if lang == "es" else fetch_verse_text_en(reference)


def fetch_context(reference: str, lang: str, margin: int = 10):
    return fetch_context_es(reference, margin) if lang == "es" else fetch_context_en(reference, margin)


# --- Moods, in the order they're offered in the picker (internal keys stay English --
#     they're the join key against verses.csv -- only the on-screen label is localized) ---
MOOD_ORDER = [
    "Weary", "Grieving", "Afraid", "Anxious", "Angry", "Lonely",
    "Grateful", "Hopeful", "Seeking Guidance", "Joyful",
]

MOOD_LABELS = {
    "en": {m: m for m in MOOD_ORDER},
    "es": {
        "Weary": "Cansado/a", "Grieving": "Afligido/a", "Afraid": "Asustado/a",
        "Anxious": "Ansioso/a", "Angry": "Enojado/a", "Lonely": "Solo/a",
        "Grateful": "Agradecido/a", "Hopeful": "Esperanzado/a",
        "Seeking Guidance": "Buscando guía", "Joyful": "Alegre",
    },
}

TESTAMENT_LABELS = {
    "en": {"Both": "Both", "Old Testament": "Old Testament", "New Testament": "New Testament"},
    "es": {"Both": "Ambos", "Old Testament": "Antiguo Testamento", "New Testament": "Nuevo Testamento"},
}

# --- Varied response banks. Each list has several phrasings; one is picked at random
#     each time so the conversation doesn't feel like the same fixed script on repeat use. ---

GREETINGS = {
    "en": [
        "Hey -- how's your day going?",
        "Hi there! What's on your mind today?",
        "Hey! How are you feeling right now?",
        "Welcome back -- how's everything going today?",
    ],
    "es": [
        "Hola -- ¿cómo va tu día?",
        "¡Hola! ¿Qué tienes en mente hoy?",
        "¡Hola! ¿Cómo te sientes en este momento?",
        "Bienvenido/a de nuevo -- ¿cómo va todo hoy?",
    ],
}

ACK_VARIANTS = {
    "en": {
        "Weary": [
            "Running on empty is exhausting. It's okay to feel worn out.",
            "Weariness has a way of settling into everything. Be gentle with yourself.",
            "Feeling depleted is hard, no matter the cause. Rest is allowed.",
        ],
        "Grieving": [
            "Grief is heavy to carry, however it shows up for you.",
            "Loss leaves a real ache, and grieving takes time.",
            "There's no right way to grieve. However you're feeling it is okay.",
        ],
        "Afraid": [
            "Fear can be so unsettling to sit with.",
            "Feeling afraid takes a real toll, whatever's behind it.",
            "Fear is hard to carry alone. You don't have to face it by yourself.",
        ],
        "Anxious": [
            "Anxious feelings can be so exhausting to carry around.",
            "Worry has a way of taking over everything else.",
            "Anxiety can make everything feel louder than it is.",
        ],
        "Angry": [
            "Anger is a valid thing to feel.",
            "Frustration is a completely human thing to feel.",
            "It's okay to feel angry. It doesn't mean you've done anything wrong.",
        ],
        "Lonely": [
            "I'm sorry you're feeling so alone right now.",
            "Isolation is a hard feeling to sit with.",
            "It's hard to feel unseen sometimes.",
        ],
        "Grateful": [
            "Gratitude is always worth noticing.",
            "Gratitude is a wonderful place to be in.",
            "There's something good about pausing to feel thankful.",
        ],
        "Hopeful": [
            "I love that you're feeling hopeful.",
            "Hope is a great feeling to hold onto.",
            "Hope is always worth savoring.",
        ],
        "Seeking Guidance": [
            "It makes sense to feel unsure -- big questions deserve some thought.",
            "Not knowing which way to go is uncomfortable, and that's understandable.",
            "Feeling stuck happens to everyone at some point.",
        ],
        "Joyful": [
            "Joy is wonderful to feel!",
            "Joyful energy is contagious!",
            "Joy is always worth celebrating.",
        ],
    },
    "es": {
        "Weary": [
            "Andar con el tanque vacío es agotador. Está bien sentirte cansado/a.",
            "El cansancio tiene una forma de meterse en todo. Sé amable contigo mismo/a.",
            "Sentirte agotado/a es difícil, sin importar la causa. Descansar está permitido.",
        ],
        "Grieving": [
            "El duelo pesa mucho, sin importar cómo se presente para ti.",
            "La pérdida deja una herida real, y sanar toma tiempo.",
            "No existe una forma correcta de vivir el duelo. Como sea que lo sientas está bien.",
        ],
        "Afraid": [
            "El miedo puede ser inquietante de sobrellevar.",
            "Sentir miedo cuesta mucho, sin importar de dónde venga.",
            "El miedo es difícil de cargar solo/a. No tienes que enfrentarlo tú solo/a.",
        ],
        "Anxious": [
            "Los sentimientos de ansiedad pueden ser tan agotadores de cargar.",
            "La preocupación tiene una forma de apoderarse de todo lo demás.",
            "La ansiedad puede hacer que todo se sienta más fuerte de lo que es.",
        ],
        "Angry": [
            "El enojo es algo válido de sentir.",
            "La frustración es algo completamente humano de sentir.",
            "Está bien sentir enojo. No significa que hayas hecho algo mal.",
        ],
        "Lonely": [
            "Siento que te sientas tan solo/a ahora mismo.",
            "El aislamiento es un sentimiento difícil de sobrellevar.",
            "A veces es difícil sentirte invisible.",
        ],
        "Grateful": [
            "La gratitud siempre vale la pena notarla.",
            "La gratitud es un lugar maravilloso en el cual estar.",
            "Hay algo bueno en detenerte a sentir agradecimiento.",
        ],
        "Hopeful": [
            "Me encanta que te sientas esperanzado/a.",
            "La esperanza es un gran sentimiento para aferrarte a él.",
            "La esperanza siempre vale la pena saborearla.",
        ],
        "Seeking Guidance": [
            "Tiene sentido sentirte inseguro/a -- las grandes preguntas merecen reflexión.",
            "No saber qué camino tomar es incómodo, y eso es comprensible.",
            "Sentirte estancado/a le pasa a todo el mundo en algún momento.",
        ],
        "Joyful": [
            "¡La alegría se siente maravillosa!",
            "¡La energía alegre es contagiosa!",
            "La alegría siempre vale la pena celebrarla.",
        ],
    },
}

TRANSITION_VARIANTS = {
    "en": {
        "Weary": [
            "Here are some verses that might help renew your strength:",
            "A few passages about rest and renewed strength, for when you're running low:",
        ],
        "Grieving": [
            "Here are some verses that might bring you a little comfort:",
            "A few passages about God's nearness in grief:",
        ],
        "Afraid": [
            "Here are some verses about courage and God's presence with you:",
            "A few passages about courage when things feel uncertain:",
        ],
        "Anxious": [
            "Here are some verses that might help bring you some peace:",
            "A few passages about trading worry for peace:",
        ],
        "Angry": [
            "Here are some verses that might help you process that:",
            "A few passages about handling anger well:",
        ],
        "Lonely": [
            "Here are some verses reminding you that you're never truly alone:",
            "A few passages about God's presence even in isolation:",
        ],
        "Grateful": [
            "Here are some verses to celebrate that gratitude with you:",
            "A few passages about thankfulness:",
        ],
        "Hopeful": [
            "Here are some verses to encourage that hope even more:",
            "A few passages about hope that holds up:",
        ],
        "Seeking Guidance": [
            "Here are some verses about seeking direction:",
            "A few passages about finding guidance:",
        ],
        "Joyful": [
            "Here are some verses to celebrate that joyful vibe with you:",
            "A few passages about joy:",
        ],
    },
    "es": {
        "Weary": [
            "Aquí tienes algunos versículos que podrían ayudar a renovar tus fuerzas:",
            "Algunos pasajes sobre el descanso y las fuerzas renovadas, para cuando estás bajo/a de energía:",
        ],
        "Grieving": [
            "Aquí tienes algunos versículos que podrían traerte un poco de consuelo:",
            "Algunos pasajes sobre la cercanía de Dios en el duelo:",
        ],
        "Afraid": [
            "Aquí tienes algunos versículos sobre el valor y la presencia de Dios contigo:",
            "Algunos pasajes sobre el valor cuando las cosas se sienten inciertas:",
        ],
        "Anxious": [
            "Aquí tienes algunos versículos que podrían traerte algo de paz:",
            "Algunos pasajes sobre cambiar la preocupación por la paz:",
        ],
        "Angry": [
            "Aquí tienes algunos versículos que podrían ayudarte a procesar eso:",
            "Algunos pasajes sobre cómo manejar bien el enojo:",
        ],
        "Lonely": [
            "Aquí tienes algunos versículos que te recuerdan que nunca estás verdaderamente solo/a:",
            "Algunos pasajes sobre la presencia de Dios incluso en el aislamiento:",
        ],
        "Grateful": [
            "Aquí tienes algunos versículos para celebrar esa gratitud contigo:",
            "Algunos pasajes sobre la gratitud:",
        ],
        "Hopeful": [
            "Aquí tienes algunos versículos para animar aún más esa esperanza:",
            "Algunos pasajes sobre una esperanza que se mantiene firme:",
        ],
        "Seeking Guidance": [
            "Aquí tienes algunos versículos sobre buscar dirección:",
            "Algunos pasajes sobre encontrar guía:",
        ],
        "Joyful": [
            "Aquí tienes algunos versículos para celebrar esa buena vibra contigo:",
            "Algunos pasajes sobre la alegría:",
        ],
    },
}

CLOSING_LINES = {
    "en": {
        "Weary": [
            "Take it slow today -- rest is allowed.",
            "You don't have to carry all of it at once. Be gentle with yourself.",
        ],
        "Grieving": [
            "Take your time with this. Healing isn't a straight line, and that's okay.",
            "You don't have to be okay right away. Sit with it as long as you need.",
        ],
        "Afraid": [
            "One step at a time -- you don't have to face it all today.",
            "Courage doesn't mean not being scared, just moving forward anyway.",
        ],
        "Anxious": [
            "Try to take a breath -- you don't have to solve everything right now.",
            "One thing at a time. You've got more steadiness in you than it feels like.",
        ],
        "Angry": [
            "It's okay to feel this and still choose how you respond.",
            "Give yourself a little space before deciding what's next.",
        ],
        "Lonely": [
            "You're more surrounded than it might feel like right now.",
            "Reaching out to just one person today might help more than it seems.",
        ],
        "Grateful": [
            "Hold onto that feeling -- it's worth noticing.",
            "That gratitude is a good anchor for the rest of your day.",
        ],
        "Hopeful": [
            "Keep leaning into that hope -- it's well placed.",
            "That optimism is worth holding onto.",
        ],
        "Seeking Guidance": [
            "Clarity often comes one step at a time, not all at once. Be patient with the process.",
            "Trust that you don't have to have it all figured out today.",
        ],
        "Joyful": [
            "Enjoy this one -- moments like this are worth savoring.",
            "Hold onto that joy today.",
        ],
    },
    "es": {
        "Weary": [
            "Ve despacio hoy -- descansar está permitido.",
            "No tienes que cargar con todo a la vez. Sé amable contigo mismo/a.",
        ],
        "Grieving": [
            "Tómate tu tiempo con esto. Sanar no es una línea recta, y está bien.",
            "No tienes que estar bien de inmediato. Siéntelo el tiempo que necesites.",
        ],
        "Afraid": [
            "Un paso a la vez -- no tienes que enfrentarlo todo hoy.",
            "El valor no significa no tener miedo, sino seguir adelante de todos modos.",
        ],
        "Anxious": [
            "Intenta respirar -- no tienes que resolverlo todo ahora mismo.",
            "Una cosa a la vez. Tienes más firmeza en ti de lo que parece.",
        ],
        "Angry": [
            "Está bien sentir esto y aun así elegir cómo respondes.",
            "Date un poco de espacio antes de decidir qué sigue.",
        ],
        "Lonely": [
            "Estás más rodeado/a de lo que podría sentirse ahora mismo.",
            "Buscar a una sola persona hoy podría ayudar más de lo que parece.",
        ],
        "Grateful": [
            "Aférrate a ese sentimiento -- vale la pena notarlo.",
            "Esa gratitud es un buen ancla para el resto de tu día.",
        ],
        "Hopeful": [
            "Sigue apoyándote en esa esperanza -- está bien puesta.",
            "Ese optimismo vale la pena conservarlo.",
        ],
        "Seeking Guidance": [
            "La claridad a menudo llega paso a paso, no toda de una vez. Ten paciencia con el proceso.",
            "Confía en que no tienes que tenerlo todo resuelto hoy.",
        ],
        "Joyful": [
            "Disfruta este momento -- vale la pena saborear momentos así.",
            "Aférrate a esa alegría hoy.",
        ],
    },
}

# --- Suggested books to close out the conversation, based on the last mood discussed ---
BOOK_RECS = {
    "en": {
        "Weary": [
            ("Psalms", "honest, prayer-like poetry for tired seasons"),
            ("Matthew 11-12", "Jesus's own invitation to rest"),
        ],
        "Grieving": [
            ("Psalms", "especially the psalms of lament -- honest grief brought straight to God"),
            ("Lamentations", "written for exactly this kind of loss"),
            ("John 11", "Jesus grieving alongside Mary and Martha"),
        ],
        "Afraid": [
            ("Joshua", "God's repeated command to 'be strong and courageous'"),
            ("Psalms 27 & 91", "some of the most direct promises of protection in Scripture"),
        ],
        "Anxious": [
            ("Philippians", "Paul's own words on peace that guards your heart, written from prison"),
            ("Matthew 6", "Jesus teaching directly on worry"),
        ],
        "Angry": [
            ("Proverbs", "practical wisdom on anger and self-control"),
            ("James", "short and direct about taming what we say and feel"),
        ],
        "Lonely": [
            ("Psalms", "David's honesty about feeling forgotten -- and not forgotten"),
            ("Ruth", "a story about loyalty and never truly being alone"),
        ],
        "Grateful": [
            ("Psalms", "especially the psalms of praise and thanksgiving"),
            ("1 Thessalonians", "short, warm, and full of gratitude"),
        ],
        "Hopeful": [
            ("Romans 8", "on hope that doesn't disappoint"),
            ("Lamentations 3", "where hope shows up right in the middle of grief"),
        ],
        "Seeking Guidance": [
            ("Proverbs", "practical wisdom for everyday decisions"),
            ("James 1", "on asking God for wisdom"),
        ],
        "Joyful": [
            ("Psalms", "songs of celebration and praise"),
            ("Philippians", "Paul's letter about joy, written from prison"),
        ],
    },
    "es": {
        "Weary": [
            ("Salmos", "poesía honesta y como en oración para temporadas de cansancio"),
            ("Mateo 11-12", "la propia invitación de Jesús al descanso"),
        ],
        "Grieving": [
            ("Salmos", "especialmente los salmos de lamento -- dolor honesto llevado directamente a Dios"),
            ("Lamentaciones", "escrito exactamente para este tipo de pérdida"),
            ("Juan 11", "Jesús llorando junto a María y Marta"),
        ],
        "Afraid": [
            ("Josué", "el mandato repetido de Dios de 'esforzarte y ser valiente'"),
            ("Salmos 27 y 91", "algunas de las promesas de protección más directas en las Escrituras"),
        ],
        "Anxious": [
            ("Filipenses", "las propias palabras de Pablo sobre la paz que guarda tu corazón, escritas desde la prisión"),
            ("Mateo 6", "la enseñanza directa de Jesús sobre la preocupación"),
        ],
        "Angry": [
            ("Proverbios", "sabiduría práctica sobre el enojo y el dominio propio"),
            ("Santiago", "breve y directo sobre dominar lo que decimos y sentimos"),
        ],
        "Lonely": [
            ("Salmos", "la honestidad de David sobre sentirse olvidado -- y no olvidado"),
            ("Rut", "una historia sobre la lealtad y el nunca estar verdaderamente solo/a"),
        ],
        "Grateful": [
            ("Salmos", "especialmente los salmos de alabanza y acción de gracias"),
            ("1 Tesalonicenses", "breve, cálida y llena de gratitud"),
        ],
        "Hopeful": [
            ("Romanos 8", "sobre una esperanza que no decepciona"),
            ("Lamentaciones 3", "donde la esperanza aparece justo en medio del dolor"),
        ],
        "Seeking Guidance": [
            ("Proverbios", "sabiduría práctica para las decisiones cotidianas"),
            ("Santiago 1", "sobre pedirle sabiduría a Dios"),
        ],
        "Joyful": [
            ("Salmos", "cánticos de celebración y alabanza"),
            ("Filipenses", "la carta de Pablo sobre la alegría, escrita desde la prisión"),
        ],
    },
}

CLOSING_HOPE_MESSAGES = {
    "en": [
        "Whatever today held, you're not walking through it alone. I hope these words stay with you.",
        "Thanks for sharing a piece of your day with me. Whatever comes next, there's hope waiting for you in every season.",
        "Take care of yourself out there. I hope you felt a little less alone in this, even for a few minutes.",
        "However this week goes, I hope you come back to these verses again when you need them.",
    ],
    "es": [
        "Pase lo que pase hoy, no estás caminando por esto solo/a. Espero que estas palabras se queden contigo.",
        "Gracias por compartir un poco de tu día conmigo. Venga lo que venga después, hay esperanza esperándote en cada temporada.",
        "Cuídate mucho. Espero que te hayas sentido un poco menos solo/a en esto, aunque sea por unos minutos.",
        "Como sea que vaya esta semana, espero que vuelvas a estos versículos cuando los necesites.",
    ],
}

# --- All fixed UI chrome text ---
UI = {
    "en": {
        "app_title": "🌱 The Growing Faith App",
        "bible_caption": "Verses drawn from the World English Bible (WEB), a free modern public-domain translation.",
        "language_label": "Language",
        "testament_label": "Which part of Scripture would you like verses from?",
        "testament_placeholder": "Select choice.",
        "mood_label": "How are you feeling?",
        "mood_placeholder": "Select choice.",
        "sidebar_header": "🌱 Growing Faith",
        "start_over": "Start over",
        "spinner_finding_verses": "Finding verses for you...",
        "spinner_finding_more": "Finding a few more...",
        "spinner_context": "Pulling up the context around {ref}...",
        "default_closing": "Hope this helps a little.",
        "context_question": "**Would you like more context on one of these verses?**",
        "context_yes": "Yes, show me more",
        "context_no": "No, I'm good",
        "context_pick_label": "Which verse would you like more context on?",
        "context_pick_placeholder": "Select choice.",
        "whats_next": "**What would you like to do next?**",
        "more_verses_btn": "📖 More verses",
        "all_done_btn": "✅ All done",
        "verse_load_error": "*(couldn't load the text just now -- look this one up!)*",
        "context_intro": "Here's more of **{book_chapter}** surrounding **{reference}**, for a fuller picture:",
        "context_load_error": "_(Couldn't load the surrounding verses just now -- try again in a moment.)_",
        "more_verses_intro": "Sure -- here are a few more:",
        "all_verses_shared": "I've actually shared every {mood} verse I've got saved for that testament setting!",
        "end_message_with_books": "Before you go, here are a couple of books of the Bible worth spending more time in, given how you've been feeling:",
        "end_message_default": "Before you go, **Psalms** and the **Gospel of John** are always a good place to start -- honest prayers for whatever you're carrying, and a close look at who Jesus is.",
        "footer_caption": "{n} curated references across {m} moods. Scripture text: World English Bible (Public Domain), via bible-api.com.",
    },
    "es": {
        "app_title": "🌱 La App de Fe Creciente",
        "bible_caption": "Los versículos provienen de la Reina-Valera 1909 (RV1909), una traducción histórica de dominio público.",
        "language_label": "Idioma",
        "testament_label": "¿De qué parte de las Escrituras te gustaría recibir versículos?",
        "testament_placeholder": "Selecciona una opción.",
        "mood_label": "¿Cómo te sientes?",
        "mood_placeholder": "Selecciona una opción.",
        "sidebar_header": "🌱 Fe Creciente",
        "start_over": "Empezar de nuevo",
        "spinner_finding_verses": "Buscando versículos para ti...",
        "spinner_finding_more": "Buscando algunos más...",
        "spinner_context": "Buscando el contexto alrededor de {ref}...",
        "default_closing": "Espero que esto ayude un poco.",
        "context_question": "**¿Te gustaría tener más contexto sobre alguno de estos versículos?**",
        "context_yes": "Sí, muéstrame más",
        "context_no": "No, estoy bien así",
        "context_pick_label": "¿Sobre qué versículo te gustaría tener más contexto?",
        "context_pick_placeholder": "Selecciona una opción.",
        "whats_next": "**¿Qué te gustaría hacer ahora?**",
        "more_verses_btn": "📖 Más versículos",
        "all_done_btn": "✅ Ya terminé",
        "verse_load_error": "*(no se pudo cargar el texto en este momento -- ¡búscalo tú mismo/a!)*",
        "context_intro": "Aquí tienes más de **{book_chapter}** alrededor de **{reference}**, para un panorama más completo:",
        "context_load_error": "_(No se pudieron cargar los versículos circundantes en este momento -- inténtalo de nuevo en un momento.)_",
        "more_verses_intro": "Claro -- aquí tienes algunos más:",
        "all_verses_shared": "¡Ya te he compartido todos los versículos que tengo guardados para este estado de ánimo con esa configuración de Testamento!",
        "end_message_with_books": "Antes de que te vayas, aquí tienes un par de libros de la Biblia que vale la pena explorar más, dado cómo te has estado sintiendo:",
        "end_message_default": "Antes de que te vayas, **Salmos** y el **Evangelio de Juan** siempre son un buen punto de partida -- oraciones honestas para lo que sea que estés cargando, y una mirada cercana a quién es Jesús.",
        "footer_caption": "{n} referencias curadas en {m} estados de ánimo. Texto bíblico: Reina-Valera 1909 (dominio público), vía bible.helloao.org.",
    },
}


def sample_verses(data: pd.DataFrame, mood: str, testament_choice: str, n: int = 5):
    """Samples verses for a mood, preferring ones not already shown this session so a
    follow-up 'give me more verses' request surfaces new material instead of repeats."""
    pool = data[data["mood"] == mood]
    if testament_choice != "Both":
        narrowed = pool[pool["testament"] == testament_choice]
        if not narrowed.empty:
            pool = narrowed

    shown = st.session_state.get("shown_refs", set())
    unseen = pool[~pool["reference"].isin(shown)]
    use_pool = unseen if not unseen.empty else pool

    sample = use_pool.sample(min(n, len(use_pool)))
    st.session_state.shown_refs = shown | set(sample["reference"])
    return sample


def has_unseen_verses(data: pd.DataFrame, mood: str, testament_choice: str) -> bool:
    pool = data[data["mood"] == mood]
    if testament_choice != "Both":
        narrowed = pool[pool["testament"] == testament_choice]
        if not narrowed.empty:
            pool = narrowed
    shown = st.session_state.get("shown_refs", set())
    return not pool[~pool["reference"].isin(shown)].empty


def format_verses_markdown(sample_df: pd.DataFrame, lang: str) -> str:
    blocks = []
    for _, row in sample_df.iterrows():
        text = fetch_verse_text(row["reference"], lang)
        display_ref = localize_reference(row["reference"], lang)
        if text:
            blocks.append(f"> *{text}*\n>\n> -- **{display_ref}**")
        else:
            blocks.append(f"> **{display_ref}** {UI[lang]['verse_load_error']}")
    return "\n\n".join(blocks)


def build_context_markdown(reference: str, lang: str) -> str:
    parsed = parse_reference(reference)
    if parsed:
        book, chapter = parsed[0], parsed[1]
        book_display = BOOK_INFO[book.lower()][1] if lang == "es" and book.lower() in BOOK_INFO else book
        book_chapter = f"{book_display} {chapter}"
    else:
        book_chapter = localize_reference(reference, lang)

    context_text, context_ref = fetch_context(reference, lang, margin=10)
    if context_text:
        passage_block = f"> *{context_text}*\n>\n> -- **{localize_reference(context_ref, lang)}**"
    else:
        passage_block = UI[lang]["context_load_error"]

    intro = UI[lang]["context_intro"].format(
        book_chapter=book_chapter, reference=localize_reference(reference, lang)
    )
    return f"{intro}\n\n{passage_block}"


CELEBRATION_EMOJIS = {
    "Joyful": "😊🎉✨🙌😄",
    "Grateful": "🙏✨💛😊",
    "Hopeful": "🌟✨🙌😊",
}


def show_celebration(emoji_set: str, count: int = 10):
    """Floats a handful of emoji up the screen -- a little extra spark for good-news moods."""
    spans = "".join(
        f'<span class="float-emoji" style="left:{4 + i * (92 // max(count - 1, 1))}%; '
        f'animation-delay:{i * 0.12:.2f}s;">{e}</span>'
        for i, e in enumerate(random.choices(emoji_set, k=count))
    )
    st.markdown(
        f"""
        <style>
        .float-emoji-container {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 9999; overflow: hidden;
        }}
        .float-emoji {{
            position: absolute; bottom: -10%; font-size: 2rem; opacity: 0;
            animation: float-up 3.2s ease-in forwards;
        }}
        @keyframes float-up {{
            0% {{ transform: translateY(0) rotate(0deg); opacity: 0; }}
            12% {{ opacity: 1; }}
            100% {{ transform: translateY(-110vh) rotate(20deg); opacity: 0; }}
        }}
        </style>
        <div class="float-emoji-container">{spans}</div>
        """,
        unsafe_allow_html=True,
    )


def run_mood_response(mood: str):
    ack_reply = random.choice(ACK_VARIANTS[LANG][mood])

    if mood in CELEBRATION_EMOJIS:
        show_celebration(CELEBRATION_EMOJIS[mood])

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(ack_reply)
    st.session_state.messages.append({"role": "assistant", "content": ack_reply})

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner(UI[LANG]["spinner_finding_verses"]):
            sample = sample_verses(df, mood, testament_choice, n=5)
            verses_md = format_verses_markdown(sample, LANG)
        closing = random.choice(CLOSING_LINES[LANG].get(mood, [UI[LANG]["default_closing"]]))
        verses_reply = f"{random.choice(TRANSITION_VARIANTS[LANG][mood])}\n\n{verses_md}\n\n{closing}"
        st.markdown(verses_reply)
    st.session_state.messages.append({"role": "assistant", "content": verses_reply})

    st.session_state.last_mood = mood
    st.session_state.last_refs = list(sample["reference"])
    st.session_state.conversation_wrapped = False
    st.session_state.context_stage = "ask"
    st.session_state.context_available = True
    st.session_state.final_round = False


def handle_more_verses():
    """Button-triggered: shows a fresh batch of verses. The 'want more context?' question
    only ever gets offered once total -- if it's still unused (they said no on the first
    batch), this batch is the last chance for it and always ends in the closing prompt
    afterward. If it was already used on the first batch, this batch skips straight to the
    closing prompt with no context question."""
    mood = st.session_state.last_mood
    if has_unseen_verses(df, mood, testament_choice):
        sample = sample_verses(df, mood, testament_choice, n=5)
        verses_md = format_verses_markdown(sample, LANG)
        reply = f"{UI[LANG]['more_verses_intro']}\n\n{verses_md}"
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.last_refs = list(sample["reference"])

        if st.session_state.get("context_available"):
            st.session_state.context_stage = "ask"
            st.session_state.final_round = True
        else:
            st.session_state.messages.append(
                {"role": "assistant", "content": compute_end_message()}
            )
            st.session_state.conversation_wrapped = True
    else:
        mood_display = mood.lower() if LANG == "en" else MOOD_LABELS[LANG][mood]
        reply = UI[LANG]["all_verses_shared"].format(mood=mood_display)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.messages.append({"role": "assistant", "content": compute_end_message()})
        st.session_state.conversation_wrapped = True


def compute_end_message() -> str:
    mood = st.session_state.get("last_mood")
    book_recs = BOOK_RECS[LANG]
    if mood and mood in book_recs:
        recs_md = "\n".join(f"- **{book}** -- {why}" for book, why in book_recs[mood])
        body = f"{UI[LANG]['end_message_with_books']}\n\n{recs_md}"
    else:
        body = UI[LANG]["end_message_default"]
    return f"{body}\n\n{random.choice(CLOSING_HOPE_MESSAGES[LANG])}"


# --- Header ---
st.title(UI[LANG]["app_title"])
st.caption(UI[LANG]["bible_caption"])

# A counter baked into each reset-able widget's key. Bumping it on "Start over" forces
# Streamlit to treat the selectboxes as brand-new widgets, which is the reliable way to
# clear a selectbox back to its placeholder -- popping the old key alone doesn't always
# take visually, since the frontend can keep reusing the same widget instance.
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
rc = st.session_state.reset_counter

testament_choice = st.selectbox(
    UI[LANG]["testament_label"],
    ["Both", "Old Testament", "New Testament"],
    index=None,
    placeholder=UI[LANG]["testament_placeholder"],
    format_func=lambda v: TESTAMENT_LABELS[LANG][v],
    key=f"testament_choice_{rc}",
)
if testament_choice is None:
    testament_choice = "Both"

df = load_reference_data()

# --- Chat state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if st.session_state.get("greeting_lang") != LANG:
    st.session_state.greeting = random.choice(GREETINGS[LANG])
    st.session_state.greeting_lang = LANG

# Everything that makes up "where the user is" in the conversation -- wiped on "Start over"
# so they land on a truly clean slate. Language is deliberately NOT included here -- it's
# a standing preference, not conversation state.
RESET_STATE_KEYS = [
    "messages", "greeting", "greeting_lang", "last_mood", "last_refs", "shown_refs",
    "conversation_wrapped", "context_stage", "context_available", "final_round",
]

with st.sidebar:
    st.selectbox(UI[LANG]["language_label"], ["English", "Español"], key="language")
    st.subheader(UI[LANG]["sidebar_header"])
    if st.button(UI[LANG]["start_over"], use_container_width=True):
        for key in RESET_STATE_KEYS:
            st.session_state.pop(key, None)
        st.session_state.reset_counter = rc + 1
        st.rerun()

for msg in st.session_state.messages:
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- The greeting and the mood picker both disappear for good once a mood has been
#     chosen -- only "Start over" brings them back. ---
if not st.session_state.get("last_mood"):
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(st.session_state.greeting)

    quick_mood = st.selectbox(
        UI[LANG]["mood_label"],
        MOOD_ORDER,
        index=None,
        placeholder=UI[LANG]["mood_placeholder"],
        format_func=lambda m: MOOD_LABELS[LANG][m],
        key=f"quick_mood_choice_{rc}",
    )
    if quick_mood:
        run_mood_response(quick_mood)
        st.rerun()

# --- Everything past the initial mood pick is button driven. Both paths lead to the same
#     closing prompt -- this is a one-round follow-up, not an open-ended loop. ---
if st.session_state.get("last_refs") and not st.session_state.get("conversation_wrapped"):
    context_stage = st.session_state.get("context_stage", "ask")

    # --- Step 1: ask whether they want more context on one of the verses just shown.
    #     This question only ever gets asked once total (first batch, or -- if skipped
    #     there -- the second batch). Whichever batch it lands on, "No" here spends that
    #     one-time opportunity. ---
    if context_stage == "ask":
        st.markdown(UI[LANG]["context_question"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button(UI[LANG]["context_yes"], use_container_width=True):
                st.session_state.context_stage = "choose"
                st.rerun()
        with col2:
            if st.button(UI[LANG]["context_no"], use_container_width=True):
                if st.session_state.get("final_round"):
                    st.session_state.context_available = False
                    st.session_state.messages.append(
                        {"role": "assistant", "content": compute_end_message()}
                    )
                    st.session_state.conversation_wrapped = True
                else:
                    st.session_state.context_stage = "resolved"
                st.rerun()

    # --- Step 2: let them pick which verse, then show the surrounding passage ---
    elif context_stage == "choose":
        chosen = st.selectbox(
            UI[LANG]["context_pick_label"],
            st.session_state.last_refs,
            index=None,
            placeholder=UI[LANG]["context_pick_placeholder"],
            format_func=lambda r: localize_reference(r, LANG),
            key=f"context_pick_{rc}",
        )
        if chosen:
            with st.spinner(UI[LANG]["spinner_context"].format(ref=localize_reference(chosen, LANG))):
                context_md = build_context_markdown(chosen, LANG)
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                st.markdown(context_md)
            st.session_state.messages.append({"role": "assistant", "content": context_md})
            st.session_state.context_available = False

            if st.session_state.get("final_round"):
                st.session_state.messages.append(
                    {"role": "assistant", "content": compute_end_message()}
                )
                st.session_state.conversation_wrapped = True
            else:
                st.session_state.context_stage = "resolved"
            st.rerun()

    # --- Step 3: whichever path they took, land on the same "what's next" prompt ---
    if context_stage == "resolved":
        st.markdown(UI[LANG]["whats_next"])
        col1, col2 = st.columns(2)
        with col1:
            more_available = has_unseen_verses(df, st.session_state.last_mood, testament_choice)
            if st.button(UI[LANG]["more_verses_btn"], use_container_width=True, disabled=not more_available):
                with st.spinner(UI[LANG]["spinner_finding_more"]):
                    handle_more_verses()
                st.rerun()
        with col2:
            if st.button(UI[LANG]["all_done_btn"], use_container_width=True):
                st.session_state.messages.append(
                    {"role": "assistant", "content": compute_end_message()}
                )
                st.session_state.conversation_wrapped = True
                st.rerun()

st.divider()
st.caption(UI[LANG]["footer_caption"].format(n=len(df), m=df["mood"].nunique()))
