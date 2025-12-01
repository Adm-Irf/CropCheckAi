from __future__ import annotations

import os
import tempfile
import time
from typing import Any, Dict

import streamlit as st
from jamaibase import JamAI, types as t

# ==============================
# Configuration
# ==============================

# You can hardcode, or read from environment variables.
DEFAULT_PROJECT_ID = os.getenv("JAMAI_PROJECT_ID", "proj_47c5d5e744b0953d71ba7748")
DEFAULT_PAT = os.getenv("JAMAI_PAT", "jamai_pat_4e67ed6cf6f873c79193c08f3369f907691e1e4f3bd53b95")

# Exact table IDs from your project
TABLE_DETECT = "1. Detect The Problem"
TABLE_FOLLOWUP = "2. Follow-Up Question"
TABLE_CAUSES = "3. Determine The Causes"
TABLE_SOLUTION = "4. Proposed Solution"
TABLE_FINAL = "5. Final Conclusion"


# ==============================
# Helpers
# ==============================

def get_client(project_id: str, pat: str) -> JamAI:
    if not project_id or not pat:
        raise RuntimeError("Project ID and PAT must be set.")
    return JamAI(project_id=project_id, token=pat)


def upload_to_jamai(client: JamAI, uploaded_file) -> str:
    """Upload a Streamlit UploadedFile to JamAI File API and return its URI."""
    suffix = os.path.splitext(uploaded_file.name)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        resp = client.file.upload_file(tmp_path)
        return getattr(resp, "uri", "")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def safe_text(cell: Any) -> str:
    try:
        return getattr(cell, "text", "") or ""
    except Exception:
        return ""


def type_out(text: str, placeholder, delay: float = 0.015) -> None:
    """Simple typing animation into a Streamlit placeholder."""
    buf = ""
    for ch in text:
        buf += ch
        placeholder.markdown(buf)
        time.sleep(delay)


def call_action_table(
    client: JamAI,
    table_id: str,
    data: Dict[str, Any],
    stream: bool = False,
) -> Dict[str, Any]:
    """Call one Action Table row and return dict of column_id -> cell."""
    req = t.MultiRowAddRequest(table_id=table_id, data=[data], stream=stream)
    res = client.table.add_table_rows(t.TableType.ACTION, req)
    # When stream=False, res is a MultiRowCompletionResponse
    row0 = res.rows[0]
    return row0.columns


# ==============================
# Streamlit UI
# ==============================

st.set_page_config(page_title="CropCheck AI", page_icon="🌱", layout="wide")

st.title("🌱 CropCheck AI – Fruit Problem Helper")
st.caption("Upload a fruit image, describe the problem, then follow the guided steps.")

# Sidebar: credentials
with st.sidebar:
    st.subheader("JamAI Settings")
    project_id = st.text_input("Project ID", value=DEFAULT_PROJECT_ID)
    pat = st.text_input("Personal Access Token (PAT)", value=DEFAULT_PAT, type="password")
    st.markdown("---")
    st.caption("These values stay local on your machine and are only used to call JamAI Base.")

# Init session state
for key, default in [
    ("crop_type", ""),
    ("initial_guess", ""),
    ("conf_problem", ""),
    ("clarifying_q", ""),
    ("purpose_q", ""),
    ("user_answer", ""),
    ("root_cause", ""),
    ("reasoning", ""),
    ("recommended_solution", ""),
    ("safety_avoid", ""),
    ("conf_solution", ""),
    ("summary", ""),
    ("future_tips", ""),
    ("description", ""),
    ("image_uri", ""),
]:
    st.session_state.setdefault(key, default)

# Layout
left, right = st.columns([1, 1])

with left:
    st.subheader("Step 1 – Upload & Describe")

    img_file = st.file_uploader(
        "Fruit image",
        type=["jpg", "jpeg", "png", "webp"],
        help="Upload a clear photo of the fruit.",
    )
    if img_file:
        st.image(img_file, caption="Uploaded fruit image", use_column_width=True)

    description = st.text_area(
        "Describe what you see / what you’re worried about",
        value=st.session_state["description"],
        height=120,
    )

    run_step1_btn = st.button("🔍 Run Step 1 + 2 (Detect & Question)", type="primary")

with right:
    st.subheader("Step 2 – Results & Clarifying Question")
    detect_placeholder = st.empty()
    question_placeholder = st.empty()
    purpose_placeholder = st.empty()

# ==============================
# Step 1 + 2: Detect problem & generate clarifying question
# ==============================

if run_step1_btn:
    try:
        client = get_client(project_id, pat)
    except Exception as e:
        st.error(f"JamAI client error: {e}")
    else:
        if not img_file:
            st.warning("Please upload an image first.")
        elif not description.strip():
            st.warning("Please enter a short description.")
        else:
            with st.spinner("Sending image to JamAI (Detect The Problem)…"):
                img_uri = upload_to_jamai(client, img_file)
                st.session_state["image_uri"] = img_uri
                st.session_state["description"] = description

                # --- Table 1: Detect The Problem ---
                cols1 = call_action_table(
                    client,
                    TABLE_DETECT,
                    {
                        "Crop Image": img_uri,
                        "Description": description,
                    },
                    stream=False,
                )

                crop_type = safe_text(cols1.get("Crop Type"))
                initial_guess = safe_text(cols1.get("Initial Problem Guess"))
                conf_problem = safe_text(cols1.get("Confidence Score Problem"))

                st.session_state["crop_type"] = crop_type
                st.session_state["initial_guess"] = initial_guess
                st.session_state["conf_problem"] = conf_problem

                detect_placeholder.markdown(
                    f"""
                    **Detected crop:** `{crop_type or "Unknown"}`  
                    **Initial problem guess:** `{initial_guess or "—"}`  
                    **Confidence (problem):** `{conf_problem or "—"}`
                    """
                )

            with st.spinner("Generating follow-up question…"):
                # --- Table 2: Follow-Up Question ---
                cols2 = call_action_table(
                    client,
                    TABLE_FOLLOWUP,
                    {
                        "Crop Type": crop_type,
                        "Initial Problem Guess": initial_guess,
                        "Confidence Score Problem": conf_problem,
                    },
                    stream=False,
                )
                clarifying_q = safe_text(cols2.get("Clarifying Question"))
                purpose_q = safe_text(cols2.get("Purpose of Question"))

                st.session_state["clarifying_q"] = clarifying_q
                st.session_state["purpose_q"] = purpose_q

                question_placeholder.markdown(f"**Clarifying question:** {clarifying_q}")
                purpose_placeholder.markdown(f"*Purpose:* {purpose_q}")

# Show question + answer box if we have a clarifying question
if st.session_state["clarifying_q"]:
    st.markdown("---")
    st.subheader("Step 3 – Your Answer")

    st.write("Please answer the clarifying question in your own words:")
    st.info(st.session_state["clarifying_q"])

    st.session_state["user_answer"] = st.text_area(
        "Your answer",
        value=st.session_state["user_answer"],
        height=80,
    )

    run_rest_btn = st.button("✅ Run Steps 3–5 (Cause → Solution → Conclusion)")

else:
    run_rest_btn = False

# ==============================
# Steps 3–5: Cause, Solution, Final Conclusion
# ==============================

if run_rest_btn:
    if not st.session_state["user_answer"].strip():
        st.warning("Please type your answer to the clarifying question first.")
    else:
        try:
            client = get_client(project_id, pat)
        except Exception as e:
            st.error(f"JamAI client error: {e}")
        else:
            with st.spinner("Determining root cause…"):
                cols3 = call_action_table(
                    client,
                    TABLE_CAUSES,
                    {
                        "Crop Type": st.session_state["crop_type"],
                        "Initial Problem Guess": st.session_state["initial_guess"],
                        "User Answer": st.session_state["user_answer"],
                        "Description": st.session_state["description"],
                    },
                    stream=False,
                )

                root_cause = safe_text(cols3.get("Root Cause"))
                reasoning = safe_text(cols3.get("Reasoning"))

                st.session_state["root_cause"] = root_cause
                st.session_state["reasoning"] = reasoning

            with st.spinner("Generating recommended solution…"):
                cols4 = call_action_table(
                    client,
                    TABLE_SOLUTION,
                    {
                        "Crop Type": st.session_state["crop_type"],
                        "Root Cause": root_cause,
                        "Initial Problem Guess": st.session_state["initial_guess"],
                        "User Answer": st.session_state["user_answer"],
                    },
                    stream=False,
                )

                recommended = safe_text(cols4.get("Recommended Solution"))
                safety_avoid = safe_text(cols4.get("Safety or Avoid List"))
                conf_solution = safe_text(cols4.get("Confidence Score Solution"))

                st.session_state["recommended_solution"] = recommended
                st.session_state["safety_avoid"] = safety_avoid
                st.session_state["conf_solution"] = conf_solution

            with st.spinner("Building final summary & prevention tips…"):
                cols5 = call_action_table(
                    client,
                    TABLE_FINAL,
                    {
                        "Crop Type": st.session_state["crop_type"],
                        "Root Cause": root_cause,
                        "Users Answer": st.session_state["user_answer"],
                        "Recommended Solution": recommended,
                    },
                    stream=False,
                )

                summary = safe_text(cols5.get("Summary"))
                future_tips = safe_text(cols5.get("Future Prevention Tips"))

                st.session_state["summary"] = summary
                st.session_state["future_tips"] = future_tips

# ==============================
# Display final results (with small typing effect)
# ==============================

if st.session_state["root_cause"]:
    st.markdown("---")
    st.subheader("Step 4 – Diagnosis & Solution")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Crop type:** {st.session_state['crop_type'] or 'Unknown'}")
        st.markdown(f"**Root cause:** {st.session_state['root_cause'] or '—'}")
        st.markdown(f"**Reasoning:** {st.session_state['reasoning'] or '—'}")

    with col2:
        st.markdown(f"**Recommended solution:** {st.session_state['recommended_solution'] or '—'}")
        st.markdown(f"**Safety / avoid:** {st.session_state['safety_avoid'] or '—'}")
        st.markdown(
            f"**Confidence (solution):** {st.session_state['conf_solution'] or '—'}"
        )

if st.session_state["summary"]:
    st.markdown("---")
    st.subheader("Step 5 – Final Conclusion")

    summary_ph = st.empty()
    tips_ph = st.empty()

    # Typing effect for the summary only (so it feels “live”)
    type_out(st.session_state["summary"], summary_ph)

    tips_ph.markdown(f"**Future prevention tips:** {st.session_state['future_tips'] or '—'}")
