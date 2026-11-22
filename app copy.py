import json
import re
import csv
import io
import os
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
    """Load saved requirements and test cases from data.json."""
    if not DATA_FILE.exists():
        return {"requirements": [], "test_cases": []}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        requirements = data.get("requirements", [])
        test_cases = data.get("test_cases", [])

        # Keep older records. The old field was called "actor".
        # Its value is carried forward so existing data is not lost.
        for requirement in requirements:
            if "action" not in requirement and "actor" in requirement:
                requirement["action"] = requirement.get("actor", "")
                requirement["_legacy_abc_migration"] = True

        return {
            "requirements": requirements,
            "test_cases": test_cases,
        }

    except (json.JSONDecodeError, OSError, TypeError):
        return {"requirements": [], "test_cases": []}


def save_data():
    """Save current application data to data.json."""
    data = {
        "requirements": st.session_state.requirements,
        "test_cases": st.session_state.test_cases,
    }

    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


if "requirements" not in st.session_state or "test_cases" not in st.session_state:
    saved_data = load_data()

    if "requirements" not in st.session_state:
        st.session_state.requirements = saved_data["requirements"]

    if "test_cases" not in st.session_state:
        st.session_state.test_cases = saved_data["test_cases"]


# ---------------- HELPER FUNCTIONS ----------------

def next_id(items, field, prefix):
    """Create the next ID without reusing an existing number."""
    highest_number = 0

    for item in items:
        value = str(item.get(field, ""))
        match = re.search(r"(\d+)$", value)
        if match:
            highest_number = max(highest_number, int(match.group(1)))

    return f"{prefix}-{highest_number + 1:03d}"


def make_requirement_description(action, behavior, constraint):
    return (
        f"Action: {action.strip()} "
        f"Behavior: {behavior.strip()} "
        f"Constraint: {constraint.strip()}"
    )


def generate_cases(requirement):
    """Generate sample test cases using rule-based templates."""
    description = requirement.get("description", "").lower()
    requirement_id = requirement["id"]

    if "login" in description or "log in" in description:
        scenarios = [
            (
                "Valid login details",
                "Enter a registered username and the correct password.",
                "The system should allow the user to log in.",
            ),
            (
                "Invalid password",
                "Enter a registered username and an incorrect password.",
                "The system should reject the login attempt and show an error.",
            ),
            (
                "Invalid username",
                "Enter an unregistered username and a password.",
                "The system should reject the login attempt and show an error.",
            ),
            (
                "Blank username",
                "Leave the username field empty and enter a password.",
                "The system should show a message that the username is required.",
            ),
            (
                "Blank password",
                "Enter a username and leave the password field empty.",
                "The system should show a message that the password is required.",
            ),
        ]

    elif "password reset" in description or "forgot password" in description:
        scenarios = [
            (
                "Password reset with registered email",
                "Open Forgot Password, enter a registered email, and submit the request.",
                "The system should send a password reset link to the registered email.",
            ),
            (
                "Password reset with unregistered email",
                "Enter an email address that is not registered and submit the request.",
                "The system should show a safe message and should not create a reset link for an unknown account.",
            ),
            (
                "Password reset with blank email",
                "Leave the email field empty and submit the request.",
                "The system should show a message that the email address is required.",
            ),
            (
                "Expired password reset link",
                "Open a password reset link after its allowed expiration time.",
                "The system should reject the expired link and ask the user to request a new one.",
            ),
            (
                "Password reset link within time limit",
                "Open the reset link before its expiration time and enter a valid new password.",
                "The system should allow the password to be reset.",
            ),
        ]

    else:
        scenarios = [
            (
                "Valid input",
                "Enter information that follows the requirement.",
                "The system should perform the required behavior.",
            ),
            (
                "Invalid input",
                "Enter information that does not follow the requirement.",
                "The system should reject the invalid input or show an error.",
            ),
            (
                "Missing input",
                "Leave a required input field empty.",
                "The system should identify the missing information.",
            ),
            (
                "Boundary input",
                "Enter a value at the allowed limit.",
                "The system should handle the boundary value correctly.",
            ),
        ]

    generated = []

    for title, steps, expected_result in scenarios:
        generated.append(
            {
                "id": next_id(
                    st.session_state.test_cases + generated,
                    "id",
                    "TC",
                ),
                "requirement_id": requirement_id,
                "title": title,
                "steps": steps,
                "expected_result": expected_result,
                "source": "Rule-based prototype",
                "status": "Draft",
            }
        )

    return generated


def get_gemini_api_key():
    """Read the API key from Streamlit secrets or an environment variable."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

    return api_key or os.environ.get("GEMINI_API_KEY", "")


def generate_cases_with_gemini(requirement):
    """Ask Gemini to create draft test cases for one ABC requirement."""
    api_key = get_gemini_api_key()

    if not api_key:
        raise RuntimeError(
            "Gemini API key was not found. Add GEMINI_API_KEY to "
            ".streamlit/secrets.toml."
        )

    action = requirement.get("action", "")
    behavior = requirement.get("behavior", "")
    constraint = requirement.get("constraint", "")
    requirement_id = requirement["id"]

    prompt = f"""
You are helping a software tester create test cases.

Use only the requirement information below. Do not invent application
features, URLs, field names, or business rules that are not provided.
Create 4 to 6 useful test cases. Include positive, negative, missing-input,
and boundary scenarios when they make sense for this requirement.

ABC requirement:
A - Action: {action}
B - Behavior: {behavior}
C - Constraint: {constraint}

Return ONLY a valid JSON array. Do not use Markdown or code fences.
Each array item must contain exactly these string fields:
"title", "steps", and "expected_result".

Example format:
[
  {{
    "title": "Example test case",
    "steps": "1. Perform an action. 2. Submit the information.",
    "expected_result": "The system should respond as described in the requirement."
  }}
]
"""

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        response_text = response.text or ""
    finally:
        client.close()

    # Accept a plain JSON array or an array surrounded by code fences/text.
    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if not match:
        raise ValueError("Gemini did not return a readable JSON test-case list.")

    generated_items = json.loads(match.group(0))

    if not isinstance(generated_items, list) or not generated_items:
        raise ValueError("Gemini returned an empty or invalid test-case list.")

    if len(generated_items) > 8:
        generated_items = generated_items[:8]

    generated = []
    for item in generated_items:
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        steps = item.get("steps")
        expected_result = item.get("expected_result")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (title, steps, expected_result)
        ):
            continue

        generated.append(
            {
                "id": next_id(
                    st.session_state.test_cases + generated,
                    "id",
                    "TC",
                ),
                "requirement_id": requirement_id,
                "title": title.strip()[:200],
                "steps": steps.strip()[:2000],
                "expected_result": expected_result.strip()[:2000],
                "source": "Gemini AI",
                "status": "Draft",
            }
        )

    if not generated:
        raise ValueError("Gemini's response did not contain valid test cases.")

    return generated


def validate_and_save_generated_cases(new_cases):
    """Validate generated cases before saving them."""
    valid_requirement_ids = {
        item.get("id") for item in st.session_state.requirements
    }

    if not isinstance(new_cases, list) or not new_cases:
        return False, "No test cases were generated."

    if len(new_cases) > 8:
        return False, "The generated response contained too many test cases."

    for case in new_cases:
        required_fields = [
            case.get("title"),
            case.get("steps"),
            case.get("expected_result"),
            case.get("requirement_id"),
        ]

        fields_are_valid = all(
            isinstance(field, str) and field.strip()
            for field in required_fields
        )
        requirement_is_valid = case.get("requirement_id") in valid_requirement_ids

        if not fields_are_valid or not requirement_is_valid:
            return False, "Generated test cases failed validation."

    st.session_state.test_cases.extend(new_cases)
    save_data()
    return True, f"{len(new_cases)} draft test cases generated and checked."


def normalize_text(value):
    """Normalize text for exact duplicate comparison."""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def find_duplicate_cases(cases):
    """Find repeated cases using title, steps, and expected result."""
    seen_signatures = set()
    duplicate_cases = []

    for case in cases:
        signature = (
            normalize_text(case.get("title", "")),
            normalize_text(case.get("steps", "")),
            normalize_text(case.get("expected_result", "")),
        )

        if signature in seen_signatures:
            duplicate_cases.append(case)
        else:
            seen_signatures.add(signature)

    return duplicate_cases


# ---------------- VISUAL STYLE ----------------

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #f5f8fc 0%, #ffffff 48%);
    }
    [data-testid="stSidebar"] {
        background: #10243a;
    }
    [data-testid="stSidebar"] * {
        color: #f4f7fb;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        color: #f4f7fb;
    }
    .main-title {
        font-size: 2.05rem;
        font-weight: 750;
        color: #17324d;
        margin-bottom: 0.1rem;
    }
    .main-subtitle {
        color: #60758a;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }
    .section-note {
        background: #edf4fb;
        border-left: 4px solid #3b82b9;
        padding: 0.8rem 1rem;
        border-radius: 8px;
        color: #24445f;
        margin: 0.6rem 0 1rem 0;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2eaf2;
        padding: 16px 18px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(25, 55, 85, 0.05);
    }
    div[data-testid="stMetricLabel"] {
        color: #526b82;
    }
    div[data-testid="stMetricValue"] {
        color: #17324d;
    }
    div.stButton > button,
    div.stFormSubmitButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------- HEADER AND NAVIGATION ----------------

st.markdown(
    '<div class="main-title">🧪 AI-Assisted Testing Platform</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="main-subtitle">'
    'Software test case generation, review, and evaluation'
    '</div>',
    unsafe_allow_html=True,
)

st.sidebar.title("🧪 Testing Platform")
st.sidebar.caption("Project Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Dashboard",
        "ABC Requirements",
        "Test Case Generation",
        "Review Test Cases",
        "Evaluation and Results",
        "AI Guardrails",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Prototype status")
st.sidebar.info(
    "Gemini AI is available for test-case generation. "
    "Rule-based examples are also available as a fallback."
)


# ---------------- DASHBOARD ----------------

if page == "Dashboard":
    requirements = st.session_state.requirements
    cases = st.session_state.test_cases

    total_requirements = len(requirements)
    total_cases = len(cases)
    approved_count = sum(1 for case in cases if case.get("status") == "Approved")
    draft_count = sum(1 for case in cases if case.get("status") == "Draft")
    rejected_count = sum(1 for case in cases if case.get("status") == "Rejected")

    approved_requirement_ids = {
        case.get("requirement_id")
        for case in cases
        if case.get("status") == "Approved"
    }
    covered_count = sum(
        1 for requirement in requirements
        if requirement.get("id") in approved_requirement_ids
    )
    coverage = (
        covered_count / total_requirements * 100
        if total_requirements
        else 0
    )

    st.header("Project Dashboard")
    st.write("A quick overview of the requirements and test cases in this project.")

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Requirements", total_requirements)
    metric2.metric("Total Test Cases", total_cases)
    metric3.metric("Approved Cases", approved_count)
    metric4.metric("Coverage", f"{coverage:.1f}%")

    st.subheader("Test Case Review Status")
    status_col1, status_col2, status_col3 = st.columns(3)
    status_col1.metric("Draft", draft_count)
    status_col2.metric("Approved", approved_count)
    status_col3.metric("Rejected", rejected_count)

    st.subheader("Requirement Coverage")
    st.progress(int(round(coverage)))
    st.caption(
        f"{covered_count} of {total_requirements} requirements have at least "
        "one approved test case."
    )

    st.divider()
    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Project Workflow")
        st.markdown(
            """
            1. **Add requirements** using Action, Behavior, and Constraint.
            2. **Generate test cases** from a selected requirement.
            3. **Review test cases** and edit, approve, or reject them.
            4. **Evaluate results** using coverage and duplicate checks.
            """
        )

    with right:
        st.subheader("Quick Start")
        st.write("Choose a section from the left navigation to continue.")
        st.info(
            "Start with ABC Requirements if no requirements have been added yet."
            if total_requirements == 0
            else "Your saved project data is loaded. You can continue from any section."
        )

    st.caption(
        "Coverage is based on requirements linked to at least one approved test case. "
        "It does not prove that every possible scenario has been tested."
    )


# ---------------- ABC REQUIREMENTS ----------------

elif page == "ABC Requirements":
    st.header("Software Requirements – ABC Format")
    st.markdown(
        '<div class="section-note">'
        '<b>A = Action</b> — the action being performed. &nbsp; '
        '<b>B = Behavior</b> — how the system should respond. &nbsp; '
        '<b>C = Constraint</b> — a rule or limit the system must follow.'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.form("requirement_form", clear_on_submit=True):
        action = st.text_area(
            "A – Action",
            placeholder="Example: User submits a password reset request.",
            height=75,
        )
        behavior = st.text_area(
            "B – Behavior",
            placeholder="Example: The system sends a reset link to the registered email.",
            height=75,
        )
        constraint = st.text_area(
            "C – Constraint",
            placeholder="Example: The reset link must expire after 15 minutes.",
            height=75,
        )
        submitted = st.form_submit_button("Save Requirement", use_container_width=True)

    if submitted:
        if not action.strip() or not behavior.strip() or not constraint.strip():
            st.error("Please complete all three ABC fields.")
        elif len(action.strip() + behavior.strip() + constraint.strip()) > 2000:
            st.error("The requirement is too long. Please shorten the text.")
        else:
            requirement_id = next_id(
                st.session_state.requirements,
                "id",
                "REQ",
            )
            description = make_requirement_description(
                action,
                behavior,
                constraint,
            )

            st.session_state.requirements.append(
                {
                    "id": requirement_id,
                    "action": action.strip(),
                    "behavior": behavior.strip(),
                    "constraint": constraint.strip(),
                    "description": description,
                }
            )
            save_data()
            st.success(f"{requirement_id} saved successfully.")

    st.divider()
    st.subheader("Saved Requirements")

    if st.session_state.requirements:
        for index, requirement in enumerate(st.session_state.requirements):
            # Support older saved records that used the field name "actor".
            saved_action = requirement.get(
                "action",
                requirement.get("actor", ""),
            )

            with st.expander(
                f"{requirement.get('id', 'REQ')} — "
                f"{saved_action[:65] if saved_action else 'Requirement'}"
            ):
                if requirement.get("_legacy_abc_migration"):
                    st.warning(
                        "This requirement was saved using the old Actor label. "
                        "Please update A – Action with the actual action being performed."
                    )

                with st.form(f"edit_requirement_{index}"):
                    edited_action = st.text_area(
                        "A – Action",
                        value=saved_action,
                        key=f"edit_action_{index}",
                    )
                    edited_behavior = st.text_area(
                        "B – Behavior",
                        value=requirement.get("behavior", ""),
                        key=f"edit_behavior_{index}",
                    )
                    edited_constraint = st.text_area(
                        "C – Constraint",
                        value=requirement.get("constraint", ""),
                        key=f"edit_constraint_{index}",
                    )
                    update = st.form_submit_button("Save Changes")

                if update:
                    if not all(
                        [
                            edited_action.strip(),
                            edited_behavior.strip(),
                            edited_constraint.strip(),
                        ]
                    ):
                        st.error("Please complete all three ABC fields.")
                    elif len(
                        edited_action.strip()
                        + edited_behavior.strip()
                        + edited_constraint.strip()
                    ) > 2000:
                        st.error("The requirement is too long. Please shorten it.")
                    else:
                        requirement["action"] = edited_action.strip()
                        requirement["behavior"] = edited_behavior.strip()
                        requirement["constraint"] = edited_constraint.strip()
                        requirement["description"] = make_requirement_description(
                            edited_action,
                            edited_behavior,
                            edited_constraint,
                        )
                        requirement.pop("actor", None)
                        requirement.pop("_legacy_abc_migration", None)
                        save_data()
                        st.success("Requirement updated.")
                        st.rerun()
    else:
        st.info("No requirements have been added yet.")


# ---------------- TEST CASE GENERATION ----------------

elif page == "Test Case Generation":
    st.header("Test Case Generation")
    st.write(
        "Select a saved requirement and generate draft test cases with Gemini AI "
        "or the rule-based fallback."
    )

    st.info(
        "Gemini receives the selected requirement text to create test cases. "
        "Do not enter passwords, personal information, or confidential data."
    )

    if not st.session_state.requirements:
        st.warning("Please add an ABC requirement first.")
    else:
        requirement_options = {
            item["id"]: item for item in st.session_state.requirements
        }

        selected_id = st.selectbox(
            "Select a requirement",
            list(requirement_options.keys()),
        )
        selected_requirement = requirement_options[selected_id]

        st.info(selected_requirement.get("description", ""))

        ai_column, rule_column = st.columns(2)

        with ai_column:
            if st.button(
                "Generate with Gemini AI",
                type="primary",
                use_container_width=True,
            ):
                try:
                    new_cases = generate_cases_with_gemini(selected_requirement)
                    saved, message = validate_and_save_generated_cases(new_cases)

                    if saved:
                        st.success(message)
                        st.caption(
                            "Gemini-generated cases are saved as Draft. "
                            "Review and approve them before they count toward coverage."
                        )
                    else:
                        st.error(message)

                except Exception as error:
                    st.error(
                        "Gemini could not generate test cases. "
                        f"Error type: {type(error).__name__}. "
                        "You can try again later or use the rule-based option."
                    )

        with rule_column:
            if st.button(
                "Generate Rule-Based Examples",
                use_container_width=True,
            ):
                new_cases = generate_cases(selected_requirement)
                saved, message = validate_and_save_generated_cases(new_cases)

                if saved:
                    st.success(message)
                    st.caption(
                        "These are rule-based examples, not AI-generated output. "
                        "They are saved as Draft for human review."
                    )
                else:
                    st.error(message)

    st.divider()
    st.subheader("Software Behavior Checks")

    st.write(
        "**Q1 – Desired Behavior:** The system generates draft test cases "
        "based on the selected software requirement using Gemini AI or "
        "rule-based templates."
    )

    st.write(
        "**Q2 – Preventative Behavior:** The system checks required output "
        "fields and requirement links before saving generated test cases. "
        "It also rejects blank or oversized requirements."
    )


# ---------------- REVIEW TEST CASES ----------------

elif page == "Review Test Cases":
    st.header("Test Case Review")
    st.write("Review each draft before approving or rejecting it.")

    if not st.session_state.test_cases:
        st.info("Generate test cases before reviewing them.")
    else:
        for index, case in enumerate(st.session_state.test_cases):
            current_status = case.get("status", "Draft")
            with st.expander(
                f"{case.get('id', 'TC')} — {case.get('title', 'Untitled')} "
                f"({current_status})"
            ):
                st.write("**Linked Requirement:**", case.get("requirement_id", "N/A"))
                st.write("**Source:**", case.get("source", "Not recorded"))

                with st.form(f"review_form_{index}"):
                    new_title = st.text_input(
                        "Test Case Title",
                        value=case.get("title", ""),
                    )
                    new_steps = st.text_area(
                        "Test Steps",
                        value=case.get("steps", ""),
                    )
                    new_expected = st.text_area(
                        "Expected Result",
                        value=case.get("expected_result", ""),
                    )
                    decision = st.selectbox(
                        "Review Decision",
                        ["Draft", "Approved", "Rejected"],
                        index=(
                            ["Draft", "Approved", "Rejected"].index(current_status)
                            if current_status in ["Draft", "Approved", "Rejected"]
                            else 0
                        ),
                    )
                    save_review = st.form_submit_button("Save Review")

                if save_review:
                    if not all(
                        [
                            new_title.strip(),
                            new_steps.strip(),
                            new_expected.strip(),
                        ]
                    ):
                        st.error("All test case fields must be completed.")
                    else:
                        case["title"] = new_title.strip()
                        case["steps"] = new_steps.strip()
                        case["expected_result"] = new_expected.strip()
                        case["status"] = decision
                        save_data()
                        st.success("Review saved successfully.")
                        st.rerun()

    
    st.info(
        "Q3 – Responsive Behavior: When a reviewer identifies a "
        "problematic test case, the reviewer can edit it or mark it "
        "as Rejected. The application saves the review decision. "
        "Rejected cases are not counted toward approved test-case coverage."
    )

# ---------------- EVALUATION AND RESULTS ----------------

elif page == "Evaluation and Results":
    st.header("Evaluation and Results")

    requirements = st.session_state.requirements
    cases = st.session_state.test_cases

    approved_cases = [
        case for case in cases
        if case.get("status") == "Approved"
    ]

    valid_requirement_ids = {
        requirement.get("id") for requirement in requirements
    }
    covered_requirements = {
        case.get("requirement_id")
        for case in approved_cases
        if case.get("requirement_id") in valid_requirement_ids
    }

    total_requirements = len(requirements)
    coverage = (
        len(covered_requirements) / total_requirements * 100
        if total_requirements
        else 0
    )

    duplicate_cases = find_duplicate_cases(cases)
    duplicate_count = len(duplicate_cases)
    duplicate_rate = (
        duplicate_count / len(cases) * 100
        if cases
        else 0
    )

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Requirements Covered", len(covered_requirements))
    metric2.metric("Coverage", f"{coverage:.1f}%")
    metric3.metric("Duplicate Rate", f"{duplicate_rate:.1f}%")

    st.subheader("Coverage Progress")
    st.progress(int(round(coverage)))
    st.caption(
        f"{len(covered_requirements)} of {total_requirements} requirements "
        "have at least one approved test case."
    )

    st.divider()
    st.subheader("Evaluation Formulas")
    st.write(
        "**Coverage** = (Requirements Covered / Total Requirements) × 100"
    )
    st.write(
        "**Duplicate Rate** = (Duplicate Cases / Total Test Cases) × 100"
    )
    st.caption(
        "A requirement is counted as covered only when it has at least one "
        "approved linked test case."
    )

    st.subheader("Possible Duplicate Test Cases")
    if duplicate_count:
        st.warning(
            f"{duplicate_count} possible duplicate test case(s) found. "
            "Please review them manually."
        )
        for case in duplicate_cases:
            st.write(f"- {case.get('id', 'TC')} — {case.get('title', 'Untitled')}")
    else:
        st.success("No exact duplicate test cases found.")

    st.caption(
        "Duplicate detection compares the title, steps, and expected result "
        "after normalizing capitalization and extra spaces. It does not detect "
        "all cases that may have similar meanings."
    )

    st.subheader("Test Case Status")
    if cases:
        status_rows = [
            {
                "Test Case ID": case.get("id", ""),
                "Requirement ID": case.get("requirement_id", ""),
                "Title": case.get("title", ""),
                "Status": case.get("status", "Draft"),
            }
            for case in cases
        ]
        st.dataframe(status_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No test cases are available for evaluation.")

    st.caption(
        "These calculations use the current saved application data. "
        "They do not prove that every possible scenario has been tested."
    )


    # EXPORT EVALUATION REPORT

    st.divider()
    st.subheader("Export Evaluation Report")

    export_rows = [
        {
            "Record Type": "Summary",
            "Metric": "Total Requirements",
            "Value": total_requirements,
            "Test Case ID": "",
            "Requirement ID": "",
            "Title": "",
            "Status": ""
        },
        {
            "Record Type": "Summary",
            "Metric": "Requirements Covered",
            "Value": len(covered_requirements),
            "Test Case ID": "",
            "Requirement ID": "",
            "Title": "",
            "Status": ""
        },
        {
            "Record Type": "Summary",
            "Metric": "Coverage",
            "Value": f"{coverage:.1f}%",
            "Test Case ID": "",
            "Requirement ID": "",
            "Title": "",
            "Status": ""
        },
        {
            "Record Type": "Summary",
            "Metric": "Duplicate Rate",
            "Value": f"{duplicate_rate:.1f}%",
            "Test Case ID": "",
            "Requirement ID": "",
            "Title": "",
            "Status": ""
        }
    ]

    for case in cases:
        export_rows.append({
            "Record Type": "Test Case",
            "Metric": "",
            "Value": "",
            "Test Case ID": case.get("id", ""),
            "Requirement ID": case.get("requirement_id", ""),
            "Title": case.get("title", ""),
            "Status": case.get("status", "Draft")
        })

    csv_buffer = io.StringIO()

    fieldnames = [
        "Record Type",
        "Metric",
        "Value",
        "Test Case ID",
        "Requirement ID",
        "Title",
        "Status"
    ]

    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(export_rows)

    st.download_button(
        label="Download Evaluation Report (CSV)",
        data=csv_buffer.getvalue(),
        file_name="AI_Testing_Evaluation_Report.csv",
        mime="text/csv"
    )

elif page == "AI Guardrails":

    st.header("AI Guardrails")
    st.write(
        "Rules and controls designed to make test-case generation "
        "safe, reliable, and suitable for human review."
    )

    st.divider()

    st.subheader("1. Input Validation")
    st.success("Implemented")
    st.write(
        "The system rejects blank ABC fields and requirements "
        "that exceed the allowed input length."
    )

    st.subheader("2. Output Validation")
    st.success("Implemented")
    st.write(
        "Generated test cases are checked for required fields "
        "and valid requirement links before they are saved."
    )

    st.subheader("3. Human Review")
    st.success("Implemented")
    st.write(
        "Generated test cases remain in Draft status until a "
        "reviewer approves or rejects them. Reviewers can edit cases."
    )

    st.subheader("4. Data Privacy")
    st.info("Basic protection through current prototype design")
    st.write(
        "The selected requirement is sent to Google's Gemini API when "
        "Gemini generation is used. Do not enter passwords, personal "
        "information, or confidential requirements. Rule-based generation "
        "does not send requirement text to an external AI service."
    )

    st.subheader("5. API Key Security")
    st.success("Implemented for local use")
    st.write(
        "The Gemini API key is read from Streamlit secrets or an environment "
        "variable. The key is not written directly in app.py. The secrets file "
        "must stay out of GitHub and must be added separately to the hosting "
        "platform's secrets settings when deployed."
    )

    st.subheader("6. Error Handling")
    st.success("Implemented")
    st.write(
        "The application handles missing API keys, Gemini request failures, "
        "unreadable JSON responses, and invalid generated test-case fields. "
        "Failed AI requests are not saved as test cases."
    )

    st.subheader("7. Usage Limits")
    st.info("Partially controlled")
    st.write(
        "The application limits each generation request to a maximum of "
        "eight saved cases. Google AI Studio free-tier quotas and model "
        "availability still apply. The application does not control Google's "
        "service-side rate limits."
    )

    st.divider()

    st.caption(
        "These controls reduce common risks but do not guarantee that every "
        "AI-generated test case is correct. Human review is required before "
        "approval or use."
    )
