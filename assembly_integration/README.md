# Assembly progress integration

This layer does not replace or edit the validated robot pick recipes. It stores
confirmed assembly events in SQLite and publishes the same snapshot to Unity on
`/assembly/progress` (`std_msgs/msg/String`). Real sequential execution is blocked
until all physical board slots and placement heights have been taught.

```bash
source scripts/ksmc_env.sh
python3 assembly_integration/assembly_progress.py start --cycle-id demo-001
python3 assembly_integration/assembly_progress.py complete-step --cycle-id demo-001 --order 1 --source-instance 1
python3 assembly_integration/assembly_progress.py status --cycle-id demo-001
python3 assembly_integration/validate_real_readiness.py
```

Copy `unity_integration/Assets/Scripts/AssemblyProgressSynchronizer.cs` into the
Unity project and attach it to a persistent scene object. A completion must only
be recorded after physical placement and release have both been verified.
