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
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'delete':
            skipped_words.extend(expected_words[i1:i2])
        elif tag == 'replace':
            substituted_words.append({'expected': ' '.join(expected_words[i1:i2]),
                                       'actual': ' '.join(actual_words[j1:j2])})
        elif tag == 'insert':
            added_words.extend(actual_words[j1:j2])

    total_expected = len(expected_words)
    total_errors = len(skipped_words) + len(substituted_words) + len(added_words)
    error_rate = total_errors / total_expected if total_expected else 0
    flag = "NEEDS A CLOSER LOOK" if error_rate > flag_threshold else "NORMAL"

    return {
        "flag": flag,
        "error_rate_percent": round(error_rate * 100, 1),
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
    st.audio(audio_to_process)

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
st.caption("Built for Vision to Venture 2.0 & NexHack 2.0 — Team Ctrl AI")
