# Project Status and Test Evidence

## 1. Project Overview

**Project Name:** AI-Assisted Testing Platform

**Current Status:** Working Prototype

The application helps users enter software requirements, generate test cases using the Gemini API, add manual test cases, review test cases, and evaluate results.

## 2. Project Development Status

| Feature | Current Status |
|---|---|
| Streamlit application setup | Completed |
| ABC requirement entry and validation | Completed |
| Gemini API integration | Completed |
| AI test case generation | Completed |
| Manual test case entry | Completed |
| Test case editing | Completed |
| Approve and reject functionality | Completed |
| Quality scoring | Completed |
| Requirement coverage calculation | Completed |
| Duplicate rate calculation | Completed |
| Evaluation and results page | Completed |
| CSV report export | Completed |
| Local JSON data storage | Completed |
| AI Guardrails page | Completed |
| Advanced prompt injection protection | Not implemented |
| Automatic sensitive-data detection | Not implemented |
| Semantic duplicate detection | Not implemented |
| Authentication and multi-user access | Not implemented |

## 3. Testing Evidence

The following activities were confirmed during project development.

| Test ID | Test Activity | Observed Result | Status |
|---|---|---|---|
| TE-01 | Add a software requirement | Requirement was saved successfully. | Confirmed |
| TE-02 | Generate AI test cases | Gemini generated draft test cases. | Confirmed |
| TE-03 | Add a manual test case | Manual test case was added successfully. | Confirmed |
| TE-04 | Review generated test cases | Test cases could be reviewed and scored. | Confirmed |
| TE-05 | Approve and reject test cases | Review decisions were saved successfully. | Confirmed |
| TE-06 | Calculate requirement coverage | Coverage changed based on approved test cases. | Confirmed |
| TE-07 | Export evaluation results | CSV file downloaded and opened in Excel. | Confirmed |

## 4. Additional Tests to Perform

The following tests are recommended but have not yet been confirmed as completed.

| Test ID | Test Activity | Expected Result | Status |
|---|---|---|---|
| TE-08 | Submit blank ABC requirement fields | Application should reject incomplete input. | Pending |
| TE-09 | Submit input above the character limit | Application should reject the input. | Pending |
| TE-10 | Test an invalid Gemini response | Application should reject invalid output. | Pending |
| TE-11 | Test Gemini API failure | Application should display an error message. | Pending |
| TE-12 | Test prompt injection input | Application should be evaluated for unsafe instruction handling. | Pending |
| TE-13 | Test duplicate test cases | Exact duplicates should be identified. | Pending |
| TE-14 | Refresh the application after saving data | Previously saved data should remain available. | Pending |

## 5. Known Limitations

- AI-generated test cases may contain incorrect or unsupported information.
- Human review is required before approving generated test cases.
- Prompt injection protection is not implemented.
- Confidential information is not automatically detected or removed.
- Duplicate detection checks exact matches, not semantic similarity.
- API request-frequency control is not implemented.
- Data is stored locally without application-level authentication or encryption.

## 6. Future Improvements

- Add stronger AI output validation.
- Add prompt injection protection.
- Improve privacy and sensitive-data handling.
- Add API request limits and better error recovery.
- Improve duplicate detection.
- Add more automated and negative test cases.

## 7. Project Completion Summary

The project has developed into a working prototype with Gemini API integration. Users can enter requirements, generate AI test cases, add manual cases, review and approve results, calculate evaluation metrics, and export reports.

Basic testing activities were confirmed during development. Additional negative, boundary, and AI guardrail tests remain to be performed and documented.