# MedSync Platform API Documentation

**Version:** 2.0
**Base URL:** https://api.medsynchealth.com/v2

## Authentication

All API requests require OAuth 2.0 authentication. Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## Endpoints

### GET /patients

Retrieve a list of patients.

**Query Parameters:**
- `limit` (optional): Number of results to return (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "patients": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "first_name": "John",
      "last_name": "Doe",
      "mrn": "MRN12345"
    }
  ]
}
```

### POST /patients

Create a new patient record.

**Request Body:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "date_of_birth": "1980-01-15",
  "mrn": "MRN67890"
}
```
