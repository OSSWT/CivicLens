# CivicLens portfolio deployment

This guide deploys CivicLens as a Render web service backed by MongoDB Atlas.
Reports and photos are both stored in Atlas; photos use GridFS, so Render's
ephemeral filesystem does not cause evidence to disappear after a restart.

The included free Render plan is intended for a portfolio preview. Free web
services sleep after inactivity and can cold-start on the next request. Upgrade
the service before treating availability as a production requirement.

## 1. Create the MongoDB Atlas database

1. Sign in to [MongoDB Atlas](https://cloud.mongodb.com/) and create a project
   and cluster. Select a region near the Render Singapore region when possible.
2. In **Database Access**, create a dedicated database user. Give it read/write
   access only to the `civiclens` database and generate a strong password.
3. In **Connect > Drivers**, select Python and copy the SRV connection string.
   Replace the username and password placeholders. Percent-encode special
   characters in credentials when required.
4. Keep the URI private. It should resemble:

   ```text
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

Atlas accepts connections only from entries in the project's IP access list.
The Render ranges are added after the service exists in step 3.

## 2. Create the Render service from the Blueprint

1. Sign in to [Render](https://dashboard.render.com/) and connect the GitHub
   repository `OSSWT/CivicLens`.
2. Choose **New > Blueprint**, select the repository and `main` branch, and
   apply its `render.yaml`.
3. When Render prompts for the secret environment variable, paste the Atlas URI
   into `CIVICLENS_MONGO_URI`. Google Maps is intentionally left disabled until
   the exact Render hostname is available in step 5.
4. Render generates `CIVICLENS_ADMIN_API_KEY`. Save that value in a password
   manager; it is required for status changes, resolution photos, and deletion.

The first deploy can fail to connect to Atlas until its outbound ranges are
allowlisted. That is expected; the created service provides the ranges needed
for the next step.

## 3. Restrict Atlas to Render outbound traffic

1. Open the new Render service.
2. Choose **Connect > Outbound** and copy every displayed CIDR range.
3. In Atlas, open **Network Access > IP Access List** and add every Render range.
4. Remove broad entries such as `0.0.0.0/0` if one was added during setup.
5. In Render, retry the latest deploy.

The application creates its `2dsphere` and filter indexes at startup. A healthy
deployment returns `{"status":"ok"}` from `/api/health`; this endpoint also
pings MongoDB, so it returns HTTP 503 when the database is unavailable.

## 4. Verify the database-only deployment

Open these URLs using the hostname Render assigned:

- `/` — CivicLens interface, initially with list fallback instead of the map
- `/api/health` — service and database readiness
- `/docs` — interactive OpenAPI documentation
- `/privacy` and `/terms` — public policy pages

Create a test report, reload the application, and confirm that both the report
and its photo remain available.

## 5. Enable and restrict Google Maps

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select
   a project and configure billing for Google Maps Platform.
2. Enable only **Maps JavaScript API** for this application.
3. Create an API key. Under **Application restrictions**, select **Websites**
   and add the exact Render origin:

   ```text
   https://<your-service>.onrender.com/*
   ```

   Add the custom-domain origin too if one is configured later.
4. Under **API restrictions**, restrict the key to **Maps JavaScript API**.
5. In Render, set `CIVICLENS_GOOGLE_MAPS_API_KEY` to the restricted key and
   redeploy the service.
6. Confirm the interactive map loads, then review Google Cloud quotas and
   billing alerts.

The browser must receive this map key to load Maps JavaScript API. Website and
API restrictions are therefore the security boundary; the Atlas URI and admin
key must never be exposed to the browser or committed to Git.

## 6. Final operational checks

- Confirm GitHub Actions passes before each Render auto-deploy.
- Check Render logs for startup, health-check, or Atlas authentication errors.
- Test create, nearby search, admin status update, after-photo, and deletion.
- Review and customize the Privacy Notice and Terms for the actual operator and
  intended jurisdiction before sharing the deployment broadly.
- Rotate the Atlas password, admin key, and Maps key if any secret is exposed.
- Use paid hosting, backups, moderation, rate limiting, authenticated roles, and
  managed object storage before moving beyond a portfolio/demo workload.

## Environment reference

| Variable | Portfolio cloud value | Secret |
| --- | --- | --- |
| `CIVICLENS_ENVIRONMENT` | `production` | No |
| `CIVICLENS_USE_IN_MEMORY` | `false` | No |
| `CIVICLENS_PHOTO_STORAGE` | `mongodb` | No |
| `CIVICLENS_MONGO_DATABASE` | `civiclens` | No |
| `CIVICLENS_MONGO_URI` | Atlas SRV URI | Yes |
| `CIVICLENS_GOOGLE_MAPS_API_KEY` | Restricted browser key | Public-by-design |
| `CIVICLENS_ADMIN_API_KEY` | Render-generated 256-bit value | Yes |
| `CIVICLENS_MAX_UPLOAD_MB` | `8` | No |
