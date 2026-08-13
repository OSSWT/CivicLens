# CivicLens

CivicLens is a full-stack community issue reporting platform. Residents pin a
public-space problem, upload photo evidence, and follow it from the initial
report to resolution. The application combines geospatial search, an explicit
REST API, and explainable OpenCV image-quality checks in one portfolio project.

## What it demonstrates

- Python and FastAPI backend development
- RESTful API design with generated OpenAPI, Swagger UI, and ReDoc
- MongoDB GeoJSON storage and a `2dsphere` index for nearby search
- Google Maps JavaScript API with Advanced Markers and map-based location input
- OpenCV checks for blur, brightness, resolution, and before/after visual change
- Bootstrap responsive layouts and jQuery AJAX interactions
- Layered repositories, environment-based configuration, and automated testing

These are deliberately different from the local-only vanilla JavaScript work in
Dayline and the native Kotlin/Room architecture in KeepSpot.

## Features

- Create reports for potholes, flooding, waste, streetlights, sidewalks, or other issues
- Select exact coordinates by clicking the map or entering latitude/longitude
- Inspect image resolution, brightness, and Laplacian blur score before storage
- Browse, filter, and find reports within a 5 km radius
- Display report status with distinct Google Maps Advanced Markers
- Protect status changes, resolution uploads, and deletion with an admin API key
- Upload after photos and calculate visible difference plus histogram similarity
- Continue using the report list when no Google Maps API key is configured
- Use MongoDB for persistent operation or an in-memory repository for a zero-setup demo

## Architecture

```text
Browser
|-- Bootstrap 5 responsive UI
|-- jQuery AJAX and event handling
`-- Google Maps JavaScript API
          |
          | HTTP / multipart REST API
          v
FastAPI application
|-- Request validation and OpenAPI documentation
|-- OpenCV image analysis
|-- Local photo storage
`-- Repository interface
    |-- MongoDB + GeoJSON + 2dsphere index
    `-- In-memory test/demo repository
```

## Quick start: zero-setup demo

This mode does not require MongoDB. Reports are reset when the server restarts.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set this value in `.env`:

```dotenv
CIVICLENS_USE_IN_MEMORY=true
```

Then run:

```powershell
python -m app
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at
<http://127.0.0.1:8000/docs>, with ReDoc at
<http://127.0.0.1:8000/redoc>.

## Persistent MongoDB setup

Use either MongoDB Atlas or the included Compose service:

```powershell
docker compose up -d mongo
```

Configure `.env`:

```dotenv
CIVICLENS_MONGO_URI=mongodb://localhost:27017
CIVICLENS_MONGO_DATABASE=civiclens
CIVICLENS_USE_IN_MEMORY=false
```

The application creates these indexes during startup:

- `location: 2dsphere`
- `status + category + created_at`

Optional synthetic demo records can be created after MongoDB is running:

```powershell
python scripts\seed_demo.py
```

## Google Maps setup

The list-based experience works without a map key. To enable the interactive
map, add a Maps JavaScript API key:

```dotenv
CIVICLENS_GOOGLE_MAPS_API_KEY=your-key-here
```

For deployment, restrict the key to the production website origin and restrict
its API access to Maps JavaScript API. Browser map keys are intentionally sent
to the client; restrictions, not secrecy, protect them. Never commit `.env`.

## Administration

Set a strong value before deployment:

```dotenv
CIVICLENS_ADMIN_API_KEY=replace-with-a-long-random-value
```

The web interface sends it as `X-Admin-Key` for status updates, after-photo
uploads, and deletion. This is an MVP administration boundary; a production
multi-user version should replace it with authenticated accounts and roles.

## API overview

| Method | Endpoint | Access |
| --- | --- | --- |
| `GET` | `/api/health` | Public |
| `GET` | `/api/config/public` | Public |
| `GET` | `/api/reports` | Public |
| `GET` | `/api/reports/nearby` | Public |
| `GET` | `/api/reports/{id}` | Public |
| `POST` | `/api/reports` | Public |
| `PATCH` | `/api/reports/{id}/status` | Admin |
| `POST` | `/api/reports/{id}/after-photo` | Admin |
| `DELETE` | `/api/reports/{id}` | Admin |

The full contract is documented in [docs/api.md](docs/api.md) and exposed by
the running application's OpenAPI schema.

## Quality checks

```powershell
python -m ruff check app tests scripts
python -m ruff format --check app tests scripts
python -m pytest --cov=app --cov-report=term-missing
node --check app\static\app.js
```

The tests cover image analysis, invalid uploads, GeoJSON coordinate order,
nearby distance sorting, combined filters, admin authorization, report CRUD,
photo cleanup, and before/after analysis. GitHub Actions additionally starts a
real MongoDB 8 service and executes the geospatial CRUD integration test on
every push and pull request to `main`.

## Privacy and production notes

- Photos are stored in `data/uploads` and are excluded from Git.
- The server accepts only JPEG, PNG, and WebP files and enforces a size limit.
- OpenCV scores evidence quality; it does not claim to identify or classify hazards.
- Location reports may reveal sensitive patterns. A public deployment should add
  moderation, retention rules, rate limiting, and location privacy guidance.
- Local photo storage is suitable for development. A scaled deployment should
  use managed object storage and signed upload/download policies.

## License

Released under the [MIT License](LICENSE).
