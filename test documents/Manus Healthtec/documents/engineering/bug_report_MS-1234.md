'''# Bug Report: MS-1234 - Patient search fails with special characters

**Reported by:** Emily Williams
**Date:** January 22, 2026
**Severity:** High

## Description

The patient search functionality in the MedSync Platform crashes when a user enters a search query containing special characters (e.g., apostrophes, hyphens).

## Steps to Reproduce

1. Log in to the MedSync Platform.
2. Navigate to the patient search page.
3. Enter a search query containing a special character, such as "O'Connell" or "Smith-Jones".
4. The application returns a 500 error.

## Expected Behavior

The search should correctly handle special characters and return the relevant patient records.

## Actual Behavior

The application throws a 500 error and the search fails.

## Technical Details

- **Error Log:** The backend logs show a SQL syntax error, indicating that the special characters are not being properly escaped.
- **Affected Component:** The bug appears to be in the `patient-service` microservice.

## Proposed Solution

The search query needs to be properly sanitized before being passed to the database. We should use a parameterized query to prevent SQL injection vulnerabilities.
'''
