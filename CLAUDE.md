# amwater-api — Project Context

## Project Summary

Standalone Python OIDC API library (`amwater-api`) for scraping water usage and bill data from Illinois American Water (amwater.com / mywater.amwater.com). 
It runs entirely on **pure API requests** (HTTP GET and POST) using `aiohttp` to perform Okta OIDC token exchanges and fetch account details, monthly usage charts, and statement PDFs. It does **NOT** require any browser automation, Playwright, or Chromium.

## Environment

- **Host**: Ubuntu VM at 10.10.1.19
- **Project root**: `~/projects/amwater-scraper/`
- **Runtime**: Python 3.9+ with Poetry
- **Secrets**: `~/projects/secrets.env` (or local `.env`) — `AMWATER_USERNAME`, `AMWATER_PASSWORD`

## Project Structure

```
amwater-scraper/
├── docs/                      ← Captured Swagger docs and raw network request logs
├── src/
│   └── amwater_api/
│       ├── __init__.py        ← Package module exports
│       ├── client.py          ← AmericanWaterAPI client class using aiohttp
│       └── exceptions.py      ← Custom exceptions for Home Assistant (Auth / Connect)
├── README.md                  ← Standalone package readme
├── pyproject.toml             ← Poetry package configuration and dependency definitions
├── poetry.lock                ← Locked dependency versions
├── main.py                    ← Standalone CLI verification and smoke test script
└── CLAUDE.md                  ← This file
```

## Setup & Running

Install dependencies and enter the Poetry environment:
```bash
poetry install
```

To run the verification CLI:
```bash
poetry run python3 main.py
```

## Architectural Discoveries (American Water Portal)

1. **Authentication Flow (Pure API):**
   - Hitting `POST https://auth.amwater.com/api/v1/authn` with credentials returns an Okta `sessionToken`.
   - Hitting `GET https://auth.amwater.com/oauth2/aus29oxmv4bzpt55X5d7/v1/authorize` with `sessionToken` returns a `302 Redirect` containing the OIDC authorization `code`.
   - Hitting `GET https://mywaterv2.amwater.com/openidlogin?code=...` returns a `302 Redirect` and sets the authenticated Java session cookie (`JSESSIONID`) and Bearer JWT token (`mw-authenticationToken`).
   
2. **Account Summary Pipeline (MSO):**
   - Hitting `POST https://mywaterv2.amwater.com/api/mso/data` with pipeline `com::apporchid::cloudseer::mso::myaccountsummarypipeline` returns details like `businessPartnerNumber`, `contractAccountNumber`, and `premiseNumber`.

3. **Usage Charts (VUX Microapp):**
   - Hitting `POST https://mywaterv2.amwater.com/api/vux/microapp` with microapp `usageOverviewMonthlyChartFourYears` returns Highcharts series coordinate values (measured in hundreds of gallons).

4. **Billing Statements & PDFs:**
   - Hitting `POST https://mywaterv2.amwater.com/api/vux/microapp` with microapp `billingAndPaymentsHistoryTable` returns transaction records, dates, and PDF document IDs.
   - Calling `/api/cloudseer/pdf/ViewBill?docId={docId}` returns a MIME multipart boundary response wrapping the raw PDF. The client slices out the PDF binary by locating the `%PDF` and `%%EOF` markers.

## Active Handoff

- **[2026-07-09 (Antigravity)]**: Re-architected the project from TypeScript/Playwright into a pure async Python library (`amwater-api`) using `aiohttp` and `poetry`. Verified end-to-end login, account summary parsing, 36-month chart retrieval, billing history collection, and clean PDF statement binary downloading. Tested successfully using `main.py` CLI. Pushed initial codebase to `tempeduck/amwater-api` and component to `tempeduck/amwater-hacs`.
- **[2026-07-09 (Antigravity)]**: Added support for the customer profile pipeline (`customer_profile_pipeline`) and active alerts API (`getActiveAlerts`). Added a user-adjustable polling interval and PDF default save location via Home Assistant Options Flow, outages/connectivity binary sensors, and the custom `amwater.download_latest_bill` service. Saved all code updates locally.
