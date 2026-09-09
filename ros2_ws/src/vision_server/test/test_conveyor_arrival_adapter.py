"""Teammate callback regression without ROS context, DB or motion."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('arrival_adapter',ROOT/'team_handoff/conveyor_remote_api/db/conveyor_event_subscriber.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)


def test_late_subscription_repeat_and_missed_moving_state(monkeypatch):
    events=[];monkeypatch.setattr(adapter,'persist_event',events.append)
    harness=SimpleNamespace(previous_state=None,previous_arrival_id=None,last_state_at=0,
                            timeout_reported=False,get_logger=lambda:Mock())
    def receive(mid):
        state=dict(schema_version=1,state='ASSEMBLY_STOP',moving=False,timestamp_ns=123,
                   arrival=dict(station='assembly',motion_id=mid,timestamp_ns=120))
        adapter.ConveyorEventSubscriber.on_state(harness,SimpleNamespace(data=json.dumps(state)))
    receive('server:1');receive('server:1');receive('server:2')
    arrivals=[e for e in events if e['event_type']=='STATION_REACHED']
    assert [e['motion_id'] for e in arrivals]==['server:1','server:2']
    assert all(e['station']=='assembly' for e in arrivals)
