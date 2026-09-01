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
| `GET` | `/api/v1/jobs/{job_id}` | Get assembly job progress |
| `GET` | `/api/v1/jobs/{job_id}/units` | Get assembled units, inspections, and defects |
| `GET` | `/api/v1/products/{product_id}/quality/slot-rates` | Get accumulated slot inspection/defect rates |
| `POST` | `/api/v1/assemblies` | Persist one assembly command in the PostgreSQL control queue |
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
resources are `404`, and unavailable DB is `503`.

## Assembly execution

The two assembly routes have different infrastructure boundaries.

- `POST /api/v1/assemblies` validates the top-level command and inserts it into
  `control.assembly_requests`. It does not call ROS2.
- `GET /api/v1/assemblies/current` sends the `status` command to the
  AssemblySequencer ROS2 service and returns its current or terminal snapshot.

MainServer never calls `mock_sim.py` or production write functions.

`POST /api/v1/assemblies` requires exactly this command contract:

```json
{
  "command": "start",
  "request_id": "UUID",
  "recipe_version": "assembly-r1",
  "observations": [
    {
      "order": 1,
      "part_id": "HBM",
      "gripper_grasp_opening_percent": 0,
      "gripper_release_opening_percent": 100,
      "source": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] },
      "target": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] }
    }
  ],
  "assembled_pcb": {
    "gripper_grasp_opening_percent": 0,
    "gripper_release_opening_percent": 100,
    "source": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] },
    "target": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] }
  }
}
```

`request_id` must be a UUID, `recipe_version` must be nonblank,
`observations` must be non-empty, and `assembled_pcb` must be an object.
MainServer stores the full command unchanged after top-level validation;
AssemblySequencer and the backend own recipe, pose and robot safety validation.

The first valid request returns `202`:

```json
{
  "data": {
    "accepted": true,
    "request_id": "UUID",
    "status": "QUEUED"
  }
}
```

`accepted=true` means persisted in PostgreSQL, not accepted or completed by the
robot. Repeating the same request ID, mode and payload is idempotent and
returns its current queue status. Reusing the ID for different content returns
`409 duplicate_request`.

AssemblySequencer claims the oldest `QUEUED` row for its runtime mode and
atomically creates the production Job and Unit. Use the current snapshot and
Job/Unit routes to observe execution and DB synchronization.

| HTTP | Error code | Meaning |
| --- | --- | --- |
| `400` | `invalid_request` | Invalid HTTP query or top-level assembly command |
| `409` | `duplicate_request` | The request ID already belongs to different content |
| `503` | `database_unavailable` | PostgreSQL is unavailable for query or enqueue |
| `503` | `assembly_unavailable` | Status ROS2 service is unavailable or invalid |

The status gateway serializes ROS service spins, so concurrent status calls
cannot spin the same ROS2 client context together.

## Runtime

`MAIN_SERVER_MODE` must be exactly `mock` or `real`; it chooses runtime
configuration only, never API paths or payload conversion. `MAIN_SERVER_DB_DSN`
must allow reads from `production` and enqueue/read access to
`control.assembly_requests`. MainServer does not write production tables.

Product, Job and POST assembly routes need PostgreSQL only. The current-status
route additionally requires a shell where ROS2 and the included
`Farino_AIO_Mock` overlay have been sourced, plus a running AssemblySequencer
service. For Mock, follow the [AIO launch instructions](../Farino_AIO_Mock/README.md#mock-올인원-실행).

`MAIN_SERVER_MODE=real` stores requests in the Real queue, but Real automatic
assembly is not implemented yet. Do not submit Real production requests until
the Real AssemblySequencer consumer is connected.
