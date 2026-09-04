import os
from datetime import datetime
from io import BytesIO

import joblib
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Early Stage Diabetes Prediction",
    page_icon="🩺",
    layout="centered",
)

MODEL_PATH = "diabetes_model.pkl"
SCALER_PATH = "age_scaler.pkl"
COLUMNS_PATH = "feature_columns.pkl"
SAVE_FILE_XLSX = "saved_reports.xlsx"  # admin-only saved records (Excel)


def _get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD", "admin123")


# ---------------------------------------------------------------------------
# Load model + preprocessing objects
# ---------------------------------------------------------------------------
@st.cache_resource
def load_artifacts():
    missing = [p for p in [MODEL_PATH, SCALER_PATH, COLUMNS_PATH] if not os.path.exists(p)]
    if missing:
        st.error(
            "Missing required file(s): "
            + ", ".join(missing)
            + ".\n\nMake sure diabetes_model.pkl, age_scaler.pkl and "
              "feature_columns.pkl are in the same folder as this app, "
              "then restart the app."
        )
        st.stop()

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    feature_columns = joblib.load(COLUMNS_PATH)
    return model, scaler, feature_columns


model, scaler, feature_columns = load_artifacts()

binary_columns = [c for c in feature_columns if c not in ("Age", "Gender")]

display_labels = {
    "Polyuria": "Polyuria (excessive urination)",
    "Polydipsia": "Polydipsia (excessive thirst)",
    "sudden weight loss": "Sudden weight loss",
    "Irritability": "Irritability",
    "delayed healing": "Delayed wound healing",
    "partial paresis": "Partial paresis (partial muscle weakness)",
    "Alopecia": "Alopecia (abnormal hair loss)",
    "Itching": "Itching",
}

extra_symptoms_labels = {
    "constant_fatigue": "Constant fatigue / tiredness",
    "blurry_vision": "Blurry or unclear vision",
    "frequent_infections": "Frequent infections (skin / gum / urinary)",
    "tingling_numbness": "Tingling or numbness in hands or feet",
}

diabetes_types = [
    "Not sure / I don't know",
    "Type 1",
    "Type 2",
    "Gestational diabetes",
    "Prediabetes",
]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🩺 Early Stage Diabetes Prediction")
st.write(
    "Please fill in your personal information and symptoms below, then "
    "click **Predict** to estimate the risk of early-stage diabetes."
)
st.caption(
    "⚠️ This tool is for educational/demo purposes only and is NOT a "
    "medical diagnosis. Always consult a qualified doctor for an "
    "actual diagnosis."
)
st.divider()

# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------
with st.form("patient_form", clear_on_submit=False):
    st.subheader("Personal Information")

    c1, c2 = st.columns(2)
    with c1:
        first_name = st.text_input("First name *")
    with c2:
        last_name = st.text_input("Last name *")

    c3, c4 = st.columns(2)
    with c3:
        phone = st.text_input("Phone number *")
    with c4:
        patient_email = st.text_input("Email address (optional)")

    address = st.text_input("Residential address (city / area) *")

    diabetes_type = st.selectbox("Which type of diabetes do you believe you have?", diabetes_types)

    st.divider()
    st.subheader("Basic Information")

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", min_value=1, max_value=120, value=40, step=1)
    with col2:
        gender = st.selectbox("Gender", ["Male", "Female"])

    st.subheader("Core Symptoms")
    st.caption("Select Yes or No for each symptom below.")

    symptom_values = {}
    s_col1, s_col2 = st.columns(2)
    for i, col in enumerate(binary_columns):
        label = display_labels.get(col, col)
        target_col = s_col1 if i % 2 == 0 else s_col2
        with target_col:
            symptom_values[col] = st.selectbox(label, ["No", "Yes"], key=col)

    st.subheader("Additional Symptoms (optional)")
    st.caption(
        "These symptoms don't directly affect the predicted percentage "
        "(the model was not trained on them), but they help enrich your "
        "final report and its recommendations."
    )
    extra_values = {}
    e_col1, e_col2 = st.columns(2)
    for i, (key, label) in enumerate(extra_symptoms_labels.items()):
        target_col = e_col1 if i % 2 == 0 else e_col2
        with target_col:
            extra_values[key] = st.selectbox(label, ["No", "Yes"], key=f"extra_{key}")

    submitted = st.form_submit_button("🔍 Predict", use_container_width=True)


# ---------------------------------------------------------------------------
# Prediction logic
# ---------------------------------------------------------------------------
def _model_probability(raw_input: dict) -> float:
    df_new = pd.DataFrame([raw_input])
    df_new["Gender"] = df_new["Gender"].map({"Male": 1, "Female": 0})

    for col in binary_columns:
        df_new[col] = df_new[col].map({"Yes": 1, "No": 0})

    df_new["Age"] = scaler.transform(df_new[["Age"]])
    df_new = df_new[feature_columns]

    return float(model.predict_proba(df_new)[0][1])


def predict_new_patient(raw_input: dict):
    yes_symptoms = [c for c in binary_columns if raw_input.get(c) == "Yes"]

    if not yes_symptoms:
        return 0, 0.0

    actual_probability = _model_probability(raw_input)

    baseline_input = dict(raw_input)
    for col in binary_columns:
        baseline_input[col] = "No"

    baseline_probability = _model_probability(baseline_input)

    contributions = []
    for col in yes_symptoms:
        one_symptom_input = dict(baseline_input)
        one_symptom_input[col] = "Yes"
        symptom_probability = _model_probability(one_symptom_input)
        contribution = max(0.0, symptom_probability - baseline_probability)
        contributions.append(contribution)

    total_positive_evidence = sum(contributions)

    if total_positive_evidence <= 0:
        symptom_factor = len(yes_symptoms) / max(len(binary_columns), 1)
    else:
        symptom_factor = min(total_positive_evidence / 0.50, 1.0)

    probability = actual_probability * symptom_factor
    probability = max(0.0, min(1.0, probability))
    prediction = 1 if probability >= 0.50 else 0

    return prediction, probability


# ---------------------------------------------------------------------------
# Weekly meal plan & Health Guide
# ---------------------------------------------------------------------------
WEEKLY_MEAL_PLAN = [
    {
        "Day": "Saturday",
        "Breakfast": "Boiled eggs + whole-grain bread + cucumber & tomato",
        "Lunch": "Grilled chicken breast + brown rice + green salad",
        "Dinner": "Grilled fish + sauteed vegetables (broccoli/green beans)",
        "Drinks": "Water, unsweetened green tea",
    },
    {
        "Day": "Sunday",
        "Breakfast": "Oatmeal with low-fat milk + cinnamon + a handful of berries",
        "Lunch": "Lentil soup + fattoush salad (no fried bread)",
        "Dinner": "Lean grilled meat + roasted vegetables",
        "Drinks": "Water, unsweetened mint tea",
    },
    {
        "Day": "Monday",
        "Breakfast": "Plain yogurt + whole-grain cereal + raw nuts",
        "Lunch": "Tuna salad with olive oil + 1 slice whole-grain bread",
        "Dinner": "Stuffed vegetables (peppers/zucchini) with a small amount of rice",
        "Drinks": "Water, anise or chamomile tea",
    },
    {
        "Day": "Tuesday",
        "Breakfast": "Vegetable omelet + whole-grain bread",
        "Lunch": "Boiled or grilled chicken + quinoa or bulgur + salad",
        "Dinner": "Vegetable soup + a small piece of low-fat cheese",
        "Drinks": "Water, green tea",
    },
    {
        "Day": "Wednesday",
        "Breakfast": "Greek yogurt + chia seeds + low-sugar fruit (apple/berries)",
        "Lunch": "Grilled fish + leafy green salad + 1 tbsp olive oil",
        "Dinner": "Cooked lentils or chickpeas + roasted vegetables",
        "Drinks": "Water, unsweetened hibiscus tea",
    },
    {
        "Day": "Thursday",
        "Breakfast": "Whole-grain bread + low-fat cheese + fresh vegetables",
        "Lunch": "Grilled meat or chicken + sauteed vegetables + a small portion of brown rice",
        "Dinner": "Large salad with grilled chicken or tuna",
        "Drinks": "Water, mint tea",
    },
    {
        "Day": "Friday",
        "Breakfast": "Oatmeal or eggs + a handful of raw nuts",
        "Lunch": "Fish or chicken + roasted vegetables + salad",
        "Dinner": "Light vegetable soup + a small piece of cheese",
        "Drinks": "Water, unsweetened herbal tea",
    },
]

GENERAL_TIPS = [
    "Use the plate method: half the plate vegetables, a quarter lean protein, a quarter whole grains or moderate starch.",
    "Prefer low-glycemic-index foods (whole grains, legumes) over sugar and refined white flour.",
    "Avoid sugary drinks and packaged juices; replace them with water or unsweetened tea/herbal infusions.",
    "Keep consistent meal times to avoid sharp swings in blood sugar.",
    "Aim for at least 150 minutes of moderate physical activity per week (after checking with your doctor).",
    "Stay well hydrated and monitor your blood sugar regularly as advised by your doctor.",
]


def render_meal_plan():
    st.subheader("🥗 Suggested Weekly Meal Plan")
    st.caption(
        "This plan is built on general diabetes-management principles "
        "(the diabetes plate method, preferring low-glycemic-index foods) "
        "and is for guidance only."
    )
    df_plan = pd.DataFrame(WEEKLY_MEAL_PLAN).set_index("Day")
    st.table(df_plan)

    st.markdown("**General tips for managing your blood sugar:**")
    for tip in GENERAL_TIPS:
        st.markdown(f"- {tip}")


def render_offline_health_guide():
    st.subheader("🌿 Offline Healthy Lifestyle & Nutrition Guide")
    st.caption("This guide is built into the application, so it works without an internet connection.")

    with st.expander("🍽️ Healthy plate method", expanded=True):
        st.markdown(
            "- **½ plate:** non-starchy vegetables such as cucumber, tomato, broccoli, green beans and leafy vegetables.\n"
            "- **¼ plate:** lean protein such as grilled chicken, fish, eggs or lean meat.\n"
            "- **¼ plate:** whole grains or a moderate starch portion such as brown rice, quinoa, bulgur or whole-grain bread.\n"
            "- Choose **water or unsweetened drinks** instead of sugary drinks."
        )

    with st.expander("🥗 Foods to prefer"):
        st.markdown(
            "- Vegetables and salads\n"
            "- Beans, lentils and chickpeas\n"
            "- Whole grains and high-fiber foods\n"
            "- Fish, skinless chicken and other lean proteins\n"
            "- Plain/low-sugar yogurt\n"
            "- Small portions of nuts\n"
            "- Whole fruit in moderate portions rather than fruit juice"
        )

    with st.expander("⚠️ Foods and drinks to limit"):
        st.markdown(
            "- Sugary soft drinks and packaged juices\n"
            "- Added sugar and very sweet desserts\n"
            "- Large portions of refined white bread/rice\n"
            "- Highly processed foods\n"
            "- Very large meals or frequent unnecessary snacking"
        )

    with st.expander("🏃 Daily lifestyle habits"):
        st.markdown(
            "- Aim for regular physical activity appropriate for your health.\n"
            "- Keep consistent meal times.\n"
            "- Stay hydrated.\n"
            "- If you monitor blood glucose, follow the schedule recommended by your healthcare professional.\n"
            "- Seek professional medical advice for persistent or concerning symptoms."
        )

    with st.expander("📅 Weekly meal plan"):
        render_meal_plan()

    st.info("⚠️ This guide is educational and does not replace a doctor's advice or a personalized diabetes treatment plan.")


# ---------------------------------------------------------------------------
# PDF Generation Function
# ---------------------------------------------------------------------------
def generate_pdf_report(report_data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.HexColor("#0f4c81"),
        spaceAfter=15,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0f4c81"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    elements = []

    elements.append(Paragraph("🩺 Early Stage Diabetes Assessment Report", title_style))
    elements.append(Paragraph(f"<b>Generated Date:</b> {report_data.get('Timestamp', '')}", body_style))
    elements.append(Spacer(1, 15))

    # Patient info table
    elements.append(Paragraph("Patient Details", heading_style))
    patient_info = [
        ["Full Name:", f"{report_data.get('First name', '')} {report_data.get('Last name', '')}"],
        ["Age / Gender:", f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}"],
        ["Phone Number:", report_data.get("Phone", "")],
        ["Email:", report_data.get("Email", "N/A")],
        ["Address:", report_data.get("Address", "")],
        ["Believed Type:", report_data.get("Reported diabetes type", "")],
    ]
    t1 = Table(patient_info, colWidths=[120, 380])
    t1.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ])
    )
    elements.append(t1)
    elements.append(Spacer(1, 15))

    # Result Table
    elements.append(Paragraph("Assessment Result", heading_style))
    is_positive = "Positive" in report_data.get("Result", "")
    res_color = colors.HexColor("#dc2626") if is_positive else colors.HexColor("#16a34a")

    res_data = [
        ["Risk Assessment:", report_data.get("Result", "")],
        ["Estimated Probability:", report_data.get("Probability", "")],
        ["Additional Symptoms Present:", report_data.get("Notable extra symptoms", "")],
    ]
    t2 = Table(res_data, colWidths=[160, 340])
    t2.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 0), (1, 0), res_color),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ])
    )
    elements.append(t2)
    elements.append(Spacer(1, 20))

    # Disclaimer
    disclaimer_text = (
        "<b>Disclaimer:</b> This report is generated by an AI model for educational and demonstration "
        "purposes only. It is NOT a medical diagnosis. Please consult a qualified doctor or healthcare "
        "provider for proper clinical evaluation and diagnosis."
    )
    elements.append(Paragraph(disclaimer_text, body_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Report storage
# ---------------------------------------------------------------------------
def save_report_to_excel(report: dict):
    new_row = pd.DataFrame([report])

    if os.path.exists(SAVE_FILE_XLSX):
        try:
            existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
            combined = pd.concat([existing, new_row], ignore_index=True)
        except Exception:
            combined = new_row
    else:
        combined = new_row

    combined.to_excel(SAVE_FILE_XLSX, index=False, engine="openpyxl")


# ---------------------------------------------------------------------------
# Form Submission Logic
# ---------------------------------------------------------------------------
if submitted:
    clean_first_name = first_name.strip()
    clean_last_name = last_name.strip()
    clean_phone = phone.strip()
    clean_address = address.strip()
    clean_email = patient_email.strip()

    errors = []
    if not clean_first_name:
        errors.append("First name is required.")
    if not clean_last_name:
        errors.append("Last name is required.")
    if not clean_phone:
        errors.append("Phone number is required.")
    if not clean_address:
        errors.append("Residential address is required.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        raw_input = {"Age": age, "Gender": gender, **symptom_values}
        result, probability = predict_new_patient(raw_input)

        any_extra_symptom = any(v == "Yes" for v in extra_values.values())

        st.session_state["last_report"] = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "First name": clean_first_name,
            "Last name": clean_last_name,
            "Phone": clean_phone,
            "Email": clean_email if clean_email else "N/A",
            "Address": clean_address,
            "Reported diabetes type": diabetes_type,
            "Age": age,
            "Gender": gender,
            "Result": "Positive (high risk)" if result == 1 else "Negative (low risk)",
            "Probability": f"{probability * 100:.1f}%",
            "Notable extra symptoms": "Yes" if any_extra_symptom else "No",
        }
        st.session_state["last_result"] = int(result)
        st.session_state["last_probability"] = float(probability)
        st.session_state["report_saved"] = False

# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------
if "last_report" in st.session_state:
    report = st.session_state["last_report"]
    result = st.session_state["last_result"]
    probability = st.session_state["last_probability"]

    st.divider()
    st.subheader("Result")

    if result == 1:
        st.error("⚠️ High risk of early-stage diabetes")
    else:
        st.success("✅ Low risk of early-stage diabetes")

    st.metric("Estimated probability of Positive", report["Probability"])
    st.progress(min(max(probability, 0.0), 1.0))

    st.divider()

    if result == 1:
        st.warning(
            "🚨 Because your risk level is high, we strongly recommend "
            "visiting the nearest doctor or health center as soon as "
            "possible for an accurate diagnosis and your personal safety. "
            "Please don't rely on this tool as a substitute for medical advice."
        )
        render_offline_health_guide()
    else:
        if report["Notable extra symptoms"] == "Yes":
            st.info(
                "We noticed you selected 'Yes' for some additional symptoms. "
                "Even though the current result is low-risk, it's a good idea "
                "to see a doctor if these symptoms persist."
            )
        render_meal_plan()
        render_offline_health_guide()

    st.caption(
        "⚠️ This tool is for educational/demo purposes only and is NOT a "
        "medical diagnosis. Always consult a qualified doctor for an actual diagnosis."
    )

    if not st.session_state.get("report_saved", False):
        save_report_to_excel(report)
        st.session_state["report_saved"] = True

    st.divider()
    st.subheader("📄 Download Assessment Report")

    pdf_data = generate_pdf_report(report)
    file_name_pdf = f"Diabetes_Report_{report['First name']}_{report['Last name']}.pdf"

    st.download_button(
        label="📥 Download Report (PDF)",
        data=pdf_data,
        file_name=file_name_pdf,
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Admin Panel
# ---------------------------------------------------------------------------
st.divider()
with st.expander("🔒 Admin Panel (staff only)"):
    st.caption(
        "This section is restricted. Patients should not be given this "
        "password. It gives access to every patient's submitted data."
    )
    admin_pw = st.text_input("Admin password", type="password", key="admin_pw")

    if admin_pw:
        if admin_pw == ADMIN_PASSWORD:
            st.success("Access granted.")
            if os.path.exists(SAVE_FILE_XLSX):
                try:
                    history_df = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
                    st.dataframe(history_df, use_container_width=True)

                    col_download, col_clean = st.columns(2)

                    with col_download:
                        with open(SAVE_FILE_XLSX, "rb") as f:
                            st.download_button(
                                "⬇️ Download Excel file",
                                data=f.read(),
                                file_name=SAVE_FILE_XLSX,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )

                    with col_clean:
                        if st.button("🗑️ Clean Data", type="secondary", use_container_width=True):
                            st.session_state["confirm_clean"] = True

                    if st.session_state.get("confirm_clean", False):
                        st.warning("⚠️ Are you sure you want to delete all saved records? This action cannot be undone!")

                        col_yes, col_no = st.columns(2)

                        with col_yes:
                            if st.button("Yes, Delete Data", type="primary", use_container_width=True):
                                try:
                                    os.remove(SAVE_FILE_XLSX)
                                    st.session_state["confirm_clean"] = False
                                    st.success("All data cleared successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error while deleting file: {e}")

                        with col_no:
                            if st.button("Cancel", use_container_width=True):
                                st.session_state["confirm_clean"] = False
                                st.rerun()

                except Exception as exc:  # noqa: BLE001
                    st.warning(f"Could not read the saved records file: {exc}")
            else:
                st.caption("No saved records yet.")
        else:
            st.error("Incorrect password.")
