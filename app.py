from __future__ import annotations

import os
import tempfile
from typing import Dict

import streamlit as st
from dotenv import load_dotenv
from jamaibase import JamAI, types as t

# ==============================
# Load environment variables
# ==============================
load_dotenv()
PROJECT_ID = os.getenv("JAMAI_PROJECT_ID")
PAT = os.getenv("JAMAI_PAT")

if not PROJECT_ID or not PAT:
    raise RuntimeError("JAMAI_PROJECT_ID or JAMAI_PAT missing in .env")

# JamAI client (correct signature)
client = JamAI(project_id=PROJECT_ID, token=PAT)

# ==============================
# Table IDs
# ==============================
TABLE_DETECT = "1. Detect the Problem"
TABLE_CLARIFY = "2. User Clarification"
TABLE_FINAL = "3. Final Conclusion"

# ==============================
# Streamlit config
# ==============================
st.set_page_config(
    page_title="CropCheckAI",
    page_icon="🌱",
    layout="wide",
)
st.title("🌾 CropCheckAI – Fruit & Crop Disease Assistant")

# ==============================
# Helpers
# ==============================

def upload_streamlit_file(tmp_file) -> str:
    """Save uploaded file to a temp path and upload to JamAI file store.
    Returns the file URI that can be used in an Action table.
    """
    suffix = os.path.splitext(tmp_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(tmp_file.read())
        temp_path = f.name

    try:
        file_resp = client.file.upload_file(temp_path)
        return file_resp.uri
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def run_action_row(table_id: str, data: Dict[str, str]) -> Dict[str, str]:
    """Call an Action table once and return a simple dict of outputs."""
    resp = client.table.add_table_rows(
        table_type=t.TableType.ACTION,
        request=t.RowAddRequest(
            table_id=table_id,
            data=[data],
            stream=False,
        ),
    )

    row = resp.rows[0]
    out: Dict[str, str] = {}
    for col_name, col_val in row.columns.items():
        # Most of your columns are text outputs
        if hasattr(col_val, "text") and col_val.text is not None:
            out[col_name] = col_val.text

    return out


# ==============================
# Session state
# ==============================

if "step" not in st.session_state:
    st.session_state.step = 1

if "detect_out" not in st.session_state:
    st.session_state.detect_out = None

if "clarify_out" not in st.session_state:
    st.session_state.clarify_out = None

if "final_out" not in st.session_state:
    st.session_state.final_out = None


def reset_all():
    st.session_state.step = 1
    st.session_state.detect_out = None
    st.session_state.clarify_out = None
    st.session_state.final_out = None
    st.rerun()


# Sidebar
st.sidebar.header("Actions")
if st.sidebar.button("🔄 Start over", use_container_width=True):
    reset_all()
st.sidebar.markdown("This tool focuses on **fruit & crop diseases** only.")

# =======================================================================
# STEP 1 – Detect the Problem  (Table: 1. Detect the Problem)
# =======================================================================
if st.session_state.step == 1:
    st.header("Step 1 – Upload crop image & symptoms")

    c1, c2 = st.columns([1, 1])

    # ----------- IMAGE UPLOAD -----------
    with c1:
        user_image = st.file_uploader(
            "Upload a photo of the affected crop/fruit",
            type=["jpg", "jpeg", "png"],
        )

        # Show preview immediately
        if user_image:
            st.markdown("### 📷 Image Preview")
            st.image(user_image, use_column_width=True)

    # ----------- DESCRIPTION -----------
    with c2:
        user_desc = st.text_area(
            "Describe the symptoms (spots, rot, wilting, etc.)",
            placeholder="Example: Brown spots on mango leaves, some fruits turning black near the stem...",
            height=200,
        )

    # ----------- SUBMIT BUTTON -----------
    if st.button("Analyze disease", type="primary"):
        if not user_image or not user_desc:
            st.warning("Please upload an image **and** describe the symptoms.")
        else:
            with st.spinner("Analyzing crop / fruit disease..."):
                img_uri = upload_streamlit_file(user_image)

                detect_out = run_action_row(
                    TABLE_DETECT,
                    {
                        "user_image": img_uri,
                        "user_desc": user_desc,
                    },
                )

                st.session_state.detect_out = detect_out
                st.session_state.step = 2
                st.rerun()

    st.stop()


# =======================================================================
# STEP 2 – User Clarification  (Table: 2. User Clarification)
# =======================================================================
if st.session_state.step == 2:
    detect = st.session_state.detect_out

    st.header("Step 2 – Confirm details about the disease")

    st.write("### 🧾 Detected crop & initial disease guess")
    st.info(
        f"**Crop type:** {detect.get('crop_type', 'N/A')}\n\n"
        f"**Initial disease guess:** {detect.get('initial_guess', 'N/A')}\n\n"
        f"**Confidence level:** {detect.get('confidence_level', 'N/A')}"
    )

    st.write("### ❓ Clarifying question")
    st.warning(detect.get("clarifying_question", "No question generated."))

    user_answer = st.text_area(
        "Your answer (based on what you see in your field):",
        placeholder="Example: Yes, the spots are spreading from lower leaves upwards...",
    )

    if st.button("Submit answer", type="primary"):
        if not user_answer:
            st.warning("Please type your answer first.")
        else:
            with st.spinner("Interpreting your answer..."):
                # IMPORTANT: this expects an **input column** in table 2.
                # Create an INPUT text column named `user_answer` in
                # \"2. User Clarification\" and keep the three outputs you showed.
                clarify_out = run_action_row(
                    TABLE_CLARIFY,
                    {
                        "user_answer": user_answer,
                    },
                )

                st.session_state.clarify_out = clarify_out
                st.session_state.step = 3
                st.rerun()

    st.stop()


# =======================================================================
# STEP 3 – Final Conclusion  (Table: 3. Final Conclusion)
# =======================================================================
if st.session_state.step == 3:
    detect = st.session_state.detect_out
    clarify = st.session_state.clarify_out

    st.header("Step 3 – Final diagnosis & recommendations")

    # We pass a compact case summary into table 3.
    # Create an INPUT text column in \"3. Final Conclusion\" called `case_context`
    # and keep your four output columns.
    case_context = f"""
Crop type: {detect.get('crop_type', '')}
Initial disease guess: {detect.get('initial_guess', '')}
Confidence level: {detect.get('confidence_level', '')}

Cleaned user clarification: {clarify.get('cleaned_answer', '')}
Interpretation of answer: {clarify.get('answer_interpretation', '')}
Does user answer support initial guess?: {clarify.get('supports_initial_guess', '')}
"""

    with st.spinner("Generating final fruit/crop disease diagnosis..."):
        final_out = run_action_row(
            TABLE_FINAL,
            {
                "case_context": case_context,
            },
        )
        st.session_state.final_out = final_out

    final = st.session_state.final_out

    st.subheader("🌿 Final disease diagnosis")
    st.success(final.get("final_diagnosis", "No diagnosis generated."))

    st.subheader("🦠 Cause")
    st.write(final.get("cause", "No cause generated."))

    st.subheader("🧴 Treatment steps")
    st.write(final.get("treatment_steps", "No treatment steps generated."))

    st.subheader("🛡 Prevention tips")
    st.write(final.get("prevention_tips", "No prevention tips generated."))

    st.success("✔ Fruit/crop disease analysis completed.")

    if st.button("Start a new case"):
        reset_all()
