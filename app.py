import csv
import io
import json
import os
import re
import time
from pathlib import Path

import streamlit as st
from google import genai


# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="AI-Assisted Testing Platform",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path(__file__).parent / "data.json"


# ---------------- DATA STORAGE ----------------
def load_data():
    if not DATA_FILE.exists():
        return {"requirements": [], "test_cases": []}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        requirements = data.get("requirements", [])
        cases = data.get("test_cases", [])

        # Keep compatibility with older records that used "actor".
        for req in requirements:
            if "action" not in req and "actor" in req:
                req["action"] = req.get("actor", "")
                req["_legacy_abc_migration"] = True

        return {"requirements": requirements, "test_cases": cases}
    except (json.JSONDecodeError, OSError, TypeError):
        st.error("The saved data file could not be read. Please keep a backup of data.json.")
        return {"requirements": [], "test_cases": []}


if "requirements" not in st.session_state or "test_cases" not in st.session_state:
    saved = load_data()
    st.session_state.setdefault("requirements", saved["requirements"])
    st.session_state.setdefault("test_cases", saved["test_cases"])


def save_data():
    payload = {
        "requirements": st.session_state.requirements,
        "test_cases": st.session_state.test_cases,
    }
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4, ensure_ascii=False)


# ---------------- HELPERS ----------------
def next_id(items, field, prefix):
    highest = 0
    for item in items:
        match = re.search(r"(\d+)$", str(item.get(field, "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}-{highest + 1:03d}"


def make_description(action, behavior, constraint):
    return (
        f"Action: {action.strip()} "
        f"Behavior: {behavior.strip()} "
        f"Constraint: {constraint.strip()}"
    )


def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        key = ""
    return key or os.environ.get("GEMINI_API_KEY", "")


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def find_duplicate_cases(cases):
    seen = set()
    duplicates = []
    for case in cases:
        signature = (
            normalize(case.get("title")),
            normalize(case.get("steps")),
            normalize(case.get("expected_result")),
        )
        if signature in seen:
            duplicates.append(case)
        else:
            seen.add(signature)
    return duplicates


def rule_based_cases(requirement):
    description = requirement.get("description", "").lower()
    if "login" in description or "log in" in description:
        scenarios = [
            ("Valid login details", "Enter a registered username and correct password.",
             "The system should allow the user to log in."),
            ("Invalid password", "Enter a registered username and incorrect password.",
             "The system should reject the login and show an error."),
            ("Invalid username", "Enter an unregistered username and a password.",
             "The system should reject the login and show an error."),
            ("Blank username", "Leave the username empty and enter a password.",
             "The system should show that the username is required."),
            ("Blank password", "Enter a username and leave the password empty.",
             "The system should show that the password is required."),
        ]
    elif "password reset" in description or "forgot password" in description:
        scenarios = [
            ("Registered email", "Open Forgot Password, enter a registered email, and submit.",
             "The system should send a reset link to the registered email."),
            ("Unregistered email", "Enter an email that is not registered and submit.",
             "The system should show a safe message."),
            ("Blank email", "Leave the email field empty and submit.",
             "The system should show that email is required."),
            ("Expired reset link", "Open a reset link after its expiration time.",
             "The system should reject the expired link."),
            ("Valid reset link", "Open a valid reset link and enter a new password.",
             "The system should allow the password to be reset."),
        ]
    else:
        scenarios = [
            ("Valid input", "Enter information that follows the requirement.",
             "The system should perform the required behavior."),
            ("Invalid input", "Enter information that does not follow the requirement.",
             "The system should reject invalid input or show an error."),
            ("Missing input", "Leave a required input field empty.",
             "The system should identify the missing information."),
            ("Boundary input", "Enter a value at the allowed limit.",
             "The system should handle the boundary value correctly."),
        ]

    result = []
    for title, steps, expected in scenarios:
        result.append({
            "id": next_id(st.session_state.test_cases + result, "id", "TC"),
            "requirement_id": requirement["id"],
            "title": title,
            "steps": steps,
            "expected_result": expected,
            "source": "Rule-based prototype",
            "status": "Draft",
        })
    return result


def gemini_cases(requirement):
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Gemini API key not found in .streamlit/secrets.toml.")

    prompt = f"""
You are helping a software tester create test cases.
Use only the requirement information below. Do not invent features or rules.
Create 4 to 6 test cases. Include positive, negative, missing-input, and
boundary scenarios when relevant.

A - Action: {requirement.get('action', '')}
B - Behavior: {requirement.get('behavior', '')}
C - Constraint: {requirement.get('constraint', '')}

Return ONLY a valid JSON array. Each item must contain string fields:
"title", "steps", and "expected_result".
"""
    client = genai.Client(api_key=api_key)
    started = time.perf_counter()
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        response_text = response.text or ""
    finally:
        client.close()
    elapsed = round(time.perf_counter() - started, 2)

    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if not match:
        raise ValueError("Gemini did not return a readable JSON list.")
    items = json.loads(match.group(0))
    if not isinstance(items, list) or not items:
        raise ValueError("Gemini returned an empty or invalid list.")

    batch_id = f"GEM-{int(time.time() * 1000)}"
    result = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        steps = item.get("steps")
        expected = item.get("expected_result")
        if not all(isinstance(v, str) and v.strip() for v in (title, steps, expected)):
            continue
        result.append({
            "id": next_id(st.session_state.test_cases + result, "id", "TC"),
            "requirement_id": requirement["id"],
            "title": title.strip()[:200],
            "steps": steps.strip()[:2000],
            "expected_result": expected.strip()[:2000],
            "source": "Gemini AI",
            "status": "Draft",
            "generation_batch_id": batch_id,
            "generation_time_seconds": elapsed,
        })
    if not result:
        raise ValueError("Gemini response did not contain valid test cases.")
    return result, elapsed


def save_generated_cases(cases):
    valid_ids = {r.get("id") for r in st.session_state.requirements}
    if not cases or len(cases) > 8:
        return False, "No valid test cases were generated."
    for case in cases:
        if (
            case.get("requirement_id") not in valid_ids
            or not all(str(case.get(k, "")).strip()
                       for k in ("title", "steps", "expected_result"))
        ):
            return False, "Generated test cases did not pass validation."
    st.session_state.test_cases.extend(cases)
    save_data()
    return True, f"{len(cases)} draft test case(s) saved."


def source_metrics(cases, total_requirements, valid_requirement_ids):
    approved = [c for c in cases if c.get("status") == "Approved"]
    covered = {
        c.get("requirement_id") for c in approved
        if c.get("requirement_id") in valid_requirement_ids
    }
    coverage = len(covered) / total_requirements * 100 if total_requirements else 0
    duplicates = find_duplicate_cases(cases)
    duplicate_rate = len(duplicates) / len(cases) * 100 if cases else 0

    quality_fields = [
        "quality_correctness", "quality_clarity",
        "quality_completeness", "quality_relevance",
    ]
    quality_values = []
    for case in cases:
        vals = [case.get(field) for field in quality_fields]
        if all(isinstance(v, (int, float)) for v in vals):
            quality_values.append(sum(vals) / 4)
    avg_quality = sum(quality_values) / len(quality_values) if quality_values else None

    if cases and cases[0].get("source") == "Manual":
        timed = [
            c["creation_time_seconds"] for c in cases
            if isinstance(c.get("creation_time_seconds"), (int, float))
        ]
        total_time = sum(timed) if timed else None
        avg_time = total_time / len(timed) if timed else None
    else:
        batches = {}
        for case in cases:
            batch = case.get("generation_batch_id")
            seconds = case.get("generation_time_seconds")
            if batch and isinstance(seconds, (int, float)):
                batches.setdefault(batch, {"seconds": seconds, "count": 0})
                batches[batch]["count"] += 1
        total_time = sum(v["seconds"] for v in batches.values()) if batches else None
        timed_count = sum(v["count"] for v in batches.values())
        avg_time = total_time / timed_count if timed_count else None

    return {
        "total": len(cases), "approved": len(approved), "covered": len(covered),
        "coverage": coverage, "duplicates": len(duplicates),
        "duplicate_rate": duplicate_rate, "quality": avg_quality,
        "creation_time": total_time, "average_creation_time": avg_time,
    }


# ---------------- STYLE AND HEADER ----------------
st.markdown("""
<style>
.stApp { background: linear-gradient(180deg, #f5f8fc 0%, #ffffff 48%); }
[data-testid="stSidebar"] { background: #10243a; }
[data-testid="stSidebar"] * { color: #f4f7fb; }
.main-title { font-size: 2.05rem; font-weight: 750; color: #17324d; }
.main-subtitle { color: #60758a; font-size: 1rem; margin-bottom: 1.2rem; }
.section-note { background: #edf4fb; border-left: 4px solid #3b82b9;
padding: .8rem 1rem; border-radius: 8px; color: #24445f; margin: .6rem 0 1rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🧪 AI-Assisted Testing Platform</div>',
            unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Software test case generation, review, and evaluation</div>',
            unsafe_allow_html=True)

# IMPORTANT: Manual Test Case Entry is included in this navigation list.
st.sidebar.title("🧪 Testing Platform")
st.sidebar.caption("Project Navigation")
page = st.sidebar.radio("Go to", [
    "Dashboard",
    "ABC Requirements",
    "Test Case Generation",
    "Manual Test Case Entry",
    "Review Test Cases",
    "Evaluation and Results",
    "AI Guardrails",
])
st.sidebar.divider()
st.sidebar.caption("Prototype status")
st.sidebar.info("Gemini AI generation and rule-based examples are available.")


# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    requirements = st.session_state.requirements
    cases = st.session_state.test_cases
    total_req = len(requirements)
    approved = [c for c in cases if c.get("status") == "Approved"]
    covered_ids = {c.get("requirement_id") for c in approved}
    covered = sum(1 for r in requirements if r.get("id") in covered_ids)
    coverage = covered / total_req * 100 if total_req else 0

    st.header("Project Dashboard")
    st.write("A quick overview of the requirements and test cases in this project.")
    cols = st.columns(4)
    cols[0].metric("Requirements", total_req)
    cols[1].metric("Total Test Cases", len(cases))
    cols[2].metric("Approved Cases", len(approved))
    cols[3].metric("Coverage", f"{coverage:.1f}%")
    st.subheader("Test Case Review Status")
    status_cols = st.columns(3)
    status_cols[0].metric("Draft", sum(c.get("status") == "Draft" for c in cases))
    status_cols[1].metric("Approved", len(approved))
    status_cols[2].metric("Rejected", sum(c.get("status") == "Rejected" for c in cases))
    st.subheader("Requirement Coverage")
    st.progress(int(round(coverage)))
    st.caption(f"{covered} of {total_req} requirements have at least one approved test case.")
    st.subheader("Project Workflow")
    st.markdown("""
    1. Add requirements using Action, Behavior, and Constraint.
    2. Generate test cases with Gemini AI or write them manually.
    3. Review, score, edit, approve, or reject test cases.
    4. Compare coverage, duplicate rate, quality, and creation time.
    """)
    st.caption("Coverage is based on approved cases linked to requirements. It does not prove every possible scenario has been tested.")


# ---------------- REQUIREMENTS ----------------
elif page == "ABC Requirements":
    st.header("Software Requirements – ABC Format")
    st.markdown('<div class="section-note"><b>A = Action</b> — action being performed. '
                '<b>B = Behavior</b> — how the system should respond. '
                '<b>C = Constraint</b> — a rule or limit.</div>', unsafe_allow_html=True)

    with st.form("requirement_form", clear_on_submit=True):
        action = st.text_area("A – Action", placeholder="Example: User submits a password reset request.")
        behavior = st.text_area("B – Behavior", placeholder="Example: The system sends a reset link.")
        constraint = st.text_area("C – Constraint", placeholder="Example: The link expires after 15 minutes.")
        submitted = st.form_submit_button("Save Requirement", use_container_width=True)
    if submitted:
        if not all(x.strip() for x in (action, behavior, constraint)):
            st.error("Please complete all three ABC fields.")
        elif len(action + behavior + constraint) > 2000:
            st.error("The requirement is too long. Please shorten it.")
        else:
            rid = next_id(st.session_state.requirements, "id", "REQ")
            st.session_state.requirements.append({
                "id": rid, "action": action.strip(), "behavior": behavior.strip(),
                "constraint": constraint.strip(),
                "description": make_description(action, behavior, constraint),
            })
            save_data()
            st.success(f"{rid} saved successfully.")

    st.divider()
    st.subheader("Saved Requirements")
    if not st.session_state.requirements:
        st.info("No requirements have been added yet.")
    for i, req in enumerate(st.session_state.requirements):
        saved_action = req.get("action", req.get("actor", ""))
        with st.expander(f"{req.get('id', 'REQ')} — {saved_action[:65]}"):
            with st.form(f"edit_requirement_{i}"):
                a = st.text_area("A – Action", value=saved_action)
                b = st.text_area("B – Behavior", value=req.get("behavior", ""))
                c = st.text_area("C – Constraint", value=req.get("constraint", ""))
                update = st.form_submit_button("Save Changes")
            if update:
                if not all(x.strip() for x in (a, b, c)):
                    st.error("Please complete all three ABC fields.")
                else:
                    req.update({
                        "action": a.strip(), "behavior": b.strip(),
                        "constraint": c.strip(),
                        "description": make_description(a, b, c),
                    })
                    req.pop("actor", None)
                    req.pop("_legacy_abc_migration", None)
                    save_data()
                    st.success("Requirement updated.")
                    st.rerun()


# ---------------- AI / RULE-BASED GENERATION ----------------
elif page == "Test Case Generation":
    st.header("Test Case Generation")
    st.write("Select a saved requirement and generate draft test cases.")
    st.info("The selected requirement is sent to Google's Gemini API when Gemini generation is used. Do not enter confidential information.")
    if not st.session_state.requirements:
        st.warning("Please add an ABC requirement first.")
    else:
        options = {r["id"]: r for r in st.session_state.requirements}
        selected = st.selectbox("Select a requirement", list(options))
        req = options[selected]
        st.info(req.get("description", ""))
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate with Gemini AI", type="primary", use_container_width=True):
                try:
                    new_cases, seconds = gemini_cases(req)
                    ok, message = save_generated_cases(new_cases)
                    if ok:
                        st.success(message)
                        st.caption(f"Gemini generation time for this batch: {seconds:.2f} seconds.")
                    else:
                        st.error(message)
                except Exception as exc:
                    st.error(f"Gemini generation failed ({type(exc).__name__}). You can use rule-based examples.")
        with col2:
            if st.button("Generate Rule-Based Examples", use_container_width=True):
                ok, message = save_generated_cases(rule_based_cases(req))
                st.success(message) if ok else st.error(message)
        st.divider()
        st.subheader("Generation Checks")
        st.write("Generated cases are saved as Draft and must be reviewed before they count toward coverage.")
        st.write("Required fields and links to existing requirements are checked before saving.")


# ---------------- MANUAL TEST CASE ENTRY ----------------
elif page == "Manual Test Case Entry":
    st.header("Manual Test Case Entry")
    st.write("Write test cases yourself and link each case to an existing ABC requirement.")
    if not st.session_state.requirements:
        st.warning("Add an ABC requirement before creating a manual test case.")
    else:
        options = {r["id"]: r for r in st.session_state.requirements}
        selected = st.selectbox("Select the requirement", list(options), key="manual_req_select")
        st.info(options[selected].get("description", ""))
        if "manual_timer_started_at" not in st.session_state:
            st.session_state.manual_timer_started_at = None
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Start manual creation timer", use_container_width=True):
                st.session_state.manual_timer_started_at = time.perf_counter()
                st.success("Timer started. Begin writing your test case.")
        with c2:
            if st.session_state.manual_timer_started_at is None:
                st.caption("Start the timer before writing to record creation time.")
            else:
                st.success("Timer is running.")
        with st.form("manual_test_case_form", clear_on_submit=True):
            title = st.text_input("Test Case Title", placeholder="Example: Register with valid details")
            steps = st.text_area("Test Steps", height=120, placeholder="Write the steps a tester should follow.")
            expected = st.text_area("Expected Result", height=90, placeholder="Describe the expected system response.")
            submitted = st.form_submit_button("Save Manual Test Case", use_container_width=True)
        if submitted:
            if not all(x.strip() for x in (title, steps, expected)):
                st.error("Please complete the title, steps, and expected result.")
            else:
                elapsed = None
                if st.session_state.manual_timer_started_at is not None:
                    elapsed = round(time.perf_counter() - st.session_state.manual_timer_started_at, 2)
                case = {
                    "id": next_id(st.session_state.test_cases, "id", "TC"),
                    "requirement_id": selected,
                    "title": title.strip()[:200],
                    "steps": steps.strip()[:2000],
                    "expected_result": expected.strip()[:2000],
                    "source": "Manual",
                    "status": "Draft",
                    "creation_time_seconds": elapsed,
                }
                st.session_state.test_cases.append(case)
                save_data()
                st.session_state.manual_timer_started_at = None
                st.success("Manual test case saved." if elapsed is None else f"Manual test case saved. Time: {elapsed:.2f} seconds.")
                st.rerun()
    st.caption("For a fair comparison, create manual cases for the same requirements used for Gemini.")


# ---------------- REVIEW AND QUALITY SCORING ----------------
elif page == "Review Test Cases":
    st.header("Test Case Review and Quality Scoring")
    st.write("Edit each test case, score its quality, and select a review decision.")
    if not st.session_state.test_cases:
        st.info("Generate or manually add test cases before reviewing them.")
    for i, case in enumerate(st.session_state.test_cases):
        status = case.get("status", "Draft")
        with st.expander(f"{case.get('id', 'TC')} — {case.get('title', 'Untitled')} ({status})"):
            st.write("**Linked Requirement:**", case.get("requirement_id", "N/A"))
            st.write("**Source:**", case.get("source", "Not recorded"))
            with st.form(f"review_form_{i}"):
                title = st.text_input("Test Case Title", value=case.get("title", ""))
                steps = st.text_area("Test Steps", value=case.get("steps", ""))
                expected = st.text_area("Expected Result", value=case.get("expected_result", ""))
                decisions = ["Draft", "Approved", "Rejected"]
                current = case.get("status", "Draft")
                decision = st.selectbox("Review Decision", decisions, index=decisions.index(current) if current in decisions else 0)
                st.markdown("**Quality score (1 = low, 5 = high)**")
                st.caption("Score correctness, clarity, completeness, and relevance to the requirement.")
                correctness = st.slider("Correctness", 1, 5, int(case.get("quality_correctness", 3)))
                clarity = st.slider("Clarity", 1, 5, int(case.get("quality_clarity", 3)))
                completeness = st.slider("Completeness", 1, 5, int(case.get("quality_completeness", 3)))
                relevance = st.slider("Relevance", 1, 5, int(case.get("quality_relevance", 3)))
                save_review = st.form_submit_button("Save Review")
            if save_review:
                if not all(x.strip() for x in (title, steps, expected)):
                    st.error("All test case fields must be completed.")
                else:
                    case.update({
                        "title": title.strip(), "steps": steps.strip(),
                        "expected_result": expected.strip(), "status": decision,
                        "quality_correctness": correctness,
                        "quality_clarity": clarity,
                        "quality_completeness": completeness,
                        "quality_relevance": relevance,
                    })
                    save_data()
                    st.success("Review and quality scores saved.")
                    st.rerun()
    st.info("Only Approved cases count toward requirement coverage. Rejected cases remain in the records but are not counted as approved.")


# ---------------- EVALUATION AND RESULTS ----------------
elif page == "Evaluation and Results":
    st.header("Evaluation and Results")
    st.write("Compare Gemini AI-generated test cases with manually written test cases. Rule-based cases are a third reference group.")
    requirements = st.session_state.requirements
    cases = st.session_state.test_cases
    total_req = len(requirements)
    valid_ids = {r.get("id") for r in requirements}
    groups = {
        "Gemini AI": [c for c in cases if c.get("source") == "Gemini AI"],
        "Manual": [c for c in cases if c.get("source") == "Manual"],
        "Rule-based prototype": [c for c in cases if c.get("source") == "Rule-based prototype"],
    }
    metrics = {name: source_metrics(items, total_req, valid_ids) for name, items in groups.items()}

    rows = []
    measures = [
        ("Total test cases", "total", lambda v: str(v), "Reported"),
        ("Approved test cases", "approved", lambda v: str(v), "Reported"),
        ("Requirement coverage", "coverage", lambda v: f"{v:.1f}%", "Higher"),
        ("Duplicate rate", "duplicate_rate", lambda v: f"{v:.1f}%", "Lower"),
        ("Average quality score", "quality", lambda v: f"{v:.2f} / 5" if v is not None else "Not scored", "Higher"),
        ("Total creation time", "creation_time", lambda v: f"{v:.2f} sec" if v is not None else "Not recorded", "Lower"),
        ("Average creation time per case", "average_creation_time", lambda v: f"{v:.2f} sec" if v is not None else "Not recorded", "Lower"),
    ]
    for label, key, fmt, preferred in measures:
        row = {"Measure": label, "Preferred result": preferred}
        for source in groups:
            row[source] = fmt(metrics[source][key])
        rows.append(row)
    st.subheader("Comparison of Generation Methods")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Coverage counts approved linked requirements using the same total requirement count for each method. Duplicate checks are exact normalized matches within each source.")

    st.subheader("Coverage and Duplicate Rate")
    chart = [{"Method": s, "Coverage (%)": metrics[s]["coverage"], "Duplicate rate (%)": metrics[s]["duplicate_rate"]} for s in groups]
    st.bar_chart(chart, x="Method", y=["Coverage (%)", "Duplicate rate (%)"])

    st.subheader("Creation Time")
    time_chart = [{"Method": s, "Total seconds": metrics[s]["creation_time"] or 0} for s in groups]
    st.bar_chart(time_chart, x="Method", y="Total seconds")
    avg_chart = [{"Method": s, "Average seconds per case": metrics[s]["average_creation_time"] or 0} for s in groups]
    st.bar_chart(avg_chart, x="Method", y="Average seconds per case")
    st.caption("Gemini time measures the API generation call for a batch. Manual time measures the timer interval from Start until one case is saved. These are approximate workflow measurements.")

    st.subheader("Quality Score")
    quality_chart = [{"Method": s, "Average score out of 5": metrics[s]["quality"] or 0} for s in groups]
    st.bar_chart(quality_chart, x="Method", y="Average score out of 5")
    st.caption("Quality is a human reviewer score across correctness, clarity, completeness, and relevance. Only cases with saved scores are included.")

    if not groups["Gemini AI"] or not groups["Manual"]:
        st.warning("A full AI-versus-Manual comparison needs cases from both methods. Create manual cases for the same requirements used for Gemini.")
    if cases:
        st.subheader("Test Case Records")
        record_rows = []
        for c in cases:
            vals = [c.get(k) for k in ("quality_correctness", "quality_clarity", "quality_completeness", "quality_relevance")]
            quality = f"{sum(vals) / 4:.2f}/5" if all(isinstance(v, (int, float)) for v in vals) else "Not scored"
            record_rows.append({
                "Test Case ID": c.get("id", ""), "Source": c.get("source", ""),
                "Requirement ID": c.get("requirement_id", ""), "Title": c.get("title", ""),
                "Status": c.get("status", "Draft"), "Quality": quality,
            })
        st.dataframe(record_rows, use_container_width=True, hide_index=True)

    st.subheader("Evaluation Formulas")
    st.write("**Requirement coverage** = (Requirements Covered by Approved Cases / Total Requirements) × 100")
    st.write("**Duplicate rate** = (Duplicate Cases within a Source / Total Cases from that Source) × 100")
    st.write("**Average quality** = Average of correctness, clarity, completeness, and relevance reviewer scores.")
    st.write("**Creation time** = Recorded Gemini batch generation time or manual authoring timer.")

    st.subheader("Possible Duplicate Test Cases")
    for source, source_cases in groups.items():
        duplicates = find_duplicate_cases(source_cases)
        with st.expander(f"{source}: {len(duplicates)} possible duplicate(s)"):
            if duplicates:
                for c in duplicates:
                    st.write(f"- {c.get('id')} — {c.get('title')}")
            else:
                st.write("No exact duplicates found within this source group.")

    # Export both comparison summaries and case-level records.
    export_rows = []
    for source, result in metrics.items():
        for label, key in [
            ("Total test cases", "total"), ("Approved test cases", "approved"),
            ("Requirements covered", "covered"), ("Coverage (%)", "coverage"),
            ("Duplicate count", "duplicates"), ("Duplicate rate (%)", "duplicate_rate"),
            ("Average quality score", "quality"), ("Total creation time seconds", "creation_time"),
            ("Average creation time per case seconds", "average_creation_time"),
        ]:
            value = result[key]
            export_rows.append({"Record Type": "Summary", "Source": source, "Metric": label,
                                "Value": round(value, 2) if isinstance(value, (int, float)) else "Not recorded"})
    for c in cases:
        export_rows.append({
            "Record Type": "Test Case", "Source": c.get("source", ""),
            "Test Case ID": c.get("id", ""), "Requirement ID": c.get("requirement_id", ""),
            "Title": c.get("title", ""), "Steps": c.get("steps", ""),
            "Expected Result": c.get("expected_result", ""), "Status": c.get("status", ""),
            "Creation Time Seconds": c.get("creation_time_seconds", c.get("generation_time_seconds", "")),
            "Correctness": c.get("quality_correctness", ""), "Clarity": c.get("quality_clarity", ""),
            "Completeness": c.get("quality_completeness", ""), "Relevance": c.get("quality_relevance", ""),
        })
    buffer = io.StringIO()
    fields = ["Record Type", "Source", "Metric", "Value", "Test Case ID", "Requirement ID",
              "Title", "Steps", "Expected Result", "Status", "Creation Time Seconds",
              "Correctness", "Clarity", "Completeness", "Relevance"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(export_rows)
    st.download_button("Download Comparison Report (CSV)", buffer.getvalue(),
                       "AI_vs_Manual_Test_Case_Comparison.csv", "text/csv")
    st.caption("Older cases are preserved. Historical timing and quality cannot be recreated; score older cases through Review Test Cases if needed.")


# ---------------- AI GUARDRAILS ----------------
elif page == "AI Guardrails":
    st.header("AI Guardrails")
    st.write("Rules and controls designed to make test-case generation safe and suitable for human review.")
    guardrails = [
        ("1. Input Validation", "Implemented", "Blank ABC fields and overly long requirements are rejected."),
        ("2. Output Validation", "Implemented", "Generated cases are checked for required fields and valid requirement links."),
        ("3. Human Review", "Implemented", "Generated cases remain Draft until a reviewer edits, scores, approves, or rejects them."),
        ("4. Data Privacy", "Important limitation", "The selected requirement is sent to Google's Gemini API for AI generation. Do not enter passwords, personal information, or confidential data."),
        ("5. API Key Security", "Implemented for local use", "The key is read from Streamlit secrets or an environment variable, not hard-coded in app.py."),
        ("6. Error Handling", "Implemented", "Missing keys, API failures, invalid JSON, and invalid generated fields are handled."),
        ("7. Usage Limits", "Partially controlled", "Each generation request is limited to eight cases. Google's service quotas still apply."),
    ]
    for title, status, detail in guardrails:
        st.subheader(title)
        st.info(f"{status}: {detail}")
    st.caption("These controls reduce common risks but do not guarantee every AI-generated test case is correct. Human review is required.")
