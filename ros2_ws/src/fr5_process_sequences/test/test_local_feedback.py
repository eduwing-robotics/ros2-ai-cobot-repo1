import socket
import struct
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fr5_process_sequences.local_feedback import HEADER, MAGIC, LocalFeedbackReceiver


def packet(sequence=1, stamp=None, instance=42, payload=b'healthy', capabilities=1):
    return HEADER.pack(MAGIC, instance, sequence, stamp or time.monotonic_ns(), len(payload), capabilities)+payload


@pytest.fixture
def receiver():
    accepted=[]
    r=LocalFeedbackReceiver('fr5_test_'+uuid4().hex,lambda state,stamp:accepted.append((state,stamp)),
                            lambda data:SimpleNamespace(value=data,reconnect_flag=int(data==b'disconnected')))
    yield r,accepted
    r.close()


def test_uses_source_timestamp_and_preserves_payload(receiver):
    r,accepted=receiver;stamp=time.monotonic_ns()-100_000_000
    r.accept(packet(stamp=stamp))
    assert accepted[0][1]==stamp/1e9
    assert accepted[0][0].value==b'healthy'
    assert r.snapshot()['max_delivery_age_ms']>=100


@pytest.mark.parametrize('bad',[
    lambda: b'bad',
    lambda: packet(stamp=time.monotonic_ns()-300_000_000),
    lambda: packet(stamp=time.monotonic_ns()+1_000_000_000),
    lambda: packet()[:-1],
    lambda: packet(payload=b'disconnected'),
])
def test_bad_feedback_never_refreshes_age(receiver,bad):
    r,accepted=receiver;r.accept(bad())
    assert not accepted and r.stats['rejected']==1
    assert r.last_source is None and r.error


def test_replay_reordering_and_driver_restart_rejected(receiver):
    r,accepted=receiver;stamp=time.monotonic_ns()
    r.accept(packet(sequence=2,stamp=stamp))
    r.accept(packet(sequence=2,stamp=stamp))
    r.accept(packet(sequence=1,stamp=stamp+1))
    r.accept(packet(sequence=3,stamp=stamp-1))
    r.accept(packet(sequence=3,stamp=stamp+1,instance=43))
    assert len(accepted)==1 and r.stats['rejected']==4


def test_duplicate_api_cannot_replace_active_receiver(receiver):
    r,_=receiver
    with pytest.raises(OSError):LocalFeedbackReceiver(r.socket.getsockname()[1:].decode(),lambda *_:None,lambda _:None)


def test_socket_receives_without_ros_executor_and_detects_source_gap(receiver):
    r,accepted=receiver
    sender=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
    try:
        first=time.monotonic_ns();sender.sendto(packet(stamp=first),r.socket.getsockname())
        deadline=time.monotonic()+1
        while not accepted and time.monotonic()<deadline:time.sleep(.005)
        assert len(accepted)==1
        # Source silence remains a >250ms gap even though the new packet is fresh.
        time.sleep(.27)
        sender.sendto(packet(sequence=2),r.socket.getsockname())
        deadline=time.monotonic()+1
        while len(accepted)<2 and time.monotonic()<deadline:time.sleep(.005)
        assert len(accepted)==2 and r.stats['max_source_gap_ms']>250
    finally:sender.close()


def test_local_timestamp_keeps_port_freshness_and_sticky_gap():
    from fr5_process_sequences.real_ros_node import FairinoRobotPort
    from fr5_process_sequences.real_backend import BackendFailure
    port=FairinoRobotPort.__new__(FairinoRobotPort)
    port._lock=threading.Lock();port._state_received_at=0.;port._state_max_age=.25
    port._state_gap_sequence=0;port._state_gap_sec=0.
    state=SimpleNamespace()
    port._store_state(state,time.monotonic()-.4)
    with pytest.raises(BackendFailure,match='stale'):port._fresh_state()
    port._store_state(state,time.monotonic())
    assert port._fresh_state() is state
    assert port._state_gap_sequence==2 and port._state_gap_sec>.25


def test_capability_requires_fresh_supported_driver(receiver):
    r,_=receiver
    assert not r.continuous_capable()
    r.accept(packet(capabilities=0))
    assert not r.continuous_capable()
    r.accept(packet(sequence=2))
    assert r.continuous_capable()
    r.clock=lambda:r.last_source+251_000_000
    assert not r.continuous_capable()


def test_rejected_driver_cannot_authorize_continuous_motion(receiver):
    r,_=receiver
    r.accept(packet())
    r.accept(packet(sequence=2,instance=43))
    assert not r.continuous_capable()


def test_continuous_check_uses_local_evidence_without_ros_request(receiver):
    from fr5_process_sequences.real_ros_node import FairinoRobotPort
    from fr5_process_sequences.real_backend import BackendFailure
    r,_=receiver
    port=FairinoRobotPort.__new__(FairinoRobotPort)
    port._local_receiver=r
    port._fresh_state=lambda:object()
    # No parameter client exists: a DDS request would fail this test.
    with pytest.raises(BackendFailure):port.assert_continuous_driver()
    r.accept(packet())
    for _ in range(100):port.assert_continuous_driver()
    r.accept(packet(sequence=2,capabilities=0))
    with pytest.raises(BackendFailure):port.assert_continuous_driver()


def test_old_protocol_cannot_claim_capability(receiver):
    r,accepted=receiver
    r.accept(packet().replace(MAGIC,b'FR5FB001',1))
    assert not accepted and not r.continuous_capable()
