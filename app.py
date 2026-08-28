import streamlit as st
import whisper
import difflib
import re
import tempfile
import os

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="SwaraSetu-RBSK", page_icon="🎙️", layout="centered")

# ---------- CORE LOGIC (same tested engine from Day 1) ----------
def clean_and_tokenize(text):
    text = re.sub(r'[^\w\s]', '', text.lower())
    return text.split()

def analyze_reading(expected_text, actual_transcript, flag_threshold=0.15):
    expected_words = clean_and_tokenize(expected_text)
    actual_words = clean_and_tokenize(actual_transcript)
    matcher = difflib.SequenceMatcher(None, expected_words, actual_words)

    skipped_words, substituted_words, added_words = [], [], []
    # word_errors counts actual WORDS affected, not the number of
    # mismatched blocks - a single block spanning 20 words must count
    # as 20 errors, not 1.
    word_errors = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'delete':
            skipped = expected_words[i1:i2]
            skipped_words.extend(skipped)
            word_errors += len(skipped)
        elif tag == 'replace':
            exp_slice = expected_words[i1:i2]
            act_slice = actual_words[j1:j2]
            substituted_words.append({'expected': ' '.join(exp_slice),
                                       'actual': ' '.join(act_slice)})
            # a replace block is at least as wrong as the longer side -
            # e.g. 24 expected words replaced by 2 actual words is 24
            # errors, not 1.
            word_errors += max(len(exp_slice), len(act_slice))
        elif tag == 'insert':
            added = actual_words[j1:j2]
            added_words.extend(added)
            word_errors += len(added)

    total_expected = len(expected_words)
    error_rate = word_errors / total_expected if total_expected else 1.0

    # Sanity guard: if the reading is dramatically shorter than expected,
    # this is not a valid attempt at the passage - flag it outright rather
    # than let a short clip look "accurate" by having few words to compare.
    coverage = len(actual_words) / total_expected if total_expected else 0
    if coverage < 0.5:
        flag = "NEEDS A CLOSER LOOK"
        error_rate = max(error_rate, 1 - coverage)
    else:
        flag = "NEEDS A CLOSER LOOK" if error_rate > flag_threshold else "NORMAL"

    return {
        "flag": flag,
        "error_rate_percent": round(min(error_rate, 1.0) * 100, 1),
        "skipped_words": skipped_words,
        "substituted_words": substituted_words,
        "added_words": added_words,
    }

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

# ---------- UI ----------
st.title("🎙️ SwaraSetu-RBSK")
st.caption("A 90-second AI reading check — built into a visit that already happens.")

# Age-appropriate passages: reading demand needs to match age, or a
# child can be wrongly flagged just for developmental stage, not a
# real reading concern. Multiple equivalent-difficulty variants per
# age band so the SAME child isn't shown the identical passage every
# year - reduces memorization while keeping difficulty standardized.
AGE_PASSAGES = {
    "6–9 years (short passage)": {
        "variants": [
            "The sun was bright in the sky. A little dog ran across the green field. He saw a red ball near the old tree.",
            "The rain fell on the small house. A young cat sat by the warm fire. She heard a loud sound near the front door.",
            "The moon was high above the hill. A brown goat walked past the old fence. It found a soft leaf near the tall grass.",
        ],
        "note": "~60–90 sec reading task",
    },
    "9+ years (longer passage)": {
        "variants": [
            "The sun was bright in the sky. A little dog ran across the green field, chasing a butterfly. He saw a red ball near the old tree and stopped to pick it up before running home.",
            "The wind was strong near the coast. A tall ship sailed across the calm sea, carrying fresh fruit. The sailors saw dark clouds forming and quickly turned back toward the harbor.",
        ],
        "note": "~90 sec reading task",
    },
    "3–6 years (word list only)": {
        "variants": [
            "cat dog sun ball tree run big red",
            "cow hen cup pen box top mat sit",
            "fox hat map pot bus fan wet six",
        ],
        "note": "~20–30 sec, simple word list, not a full passage",
    },
}

if "session_id" not in st.session_state:
    st.session_state.session_id = 0

# Defensive guard: if an older version of this app left session_log as
# a list (previous format) in this browser's cached state, reset it to
# the current dict format instead of crashing.
if "session_log" in st.session_state and not isinstance(st.session_state.session_log, dict):
    st.session_state.session_log = {}

st.markdown(
    """
    <style>
    div.stButton > button, div.stFormSubmitButton > button {
        font-size: 1.15rem !important;
        padding: 0.7rem 1.2rem !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_a, col_b = st.columns([3, 1])
with col_a:
    age_group = st.selectbox("👤 Child's age group:", list(AGE_PASSAGES.keys()))
with col_b:
    st.write("")
    st.write("")
    if st.button("🔄 New Child"):
        st.session_state.session_id += 1
        st.rerun()

import random

# Pick a passage variant for THIS child (stable during their turn,
# changes automatically for the next child via session_id + age_group).
passage_key = f"passage_{st.session_state.session_id}_{age_group}"
if passage_key not in st.session_state:
    st.session_state[passage_key] = random.choice(AGE_PASSAGES[age_group]["variants"])
EXPECTED_PASSAGE = st.session_state[passage_key]

st.markdown(
    f"""
    <div style="
        background-color:#FFF8E1;
        border-radius:20px;
        padding:32px 28px;
        margin:16px 0 8px 0;
        border:3px solid #FFD54F;
        text-align:center;
    ">
        <p style="font-size:1.1rem;color:#8D6E00;margin:0 0 12px 0;font-weight:600;">
            📖 Read this out loud
        </p>
        <p style="
            font-size:2.1rem;
            line-height:1.5;
            color:#3E2C00;
            font-weight:700;
            margin:0;
            font-family: 'Comic Sans MS', 'Trebuchet MS', sans-serif;
        ">
            {EXPECTED_PASSAGE}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(AGE_PASSAGES[age_group]["note"])

st.markdown("### 🎤 Now record the reading")
audio_file = st.file_uploader(
    "Upload an audio file (mp3, wav, m4a)",
    type=["mp3", "wav", "m4a", "mp4"],
    key=f"uploader_{st.session_state.session_id}",
)
recorded_audio = st.audio_input(
    "...or record directly here",
    key=f"recorder_{st.session_state.session_id}",
)

audio_to_process = audio_file if audio_file else recorded_audio

if audio_to_process is not None:
    # Custom player with the browser's download option disabled -
    # we preview the recording so the user can confirm it, but we
    # never expose a download path for the child's audio.
    import base64
    audio_bytes = audio_to_process.getvalue()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio controls controlsList="nodownload noplaybackrate"
               oncontextmenu="return false;" style="width:100%">
            <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
        </audio>
        <p style="font-size:0.8em;color:gray;">
        🔒 Preview only — this recording is processed in-memory and is not stored or downloadable.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔍 Check Reading", type="primary"):
        with st.spinner("AI is listening and checking the pattern..."):
            # Save uploaded/recorded audio to a temp file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio_to_process.getvalue())
                tmp_path = tmp.name

            model = load_whisper_model()
            result = model.transcribe(tmp_path)
            actual_transcript = result["text"]
            os.remove(tmp_path)

            report = analyze_reading(EXPECTED_PASSAGE, actual_transcript)

        st.markdown("### Result")
        st.markdown(f"**What the AI heard:** _{actual_transcript}_")

        if report["flag"] == "NORMAL":
            st.success(f"✅ NORMAL — {report['error_rate_percent']}% variation from expected reading")
        else:
            st.warning(f"⚠️ NEEDS A CLOSER LOOK — {report['error_rate_percent']}% variation from expected reading")

        col1, col2 = st.columns(2)
        with col1:
            if report["skipped_words"]:
                st.write("**Skipped words:**")
                st.write(", ".join(report["skipped_words"]))
        with col2:
            if report["substituted_words"]:
                st.write("**Substitutions:**")
                for sub in report["substituted_words"]:
                    st.write(f"'{sub['expected']}' → '{sub['actual']}'")

        st.divider()
        st.caption("⚕️ This is a pre-filter only. Every flagged case would be confirmed by a real human specialist at DEIC. The AI never diagnoses on its own.")

        # Log this result to the session's running summary (no audio,
        # no name - just flag + age group + time). Only ONE row per
        # child: re-clicking "Check Reading" for the SAME child (before
        # hitting Reset) updates that child's row instead of adding a
        # new one each time.
        if "session_log" not in st.session_state:
            st.session_state.session_log = {}  # keyed by session_id
        import datetime
        st.session_state.session_log[st.session_state.session_id] = {
            "Child #": st.session_state.session_id + 1,
            "Time": datetime.datetime.now().strftime("%H:%M:%S"),
            "Age group": age_group,
            "Result": report["flag"],
            "Variation": f"{report['error_rate_percent']}%",
        }
else:
    st.caption("👆 Upload or record a reading above to run the check.")

# ---------- SESSION SUMMARY (today's checks so far, no audio/names stored) ----------
if st.session_state.get("session_log"):
    st.divider()
    st.markdown("### 📋 Today's session summary")
    st.caption("No audio or names are stored — only the result and time, cleared when the page is closed.")
    log_rows = list(st.session_state.session_log.values())
    st.table(log_rows)
    normal_count = sum(1 for r in log_rows if r["Result"] == "NORMAL")
    flagged_count = len(log_rows) - normal_count
    c1, c2, c3 = st.columns(3)
    c1.metric("Children checked", len(log_rows))
    c2.metric("Normal", normal_count)
    c3.metric("Needs a closer look", flagged_count)

st.divider()
st.caption("Built for NexHack 2.0 — Team Protectech")
