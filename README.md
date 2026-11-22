# AI-Assisted Testing Platform

## 1. Project Description

The AI-Assisted Testing Platform is a web application developed using Python and Streamlit. It helps software testers create, review, and evaluate test cases from software requirements.

The application uses the Gemini API to generate draft test cases. Users can also add test cases manually, review generated cases, and evaluate testing results.

## 2. Main Features

- **ABC Requirements:** Enter requirements using Action, Behavior, and Constraint.
- **AI Test Case Generation:** Generate draft test cases using the Gemini API.
- **Manual Test Case Entry:** Add test cases manually.
- **Test Case Review:** Edit, approve, or reject test cases.
- **Quality Evaluation:** Score test cases based on correctness, clarity, completeness, and relevance.
- **Requirement Coverage:** Calculate coverage using approved test cases.
- **Duplicate Detection:** Identify exact duplicate test cases.
- **Evaluation and Results:** View testing metrics and compare results.
- **CSV Export:** Download evaluation results.
- **AI Guardrails:** View the application's current AI safety controls and limitations.
- **Data Persistence:** Save project data locally in a JSON file.

## 3. Technologies Used

- Python
- Streamlit
- Google Gemini API
- Google Gen AI Python SDK
- JSON for local data storage
- CSV for exporting results

## 4. Project Requirements

- Python 3.10 or a compatible supported version
- Internet connection for Gemini API generation
- Gemini API key
- Required Python packages

## 5. Installation and Setup

### Step 1: Download or Clone the Project

Download the project or clone the GitHub repository.

### Step 2: Open the Project Folder

Open a terminal in the project folder.

### Step 3: Install Dependencies

Run:

```bash
pip install -r requirements.txt
```

### Step 4: Configure the Gemini API Key

Create a folder named `.streamlit` in the project folder if it does not already exist.

Inside that folder, create a file named `secrets.toml`.

Add your Gemini API key:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

Replace `YOUR_GEMINI_API_KEY` with your own API key.

**Important:** Do not share your API key or upload the `secrets.toml` file to GitHub.

### Step 5: Run the Application

Run:

```bash
streamlit run app.py
```

The application will open in your web browser.

## 6. Data Storage

The application saves requirements and test cases in a local file named `data.json`.

The data file is created and updated by the application. Keep a backup of this file to protect saved project information.

## 7. Evaluation Metrics

**Requirement Coverage**

Coverage = (Requirements Covered / Total Requirements) × 100

Only requirements linked to at least one approved test case count as covered.

**Duplicate Rate**

Duplicate Rate = (Duplicate Cases / Total Test Cases) × 100

The current duplicate detection checks exact matches after normalizing test case information. It does not identify all similar or meaning-based duplicates.

**Test Case Quality**

Test cases can be scored from 1 to 5 for:

- Correctness
- Clarity
- Completeness
- Relevance

These scores are based on human review.

## 8. AI Guardrails and Limitations

The application includes basic input validation, AI response validation, and human review.

The API key is read from Streamlit secrets or an environment variable instead of being hardcoded in the main application file.

Some protections are still limited or not implemented:

- Prompt injection detection and prevention.
- Automatic detection of confidential information.
- Semantic duplicate detection.
- Independent verification of AI-generated test case accuracy.
- Request-frequency limits.
- Authentication and multi-user access control.

AI-generated test cases should always be reviewed before approval.

## 9. Important Notes

- Gemini API generation requires an internet connection and a valid API key.
- Each user who runs the application with Gemini generation enabled must configure their own API key.
- API availability and usage limits depend on the provider and account.
- Existing project data is stored locally and is not automatically shared between different computers.
- The application is an academic prototype and is not intended to replace professional software testing or security review.

## 10. Project Status

The project includes requirement entry, Gemini-based test case generation, manual test case entry, review and approval, evaluation metrics, local data storage, and CSV export.

Further improvements to AI safety, security, and advanced test evaluation remain possible future work.