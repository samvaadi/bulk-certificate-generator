# Bulk Certificate Generator Backend

A FastAPI service that accepts a recipient batch, creates a tracked job, and renders a separate PDF for every recipient. SQLite stores job and recipient state; generated files are stored beneath `storage/certificates/<job_id>/`.

## Architecture

```text
Client --POST /jobs--> FastAPI --> SQLite (job + recipients)
                             \--> BackgroundTasks worker
                                   | per-recipient render + isolated result commit
                                   v
                              Jinja2 template --> ReportLab PDF --> local storage
Client <-- status / PDF / ZIP -- FastAPI -- SQLite + storage
```

The HTML template is loaded and rendered with Jinja2 for each recipient. ReportLab draws the certificate as a vector PDF without requiring a native HTML rendering dependency. It follows the supplied certificate layout and uses the same template context.

## Setup and run

Requires Python 3.11 or later.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The default database is `certificates.db` in the project directory. Set `DATABASE_URL` to use another SQLAlchemy database URL and `CERTIFICATE_STORAGE_DIR` to change the output directory. The app creates its tables on startup.

## API

Interactive API documentation is available at `/docs`.

### Create a generation job

`POST /api/v1/jobs` returns `202 Accepted` and a job ID. Recipient email addresses are validated; `metadata` accepts arbitrary JSON key/value data including `grade`, `certificate_title`, and `issuer_name`.

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"event_name":"Python Workshop","issue_date":"2026-10-09","recipients":[{"recipient_name":"Ada Lovelace","recipient_email":"ada@example.com","metadata":{"grade":"A","issuer_name":"Training Team"}}]}'
```

Response fields: `job_id`, `status`, `total_recipients`, `created_at`, and `status_check_url`.

### Poll job status

`GET /api/v1/jobs/{job_id}` reports `PENDING`, `IN_PROGRESS`, `COMPLETED`, `PARTIALLY_COMPLETED`, or `FAILED`, counts, a 0–100 progress percentage, and each recipient's result. Successful recipients include `download_url`.

```bash
curl http://localhost:8000/api/v1/jobs/JOB_ID
```

### Download certificates

```bash
curl -OJ http://localhost:8000/api/v1/certificates/RECIPIENT_ID/download
curl -OJ http://localhost:8000/api/v1/jobs/JOB_ID/download-all
```

The first endpoint returns a PDF. The second returns a ZIP of successful certificates; failed recipients are omitted. An empty job archive is valid if no certificates succeeded.

## Design decisions

- **202 and background execution:** request validation and database persistence happen before returning; rendering is delegated to FastAPI `BackgroundTasks` so the client can poll instead of waiting for PDF generation.
- **Worker choice:** the built-in background task keeps deployment simple for this assignment. It runs in the API process and is not a durable queue; multi-process or restart-safe production deployments should replace it with a persistent task broker.
- **Failure isolation:** each recipient has its own exception boundary and database commit. A failed render increments `failed_count` and records an error while later recipients continue.
- **Storage and ZIPs:** PDFs are stored individually on disk. ZIP contents are copied in bounded chunks from each file into a temporary disk-backed archive, so the PDFs and archive are not accumulated in memory.

## Tests

From PowerShell, run these commands at the project root to create the virtual environment, install dependencies, and activate it:

```bash
cd C:\path\to\bulk-certificate-generator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, allow it for the current window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Run the automated API test suite:

```powershell
python -m pytest -q
```

Run the fictional end-to-end batch scenarios and the 1,000-recipient capacity probe:

```powershell
python -m tests.manual_scenarios
```

The scenario runner prints a job ID, result counts, elapsed time, and ZIP path for each run. It creates four ZIPs under `storage\certificates\`: `scenario_1_recipient.zip`, `scenario_5_one_failure.zip` (four successful PDFs), `scenario_100_recipients.zip`, and `capacity_probe_1000.zip`. The single failure is deliberately injected during rendering so the run verifies that the other four recipients still succeed. The backend currently has no configured maximum batch size; 1,000 is the largest size exercised by this scenario runner, not a guaranteed upper limit. Scenario job records are kept in an isolated in-memory test database; the generated PDFs and ZIPs remain in the storage directory.

The automated test suite uses an isolated in-memory SQLite database and temporary certificate storage. It covers validation, job creation and status, failure isolation, and individual and bulk downloads.

### Scenario test report

The following inputs were used with the fictional end-to-end scenario runner. Each request used issue date `2026-10-09` and an event name prefixed with `Imaginary`. The recorded runtimes are observations from one local run, not performance guarantees.

| Scenario | Input | Observed output | Bundle |
| --- | --- | --- | --- |
| Single certificate | 1 recipient: Alex Example (`alex@example.com`) | `COMPLETED`; 1 successful, 0 failed; 1 PDF; 0.12 seconds | `storage\certificates\scenario_1_recipient.zip` |
| Failure isolation | 5 recipients: Blair, Casey, Devon, Elliot, and Finley Example; all use valid `@example.com` addresses. Rendering was deliberately made to fail for Casey Faulty Input. | `PARTIALLY_COMPLETED`; 4 successful, 1 failed; Casey has an error message; 4 PDFs; 0.06 seconds | `storage\certificates\scenario_5_one_failure.zip` |
| 100-recipient batch | Fictional Recipient 001 through Fictional Recipient 100, with matching addresses `person001@example.com` through `person100@example.com` | `COMPLETED`; 100 successful, 0 failed; 100 PDFs; 0.71 seconds | `storage\certificates\scenario_100_recipients.zip` |
| Capacity probe | Capacity Probe 0001 through Capacity Probe 1000, with matching addresses `probe0001@example.com` through `probe1000@example.com` | `COMPLETED`; 1,000 successful, 0 failed; 1,000 PDFs; 6.89 seconds | `storage\certificates\capacity_probe_1000.zip` |

All names and addresses in these scenarios are fictional. The faulty recipient's request data is valid; its renderer failure is injected by the scenario runner to test that the rest of the batch still completes. Job records live only in the runner's in-memory SQLite database and are removed at exit. The generated PDFs and ZIP bundles remain in `storage\certificates\`. The API does not set a maximum batch size; 1,000 is the largest batch verified by this report, not a guaranteed upper limit.

The automated API suite now contains ten tests and covers job creation and polling, invalid recipients and empty batches, failure isolation, generated PDF bytes, individual PDF and ZIP downloads, CSV ingestion, rate limiting, and bounded concurrency.

## Reviewer Evaluation Guide
   testing instructions https://drive.google.com/file/d/1eAqRfHZkZJnWmKH7N__seL46HfwWmRtH/view?usp=sharing
   project guide and documentation  https://drive.google.com/file/d/1RUlmvCWz6RIGMCxF1QOTdhUEQ4MmyJUe/view?usp=sharing

### Install and run the test suite

From PowerShell at the project root, activate the virtual environment and install the declared dependencies. The single-command evaluator run with coverage is:

```powershell
pytest --cov=app
```

The suite covers JSON and CSV job creation, CSV extra-column metadata, request validation, generated PDF bytes, status/progress, per-recipient failure isolation, individual and ZIP retrieval, rate limiting, and the worker concurrency bound. The in-memory SQLite fixture avoids using the development database.

### Start the service

```powershell
python -m uvicorn app.main:app --reload
```

The API defaults to `http://127.0.0.1:8000`; Swagger is at `/docs`. Set the per-batch PDF worker count before startup if needed; it defaults to four:

```powershell
$env:MAX_WORKERS = "4"
python -m uvicorn app.main:app --reload
```

### Upload recipients as CSV

Send multipart form fields `event_name`, optional `issue_date`, and a `file` upload. Required CSV columns may be named `name` or `recipient_name`, and `email` or `recipient_email`. Other columns are copied to recipient `metadata`. Each parsed recipient is validated with the same schema as JSON submissions; an invalid row rejects the upload with HTTP 422 and no job is created.

Example `recipients.csv`:

```csv
name,email,department,grade
Alex Example,alex@example.com,Engineering,A
Jordan Sample,jordan@example.com,Design,B
```

PowerShell command (use `curl.exe` to invoke Windows curl rather than PowerShell's historical `curl` alias):

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/jobs/upload `
  -F "event_name=Python Workshop" `
  -F "issue_date=2026-10-10" `
  -F "file=@recipients.csv;type=text/csv"
```

The endpoint responds with HTTP 202 and the standard job response containing `job_id` and `status_check_url`. Poll `GET /api/v1/jobs/{job_id}` and use the successful recipients' `download_url` values, or call `GET /api/v1/jobs/{job_id}/download-all` for a ZIP.

### Rate limiting

Both `POST /api/v1/jobs` and `POST /api/v1/jobs/upload` are individually limited to 10 requests per minute per client IP. An excess request receives HTTP 429 Too Many Requests. The limiter uses the remote client address; deployments behind a reverse proxy should configure trusted proxy handling at the deployment boundary before relying on forwarded client IP headers. SlowAPI's default in-memory storage is process-local; multi-process or multi-instance deployments should configure a shared limits storage backend.

### Run the 100-recipient benchmark

Start the server in one PowerShell window. From the project root in another window, with dependencies installed, run:

```powershell
python scripts/benchmark.py
```

The script submits 100 fictional recipients, polls the job until it reaches a terminal status, and prints the job ID, successful and failed counts, total elapsed time, and successful certificates per second. For another server URL or polling budget, use `--base-url`, `--poll-interval`, and `--timeout`, for example:

```powershell
python scripts/benchmark.py --base-url http://127.0.0.1:8000 --poll-interval 0.25 --timeout 300
```

The benchmark sends one request and is within the configured rate limit. Runtime and throughput depend on the host and are measurements, not service-level guarantees.
