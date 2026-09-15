#!/usr/bin/env python3
"""Idempotent SQLite progress store and ROS 2 Unity-state publisher."""

import argparse
import json
import sqlite3
import time
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_RECIPE = ROOT / "config/assembly_recipe.yaml"
DEFAULT_DB = ROOT / "data/assembly_progress.sqlite3"
TOPIC = "/assembly/progress"
SCHEMA = "fr5.assembly.progress/v1"


def load_recipe(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    orders = [int(step["order"]) for step in data["steps"]]
    if orders != list(range(1, len(orders) + 1)):
        raise ValueError("recipe orders must be contiguous and start at 1")
    if len({step["slot_code"] for step in data["steps"]}) != len(orders):
        raise ValueError("slot_code values must be unique")
    return data


class ProgressStore:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS cycles (
            cycle_id TEXT PRIMARY KEY, recipe_version TEXT NOT NULL,
            status TEXT NOT NULL, created_unix REAL NOT NULL, updated_unix REAL NOT NULL
          );
          CREATE TABLE IF NOT EXISTS assembly_events (
            event_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL,
            step_order INTEGER NOT NULL, part_id TEXT NOT NULL,
            source_instance INTEGER, slot_code TEXT NOT NULL,
            status TEXT NOT NULL, timestamp_unix REAL NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(cycle_id, step_order, status),
            FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
          );
        """)
        self.db.commit()

    def start(self, recipe_version, cycle_id=None):
        cycle_id = cycle_id or f"cycle-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        now = time.time()
        self.db.execute("INSERT INTO cycles VALUES(?,?,?,?,?)", (cycle_id, recipe_version, "RUNNING", now, now))
        self.db.commit()
        return cycle_id

    def record(self, cycle_id, step, status, source_instance=None, details=None):
        if status not in {"STARTED", "ASSEMBLED", "FAILED"}:
            raise ValueError("unsupported event status")
        now = time.time()
        event_id = str(uuid.uuid4())
        with self.db:
            cycle = self.db.execute(
                "SELECT status FROM cycles WHERE cycle_id=?", (cycle_id,)
            ).fetchone()
            if cycle is None:
                raise ValueError(f"unknown cycle_id: {cycle_id}")
            if status in {"STARTED", "ASSEMBLED"}:
                completed_before = self.db.execute(
                    "SELECT COUNT(DISTINCT step_order) FROM assembly_events "
                    "WHERE cycle_id=? AND status='ASSEMBLED' AND step_order<?",
                    (cycle_id, int(step["order"])),
                ).fetchone()[0]
                if completed_before != int(step["order"]) - 1:
                    raise ValueError(f"cannot advance out of order to step {step['order']}")
            existing = self.db.execute(
                "SELECT * FROM assembly_events WHERE cycle_id=? AND step_order=? AND status=?",
                (cycle_id, int(step["order"]), status),
            ).fetchone()
            if existing:
                return dict(existing), False
            self.db.execute(
                "INSERT INTO assembly_events VALUES(?,?,?,?,?,?,?,?,?)",
                (event_id, cycle_id, int(step["order"]), step["part_id"], source_instance,
                 step["slot_code"], status, now, json.dumps(details or {}, ensure_ascii=False)),
            )
            self.db.execute("UPDATE cycles SET updated_unix=? WHERE cycle_id=?", (now, cycle_id))
        return dict(self.db.execute("SELECT * FROM assembly_events WHERE event_id=?", (event_id,)).fetchone()), True

    def state(self, cycle_id, recipe):
        cycle = self.db.execute("SELECT * FROM cycles WHERE cycle_id=?", (cycle_id,)).fetchone()
        if cycle is None:
            raise ValueError(f"unknown cycle_id: {cycle_id}")
        rows = self.db.execute(
            "SELECT * FROM assembly_events WHERE cycle_id=? ORDER BY step_order,timestamp_unix", (cycle_id,)
        ).fetchall()
        assembled = {int(row["step_order"]): dict(row) for row in rows if row["status"] == "ASSEMBLED"}
        next_step = next((step for step in recipe["steps"] if int(step["order"]) not in assembled), None)
        return {
            "schema": SCHEMA, "valid": True, "sequence": time.time_ns(),
            "cycle_id": cycle_id, "recipe_version": recipe["recipe_version"],
            "cycle_status": "COMPLETE" if next_step is None else cycle["status"],
            "completed_count": len(assembled), "total_count": len(recipe["steps"]),
            "next_step": next_step, "assembled": [assembled[key] for key in sorted(assembled)],
        }


def publish_once(payload):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
    rclpy.init()
    node = Node("assembly_progress_once")
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
    pub = node.create_publisher(String, TOPIC, qos)
    msg = String(); msg.data = json.dumps(payload, ensure_ascii=False)
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        pub.publish(msg); rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node(); rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start"); start.add_argument("--cycle-id")
    for name in ("begin-step", "complete-step", "fail-step"):
        cmd = sub.add_parser(name); cmd.add_argument("--cycle-id", required=True)
        cmd.add_argument("--order", type=int, required=True); cmd.add_argument("--source-instance", type=int)
        cmd.add_argument("--details", default="{}")
    status = sub.add_parser("status"); status.add_argument("--cycle-id", required=True)
    args = parser.parse_args(); recipe = load_recipe(args.recipe); store = ProgressStore(args.db)
    if args.command == "start":
        cycle_id = store.start(recipe["recipe_version"], args.cycle_id)
        payload = store.state(cycle_id, recipe)
    elif args.command == "status":
        payload = store.state(args.cycle_id, recipe)
    else:
        step = next((item for item in recipe["steps"] if int(item["order"]) == args.order), None)
        if step is None: raise SystemExit(f"unknown recipe order: {args.order}")
        status_name = {"begin-step": "STARTED", "complete-step": "ASSEMBLED", "fail-step": "FAILED"}[args.command]
        _, inserted = store.record(args.cycle_id, step, status_name, args.source_instance, json.loads(args.details))
        payload = store.state(args.cycle_id, recipe); payload["event_inserted"] = inserted
    print(json.dumps(payload, ensure_ascii=False, indent=2)); publish_once(payload)


if __name__ == "__main__":
    main()
