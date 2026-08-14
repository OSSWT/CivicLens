# CivicLens zero-cost portfolio deployment

This guide deploys CivicLens as a Render web service backed by MongoDB Atlas.
Reports and photos are both stored in Atlas; photos use GridFS, so Render's
ephemeral filesystem does not cause evidence to disappear after a restart.

This route does not require a paid service or billing-enabled Google project.
It is intended for a portfolio preview. Free web services sleep after
inactivity and can cold-start on the next request; they are not an availability
guarantee.

To keep the deployment charge-free:

- Choose only Atlas **M0**. Do not choose Flex or a dedicated cluster.
- Keep Render on the **Hobby** workspace and **Free** instance from
  `render.yaml`. Do not add a payment method; without one, Render suspends the
  service instead of charging if included usage is exhausted.
- Use a **Google Maps Demo Key**. Do not enable Google Cloud billing.
- Do not add a paid persistent disk, dedicated IP, or paid custom-domain slot.

## 1. Create the MongoDB Atlas database

1. Sign in to [MongoDB Atlas](https://cloud.mongodb.com/) and create a project.
2. Create an **M0 Free** cluster. Do not select **Flex**. Select a supported
   region near the Render Singapore region when possible. Atlas permits one M0
   cluster per project and the free cluster does not expire.
3. In **Database Access**, create a dedicated database user. Give it read/write
   access only to the `civiclens` database and generate a strong password.
4. In **Connect > Drivers**, select Python and copy the SRV connection string.
   Replace the username and password placeholders. Percent-encode special
   characters in credentials when required.
5. Keep the URI private. It should resemble:

   ```text
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

Atlas accepts connections only from entries in the project's IP access list.
The Render ranges are added after the service exists in step 3.

## 2. Create the Render service from the Blueprint

1. Sign in to [Render](https://dashboard.render.com/) and connect the GitHub
   repository `OSSWT/CivicLens`.
2. Keep the workspace on the free **Hobby** plan and do not add a payment
   method. This ensures usage exhaustion suspends the service instead of
   creating an overage charge.
3. Choose **New > Blueprint**, select the repository and `main` branch, and
   apply its `render.yaml`.
4. Confirm the service instance is **Free** before applying the Blueprint.
5. When Render prompts for the secret environment variable, paste the Atlas URI
   into `CIVICLENS_MONGO_URI`. Google Maps is intentionally left disabled until
   the separate no-billing setup in step 5.
6. Render generates `CIVICLENS_ADMIN_API_KEY`. Save that value in a password
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

## 5. Enable Google Maps without billing

1. Sign in to Google's
   [Maps Demo Key page](https://developers.google.com/maps/documentation/javascript/demo-key).
2. Select **Get a Demo Key** and accept the Maps Demo Project terms. Do not add
   or enable a billing account.
3. Copy the generated Demo Key.
4. In Render, add `CIVICLENS_GOOGLE_MAPS_API_KEY` with the Demo Key as its value
   and redeploy the service.
5. Confirm the interactive map, report markers, and map-click location input
   work. If the daily demo limit is reached, Maps pauses until the next day with
   no charge; the CivicLens list view remains usable.

The Demo Key supports the Maps JavaScript rendering, markers, and events used by
CivicLens, but Google defines it as testing/prototyping only. The browser must
receive it to load Maps JavaScript API. The Atlas URI and admin key must never
be exposed to the browser or committed to Git.

## 6. Final operational checks

- Confirm GitHub Actions passes before each Render auto-deploy.
- Check Render logs for startup, health-check, or Atlas authentication errors.
- Test create, nearby search, admin status update, after-photo, and deletion.
- Review and customize the Privacy Notice and Terms for the actual operator and
  intended jurisdiction before sharing the deployment broadly.
- Rotate the Atlas password, admin key, and Maps key if any secret is exposed.
- Do not click an Atlas, Render, or Google upgrade/billing prompt while using
  this zero-cost route.
- Add moderation, rate limiting, authenticated roles, backups, and managed
  object storage before moving beyond a portfolio/demo workload.

## Environment reference

| Variable | Portfolio cloud value | Secret |
| --- | --- | --- |
| `CIVICLENS_ENVIRONMENT` | `production` | No |
| `CIVICLENS_USE_IN_MEMORY` | `false` | No |
| `CIVICLENS_PHOTO_STORAGE` | `mongodb` | No |
| `CIVICLENS_MONGO_DATABASE` | `civiclens` | No |
| `CIVICLENS_MONGO_URI` | Atlas SRV URI | Yes |
| `CIVICLENS_GOOGLE_MAPS_API_KEY` | No-cost Maps Demo Key | Public-by-design |
| `CIVICLENS_ADMIN_API_KEY` | Render-generated 256-bit value | Yes |
| `CIVICLENS_MAX_UPLOAD_MB` | `8` | No |
