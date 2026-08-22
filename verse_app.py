import random
import re

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="The Growing Faith App", page_icon="🌱", layout="centered")

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


def book_from_reference(reference: str) -> str:
    return re.sub(r"\s\d+(:\d+(-\d+)?)?$", "", reference).strip()


def classify_testament(reference: str) -> str:
    book = book_from_reference(reference).lower()
    if book in OT_BOOKS:
        return "Old Testament"
    if book in NT_BOOKS:
        return "New Testament"
    return "Unknown"


@st.cache_data
def load_reference_data():
    data = pd.read_csv("verses.csv")
    data["testament"] = data["reference"].apply(classify_testament)
    return data


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def fetch_verse_text(reference: str, translation: str = "web"):
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


# --- Moods, in the order they're offered in the picker ---
MOOD_ORDER = [
    "Weary", "Grieving", "Afraid", "Anxious", "Angry", "Lonely",
    "Grateful", "Hopeful", "Seeking Guidance", "Joyful",
]

# --- Varied response banks. Each list has several phrasings; one is picked at random
#     each time so the conversation doesn't feel like the same fixed script on repeat use. ---

GREETINGS = [
    "Hey -- how's your day going?",
    "Hi there! What's on your mind today?",
    "Hey! How are you feeling right now?",
    "Welcome back -- how's everything going today?",
]

ACK_VARIANTS = {
    "Weary": [
        "That sounds like a lot to carry -- it makes sense you're feeling worn out.",
        "Running on empty is rough. No wonder you're tired.",
        "Sounds like you're pouring from an empty cup right now.",
    ],
    "Grieving": [
        "I'm really sorry you're going through that. That kind of pain is heavy.",
        "That sounds so hard. I'm sorry you're carrying that.",
        "Losses like that leave a real ache. I'm sorry.",
    ],
    "Afraid": [
        "That sounds unsettling to sit with.",
        "Fear like that is exhausting on its own.",
        "That's a heavy thing to be facing right now.",
    ],
    "Anxious": [
        "That anxious feeling can be so exhausting to carry around.",
        "Worry has a way of taking over everything else. That sounds tough.",
        "That sounds like a lot of noise in your head right now.",
    ],
    "Angry": [
        "That's a valid thing to feel -- frustration and anger happen.",
        "That sounds genuinely frustrating.",
        "Makes sense you're upset about that.",
    ],
    "Lonely": [
        "I'm sorry you're feeling so alone right now.",
        "That isolated feeling is a hard one to sit with.",
        "Feeling unseen like that is tough. I'm sorry.",
    ],
    "Grateful": [
        "That's really beautiful to hear.",
        "I love that -- gratitude like that is worth noticing.",
        "That's a good place to be in.",
    ],
    "Hopeful": [
        "I love that you're feeling hopeful.",
        "That's a great feeling to hold onto.",
        "That kind of hope is worth savoring.",
    ],
    "Seeking Guidance": [
        "It makes sense to feel unsure -- big questions deserve some thought.",
        "Not knowing which way to go is uncomfortable. That's understandable.",
        "Decisions like that weigh on you. Makes sense you're feeling stuck.",
    ],
    "Joyful": [
        "That's awesome to hear!",
        "Love that energy!",
        "That's a great day to have.",
    ],
}

TRANSITION_VARIANTS = {
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
}

FOLLOWUP_PROMPTS = [
    "Want a few more verses, or are you all done for now?",
    "Would a few more verses help, or is this enough for today?",
    "I can pull a few more if you'd like, or we can leave it here for now.",
]

CLOSING_LINES = {
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
}

# --- Suggested books to close out the conversation, based on the last mood discussed ---
BOOK_RECS = {
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
}

CLOSING_HOPE_MESSAGES = [
    "Whatever today held, you're not walking through it alone. I hope these words stay with you.",
    "Thanks for sharing a piece of your day with me. Whatever comes next, there's hope waiting for you in every season.",
    "Take care of yourself out there. I hope you felt a little less alone in this, even for a few minutes.",
    "However this week goes, I hope you come back to these verses again when you need them.",
]


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


def format_verses_markdown(sample_df: pd.DataFrame) -> str:
    blocks = []
    for _, row in sample_df.iterrows():
        text = fetch_verse_text(row["reference"])
        if text:
            blocks.append(f"> *{text}*\n>\n> -- **{row['reference']}**")
        else:
            blocks.append(f"> **{row['reference']}** *(couldn't load the text just now -- look this one up!)*")
    return "\n\n".join(blocks)


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
    ack_reply = random.choice(ACK_VARIANTS[mood])

    if mood in CELEBRATION_EMOJIS:
        show_celebration(CELEBRATION_EMOJIS[mood])

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(ack_reply)
    st.session_state.messages.append({"role": "assistant", "content": ack_reply})

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Finding verses for you..."):
            sample = sample_verses(df, mood, testament_choice, n=5)
            verses_md = format_verses_markdown(sample)
        closing = random.choice(CLOSING_LINES.get(mood, ["Hope this helps a little."]))
        follow_up = random.choice(FOLLOWUP_PROMPTS)
        verses_reply = (
            f"{random.choice(TRANSITION_VARIANTS[mood])}\n\n{verses_md}\n\n{closing}\n\n{follow_up}"
        )
        st.markdown(verses_reply)
    st.session_state.messages.append({"role": "assistant", "content": verses_reply})

    st.session_state.last_mood = mood
    st.session_state.last_refs = list(sample["reference"])
    st.session_state.conversation_wrapped = False


def handle_more_verses():
    """Button-triggered: shows a fresh batch of verses, then always wraps up with the
    closing prompt -- 'more verses' is a one-time ask, not another open-ended loop."""
    mood = st.session_state.last_mood
    if has_unseen_verses(df, mood, testament_choice):
        sample = sample_verses(df, mood, testament_choice, n=5)
        verses_md = format_verses_markdown(sample)
        reply = f"Sure -- here are a few more:\n\n{verses_md}"
        st.session_state.last_refs = list(sample["reference"])
    else:
        reply = (
            f"I've actually shared every {mood.lower()} verse I've got saved for that testament "
            f"setting!"
        )
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.messages.append({"role": "assistant", "content": compute_end_message()})
    st.session_state.conversation_wrapped = True


def compute_end_message() -> str:
    mood = st.session_state.get("last_mood")
    if mood and mood in BOOK_RECS:
        recs_md = "\n".join(f"- **{book}** -- {why}" for book, why in BOOK_RECS[mood])
        body = (
            "Before you go, here are a couple of books of the Bible worth spending more time in, "
            f"given how you've been feeling:\n\n{recs_md}"
        )
    else:
        body = (
            "Before you go, **Psalms** and the **Gospel of John** are always a good place to start -- "
            "honest prayers for whatever you're carrying, and a close look at who Jesus is."
        )
    return f"{body}\n\n{random.choice(CLOSING_HOPE_MESSAGES)}"


# --- Header ---
st.title("🌱 The Growing Faith App")
st.caption(
    "Verses drawn from the World English Bible (WEB), a free modern public-domain translation."
)

# A counter baked into each reset-able widget's key. Bumping it on "Start over" forces
# Streamlit to treat the selectboxes as brand-new widgets, which is the reliable way to
# clear a selectbox back to its placeholder -- popping the old key alone doesn't always
# take visually, since the frontend can keep reusing the same widget instance.
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
rc = st.session_state.reset_counter

testament_choice = st.selectbox(
    "Which part of Scripture would you like verses from?",
    ["Both", "Old Testament", "New Testament"],
    index=None,
    placeholder="Select choice.",
    key=f"testament_choice_{rc}",
)
if testament_choice is None:
    testament_choice = "Both"

df = load_reference_data()

# --- Chat state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "greeting" not in st.session_state:
    st.session_state.greeting = random.choice(GREETINGS)

# Everything that makes up "where the user is" in the conversation -- wiped on "Start over"
# so they land on a truly clean slate.
RESET_STATE_KEYS = [
    "messages", "greeting", "last_mood", "last_refs", "shown_refs", "conversation_wrapped",
]

with st.sidebar:
    st.subheader("🌱 Growing Faith")
    if st.button("Start over", use_container_width=True):
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
        "How are you feeling?",
        MOOD_ORDER,
        index=None,
        placeholder="Select choice.",
        key=f"quick_mood_choice_{rc}",
    )
    if quick_mood:
        run_mood_response(quick_mood)
        st.rerun()

# --- Everything past the initial mood pick is button driven. Both paths lead to the same
#     closing prompt -- this is a one-round follow-up, not an open-ended loop. ---
if st.session_state.get("last_refs") and not st.session_state.get("conversation_wrapped"):
    st.markdown("**What would you like to do next?**")
    col1, col2 = st.columns(2)
    with col1:
        more_available = has_unseen_verses(df, st.session_state.last_mood, testament_choice)
        if st.button("📖 More verses", use_container_width=True, disabled=not more_available):
            with st.spinner("Finding a few more..."):
                handle_more_verses()
            st.rerun()
    with col2:
        if st.button("✅ All done", use_container_width=True):
            st.session_state.messages.append(
                {"role": "assistant", "content": compute_end_message()}
            )
            st.session_state.conversation_wrapped = True
            st.rerun()

st.divider()
st.caption(
    f"{len(df)} curated references across {df['mood'].nunique()} moods. "
    "Scripture text: World English Bible (Public Domain), via bible-api.com."
)