from __future__ import annotations

import os
import tempfile
import base64
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

client = JamAI(project_id=PROJECT_ID, token=PAT)

# ==============================
# Table IDs
# ==============================
TABLE_DETECT = "1. Detect the Problem"
TABLE_CLARIFY = "2. User Clarification"
TABLE_FINAL = "3. Final Conclusion"

# ==============================
# Streamlit UI Settings
# ==============================
st.set_page_config(
    page_title="CropCheckAI",
    page_icon="🌱",
    layout="wide",
)

st.title("🌾 CropCheckAI – Fruit & Crop Disease Assistant")

# ==============================
# Custom CSS
# ==============================

st.markdown("""
<style>
#loading-overlay {
    position: fixed;
    top: 0; left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0,0,0,0.55);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 999999;
}
.loading-box {
    background: #111;
    padding: 25px 40px;
    border-radius: 12px;
    text-align: center;
    color: white;
    font-size: 1.3rem;
    border: 1px solid #444;
}
.spinner {
    border: 4px solid #444;
    border-top: 4px solid #ff4b4b;
    border-radius: 50%;
    width: 42px;
    height: 42px;
    animation: spin 0.9s linear infinite;
    margin: 10px auto 15px auto;
}
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>

<div id="loading-overlay">
    <div class="loading-box">
        <div class="spinner"></div>
        <span id="loading-text">Loading...</span>
    </div>
</div>

<script>
function showLoader(text){
    document.getElementById("loading-text").innerText = text;
    document.getElementById("loading-overlay").style.display = "flex";
}
</script>
""", unsafe_allow_html=True)


st.markdown("""
<style>

    /* Placeholder image box */
    .image-box {
        width: 100%;
        max-width: 350px;
        height: 350px;
        border-radius: 12px;
        overflow: hidden;
        background-color: #1e1e1e50;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 10px auto;
        border: 1px solid #333;
    }

    .image-box img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    /* Main layout container */
    .block-container {
        padding: 0rem 1rem 2rem 1rem !important;
        margin: 0 auto !important;
        width: 100% !important;
        max-width: 900px;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-top: 4rem !important;
        }
    }

    @media (min-width: 601px) {
        .block-container {
            padding-top: 2rem !important;
        }
    }

    header, [data-testid="stHeader"] {
        height: 0px !important;
    }

    /* Mobile button styles */
    @media (max-width: 600px) {
        .stButton>button {
            width: 100% !important;
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
    }

</style>
""", unsafe_allow_html=True)


# ==============================
# Helpers
# ==============================
def upload_streamlit_file(tmp_file):
    suffix = os.path.splitext(tmp_file.name)[1]

    # Reset stream pointer (CRITICAL FIX)
    tmp_file.seek(0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(tmp_file.read())
        temp_path = f.name

    try:
        resp = client.file.upload_file(temp_path)
        return resp.uri
    finally:
        try:
            os.remove(temp_path)
        except:
            pass




def run_action_row(table_id: str, data: Dict[str, str]) -> Dict[str, str]:
    """Run an Action table and return text outputs."""
    resp = client.table.add_table_rows(
        table_type=t.TableType.ACTION,
        request=t.MultiRowAddRequest(
            table_id=table_id,
            data=[data],
            stream=False,
        ),
    )

    row = resp.rows[0]
    out = {}

    for name, val in row.columns.items():
        if hasattr(val, "text") and val.text:
            out[name] = val.text

    return out


def show_image_in_box(uploaded_file):
    """Embed image inside placeholder container using base64."""
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()
    encoded = base64.b64encode(bytes_data).decode()

    st.markdown(
        f"""
        <div class="image-box">
            <img src="data:image/jpeg;base64,{encoded}">
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================
# Session State
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


# Sidebar actions
st.sidebar.header("Actions")
if st.sidebar.button("🔄 Start over", use_container_width=True):
    reset_all()


# ===================================================================
# STEP 1 – Detect the Problem
# ===================================================================
if st.session_state.step == 1:

    st.header("Step 1 – Upload crop image & symptoms")

    st.subheader("Upload a photo of the affected crop/fruit")
    user_image = st.file_uploader(
        "Upload Image",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )

    if user_image:
        st.markdown("### 📷 Image Preview")
        show_image_in_box(user_image)

    st.subheader("Describe the symptoms")
    user_desc = st.text_area(
        "desc",
        placeholder="Example: Brown spots on mango leaves, dark patches near fruit stem…",
        label_visibility="collapsed",
        height=180,
    )

    colA, colB, colC = st.columns([1, 2, 1])
    with colB:
        submitted = st.button("Analyze disease", type="primary", use_container_width=True)

    if submitted:
        if not user_image or not user_desc:
            st.warning("Please upload an image AND describe the symptoms.")
        else:
            with st.spinner("Analyzing crop / fruit disease…"):
                uri = upload_streamlit_file(user_image)

                detect_out = run_action_row(
                    TABLE_DETECT,
                    {"user_image": uri, "user_desc": user_desc},
                )

                st.session_state.detect_out = detect_out
                st.session_state.step = 2
                st.rerun()

    st.stop()


# ===================================================================
# STEP 2 – User Clarification
# ===================================================================
if st.session_state.step == 2:

    detect = st.session_state.detect_out

    st.header("Step 2 – Confirm details about the disease")

    st.info(
        f"**Crop type:** {detect.get('crop_type')}\n\n"
        f"**Initial guess:** {detect.get('initial_guess')}\n\n"
        f"**Confidence:** {detect.get('confidence_level', 'N/A')}"
    )

    st.warning(detect.get("clarifying_question", "No clarifying question."))

    user_answer = st.text_area(
        "Your answer:",
        placeholder="Example: Yes, the spots are spreading upward…",
    )

    if st.button("Submit answer", type="primary"):
        if not user_answer:
            st.warning("Please type your answer.")
        else:
            with st.spinner("Interpreting your answer…"):

                clarify_out = run_action_row(
                    TABLE_CLARIFY,
                    {
                        "crop_type": detect.get("crop_type"),
                        "initial_guess": detect.get("initial_guess"),
                        "clarifying_question": detect.get("clarifying_question"),
                        "user_answer": user_answer,
                    },
                )

                st.session_state.clarify_out = clarify_out
                st.session_state.step = 3
                st.rerun()

    st.stop()


# ===================================================================
# STEP 3 – Final Conclusion
# ===================================================================
if st.session_state.step == 3:

    detect = st.session_state.detect_out
    clarify = st.session_state.clarify_out

    st.header("Step 3 – Final diagnosis & recommendations")

    with st.spinner("Preparing final diagnosis…"):

        final_out = run_action_row(
            TABLE_FINAL,
            {
                "crop_type": detect.get("crop_type"),
                "initial_guess": detect.get("initial_guess"),
                "cleaned_answer": clarify.get("cleaned_answer"),
                "confidence_level": clarify.get("confidence_level"),
            },
        )

        st.session_state.final_out = final_out

    final = st.session_state.final_out

    st.subheader("🌿 Final disease diagnosis")
    st.success(final.get("final_diagnosis", ""))

    st.subheader("🦠 Cause")
    st.write(final.get("cause", ""))

    st.subheader("🧴 Treatment steps")
    st.write(final.get("treatment_steps", ""))

    st.subheader("🛡 Prevention tips")
    st.write(final.get("prevention_tips", ""))

    if st.button("Start a new case"):
        reset_all()
