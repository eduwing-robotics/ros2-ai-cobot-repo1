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
| `POST` | `/api/v1/assemblies` | Forward one assembly start command to the ROS bridge |
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

The execution routes are a common Mock/Real API. They always call the same
ROS2 `fairino_msgs.srv.RemoteCmdInterface` service:
`/unity/assembly/start`. MainServer does not import or call `mock_sim.py`,
`production_store.py`, or SQL write functions.

`POST /api/v1/assemblies` requires exactly this existing bridge contract:

```json
{
  "command": "start",
  "request_id": "UUID",
  "recipe_version": "mock-r1",
  "observations": [
    {
      "order": 1,
      "part_id": "HBM",
      "source": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] },
      "target": { "xyz_mm": [0, 0, 0], "xyzw": [0, 0, 0, 1] }
    }
  ]
}
```

`request_id` must be a UUID, `recipe_version` must be nonblank, and
`observations` must be non-empty. Observation poses and every other
observation field are passed unchanged to the bridge; the bridge/runner
remains the validation and execution owner. MainServer only validates the
top-level request shape.

A bridge acceptance returns `202`; it means only **accepted**, not completed.
Use `GET /api/v1/assemblies/current` and the existing job/unit query routes
to observe progress and terminal results. The current route sends exactly
`{"command":"status"}` to the bridge and returns its snapshot.

| HTTP | Error code | Meaning |
| --- | --- | --- |
| `400` | `invalid_request` | Invalid API request, recipe, or bridge request |
| `409` | `assembly_busy` | An assembly or robot command is already active |
| `503` | `assembly_unavailable` | ROS2/bridge/DB service unavailable, timeout, or invalid bridge response |
| `503` | `assembly_faulted` | Runner is faulted and must be recovered before retry |
| `503` | `assembly_execution_unavailable` | Runner is in PLAN_ONLY mode and cannot execute |

The gateway serializes ROS service spins, so concurrent HTTP calls cannot spin
the same ROS2 client context together.

## Runtime

`MAIN_SERVER_MODE` must be exactly `mock` or `real`; it chooses runtime
configuration only, never API paths or payload conversion. `MAIN_SERVER_DB_DSN`
must point at the corresponding `production` schema through a read-only
account.

Execution routes additionally require a shell where ROS2 and the Farino_AIO
overlay have been sourced, plus a running bridge that exposes
`/unity/assembly/start`. For Mock, use the single
[`launch_mock.launch.py` command](../Farino_AIO/README.md#mock-올인원-실행).
It starts MoveIt, the Mock DB bridge, Unity endpoint and MainServer against the
same Mock database; do not start MainServer separately.

For Real, start the real bridge that implements the same service and run
MainServer with `MAIN_SERVER_MODE=real` and its real read-only DB DSN.
