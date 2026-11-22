# AI Guardrails

## 1. Purpose

This document describes the safety measures currently used in the AI-Assisted Testing Platform. It also identifies risks and improvements needed when using AI to generate software test cases.

## 2. Current Guardrails

| Guardrail | Current Status | Description |
|---|---|---|
| Input validation | Implemented | Checks that required ABC fields are not empty and follow the input length limit. |
| AI output validation | Partially implemented | Checks the response format and required test case fields. |
| Human review | Implemented | Users can review, edit, approve, or reject generated test cases. |
| API key handling | Partially implemented | Reads the API key from Streamlit secrets or an environment variable instead of placing it directly in the application code. |
| Error handling | Partially implemented | Handles API errors and displays an error message. |
| Data privacy | Partially implemented | Users are advised not to enter confidential information. Automatic sensitive-data detection is not available. |
| Prompt injection protection | Not implemented | The application does not have a separate prompt injection detection or prevention mechanism. |
| API usage control | Partially implemented | Limits the number of cases processed in a generation batch, but does not limit request frequency. |

## 3. Main AI Risks

| Risk ID | Risk | Possible Impact | Priority |
|---|---|---|---|
| R1 | Incorrect AI-generated test cases | Important test scenarios may be missed. | High |
| R2 | Prompt injection | Untrusted requirement text may influence AI instructions. | High |
| R3 | Sensitive information exposure | Private information may be sent to an external AI service. | High |
| R4 | Invalid AI response | The application may not process the generated response correctly. | Medium |
| R5 | Gemini API failure | Test case generation may become unavailable. | Medium |
| R6 | Excessive API requests | API limits may be reached. | Medium |

These priorities are preliminary assessments based on possible impact and likelihood.

## 4. Proposed ABC Guardrail Requirements

| ID | Actor | Behavior | Constraint |
|---|---|---|---|
| GR-01 | Application | shall validate user requirements | before sending them to the AI service |
| GR-02 | Application | shall validate generated test cases | before saving them |
| GR-03 | Tester | shall review AI-generated test cases | before approving them |
| GR-04 | Application | shall protect the API key | by keeping it outside the application source code |
| GR-05 | Application | shall warn users about sensitive information | before submitting requirements to the external AI service |
| GR-06 | Application | shall handle API errors | without exposing secret information |
| GR-07 | Application | shall limit generated cases per request | to the configured maximum |
| GR-08 | Application | shall identify duplicate test cases | using the current exact-match comparison method |

These are proposed requirements. They should not all be considered implemented.

## 5. Recommended Improvements

1. Add stronger validation for AI-generated responses.
2. Add prompt injection protection.
3. Add automatic checks for sensitive information.
4. Improve API error messages and recovery.
5. Add request-frequency limits.
6. Improve duplicate detection.
7. Keep human review as a required step before approval.

## 6. Verification Plan

The following checks are recommended for future testing:

| Test | Expected Result | Status |
|---|---|---|
| Submit empty requirement fields | Application rejects incomplete input. | Pending |
| Submit very long requirement text | Application rejects input beyond the limit. | Pending |
| Provide an invalid AI response | Application does not save invalid test cases. | Pending |
| Simulate an API failure | Application displays an error message. | Pending |
| Submit prompt injection text | Application is evaluated for unsafe instruction handling. | Pending |
| Enter sensitive information | Privacy risks are reviewed. | Pending |
| Generate duplicate cases | Exact duplicate cases are identified. | Pending |

## 7. Known Limitations

- AI-generated results are not guaranteed to be correct.
- Output validation checks structure and required fields, not factual or semantic correctness.
- Prompt injection protection is not currently implemented.
- Sensitive information is not automatically detected or removed.
- Duplicate detection does not identify similar cases with different wording.
- API request-frequency limits are not implemented.
- Local application data does not have application-level authentication or encryption.

## 8. Conclusion

The project includes basic guardrails such as input validation, AI response checks, API key handling, and human review. However, additional protections are needed before the application could be used in a production environment.

The current version is an academic prototype designed to demonstrate AI-assisted test case generation and evaluation.