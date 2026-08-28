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

EXPECTED_PASSAGE = "The sun was bright in the sky. A little dog ran across the green field. He saw a red ball near the old tree."

st.markdown("### Step 1 — Read this passage aloud")
st.info(EXPECTED_PASSAGE)

st.markdown("### Step 2 — Upload or record your reading")
audio_file = st.file_uploader("Upload an audio file (mp3, wav, m4a)", type=["mp3", "wav", "m4a", "mp4"])

# Streamlit's built-in mic recorder (works in most modern browsers)
recorded_audio = st.audio_input("...or record directly here")

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
else:
    st.caption("👆 Upload or record a reading above to run the check.")

st.divider()
st.caption("Built for NexHack 2.0 — Team Protectech")
