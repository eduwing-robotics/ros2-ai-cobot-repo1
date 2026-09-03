# MainServer API Contract

This document is the **single API registry** for MainServer. Update it in the
same change as `server.py`. `test_server.py` compares this registry, route
order, and duplicate `(Method, Path)` pairs; do not create a route until its
method/path is absent from the table.

```bash
MAIN_SERVER_MODE=mock MAIN_SERVER_DB_DSN='dbname=main_unity_mock_test' python3 MAIN_SERVER/test_server.py
```

## Registry

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Check DB connectivity and server time |
| `GET` | `/api/v1/products` | List products and buildable quantity |
| `GET` | `/api/v1/products/{product_id}` | Get product and slot/part composition |
| `GET` | `/api/v1/products/{product_id}/requirements?quantity={quantity}` | Get required parts, stock, and shortage |
| `GET` | `/api/v1/parts/{part_id}` | Get part information and stock |
| `GET` | `/api/v1/jobs?status={status}&limit={limit}` | List the active queue and recent Jobs |
| `GET` | `/api/v1/jobs/{job_id}` | Get assembly job progress |
| `GET` | `/api/v1/jobs/{job_id}/units` | Get assembled units, inspections, and defects |
| `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | Get accumulated slot inspection/defect rates |
| `POST` | `/api/v1/assemblies` | Create one durable production Job |
| `GET` | `/api/v1/assemblies/current` | Return the ROS bridge's current/last assembly snapshot |

## Common response

Success:

```json
{ "data": {} }
```

Failure:

```json
{ "error": { "code": "invalid_request", "message": "..." } }
```

All query routes return `200`. Query invalid input is `400`, missing
resources are `404`, and unavailable DB or inconsistent part datasheet is
`503`.

`GET /api/v1/jobs` accepts an optional production Job `status` and a `limit`
from 1 to 50 (default 12). Without a status filter, `RUNNING` and `PENDING`
Jobs are returned before recent terminal Jobs.

## Assembly execution

`POST /api/v1/assemblies` creates a `PENDING` row in `production.jobs`; it does
not call ROS2 and never stores robot poses. `GET /api/v1/assemblies/current`
queries the AssemblySequencer status service.

```json
{
  "command": "start",
  "job_id": "UUID",
  "product_code": "HBM-ACCELERATOR-PACKAGE-BOARD",
  "product_version": "hbm-pkg-r1",
  "requested_quantity": 1,
  "recipe_version": "assembly-r1"
}
```

`job_id` is the HTTP idempotency key. Repeating the same Job request returns
its current status; reusing the UUID with different product, quantity or recipe
returns `409 duplicate_request`.

```json
{
  "data": {
    "accepted": true,
    "job_id": "UUID",
    "status": "PENDING"
  }
}
```

`accepted=true` means that PostgreSQL durably contains the Job. It does not
mean that the Sequencer or robot accepted or completed execution. Unity sends
Mock-only runtime coordinates directly to the Sequencer ROS boundary with the
same `job_id`; MainServer does not receive or persist them.

| HTTP | Error code | Meaning |
| --- | --- | --- |
| `400` | `invalid_request` | Invalid query or Job request |
| `409` | `duplicate_request` | The Job UUID belongs to different content |
| `503` | `database_unavailable` | PostgreSQL is unavailable |
| `503` | `datasheet_inconsistent` | DB part data and datasheet disagree |
| `503` | `assembly_unavailable` | Status ROS2 service is unavailable or invalid |

## Runtime

`MAIN_SERVER_MODE` must be exactly `mock` or `real`; it reports deployment
configuration only and is not stored in the DB. `MAIN_SERVER_DB_DSN` must allow
the documented production reads and Job insert. The defect-report worker also
updates only `production.defect_report_deliveries`. MainServer does not
transition Jobs or write Units and defects.

Product, Job and POST assembly routes need PostgreSQL only. The current-status
route additionally requires a shell where ROS2 and the included
`Farino_AIO_Mock` overlay have been sourced, plus a running AssemblySequencer
service. For Mock, follow the [AIO launch instructions](../Farino_AIO_Mock/README.md#mock-올인원-실행).

Real Job submission must remain disabled operationally until the Real
AssemblySequencer consumer is connected.
