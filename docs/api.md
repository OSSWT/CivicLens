# CivicLens API contract

All application endpoints use the `/api` prefix. Report locations are stored as
GeoJSON points in `[longitude, latitude]` order.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service readiness |
| `GET` | `/api/config/public` | Browser-safe map configuration |
| `GET` | `/api/reports` | List and filter recent reports |
| `GET` | `/api/reports/nearby` | Find reports near a coordinate |
| `GET` | `/api/reports/{id}` | Read one report |
| `POST` | `/api/reports` | Create a report with a before photo |
| `PATCH` | `/api/reports/{id}/status` | Update workflow status |
| `POST` | `/api/reports/{id}/after-photo` | Add resolution evidence |
| `DELETE` | `/api/reports/{id}` | Remove a report and its local photos |

Status-changing and delete endpoints require `X-Admin-Key`. Report creation and
photo upload use `multipart/form-data`; all other request and response bodies use
JSON.
