"""Bounded cycle-wide RPCs. Only explicitly allowlisted observations may be retried."""
import json
import sys
import time
import rclpy


class StartupServiceError(RuntimeError):
    pass


def wait_for_startup_services(clients, timeout_sec=15.0, clock=time.monotonic):
    deadline = clock() + timeout_sec
    for client in clients:
        if not client.wait_for_service(timeout_sec=max(0.0, deadline-clock())):
            raise StartupServiceError(
                f'startup service discovery timeout: {client.srv_name}; '
                f'not discovered within {timeout_sec:g}s startup budget; no request sent')


def _log(client, phase, started, attempt):
    print(json.dumps(dict(schema='fr5.startup_rpc/v1',service=client.srv_name,
        phase=phase,attempt=attempt,elapsed_sec=round(time.monotonic()-started,4),
        timestamp_unix=time.time())),file=sys.stderr,flush=True)


def call_startup_service(node, client, request, before_send=None, *, deadline=None, attempt=1):
    started=time.monotonic()
    def budget():
        remaining=3.0 if deadline is None else min(3.0,deadline-time.monotonic())
        if remaining<=0:
            raise StartupServiceError(f'startup service budget exhausted: {client.srv_name}')
        return remaining
    if not client.wait_for_service(timeout_sec=budget()):
        _log(client,'discovery_timeout',started,attempt)
        raise StartupServiceError(f'startup service unavailable: {client.srv_name}; no request sent')
    response_budget=budget()
    if before_send is not None:
        before_send()  # Durable uncertainty marker before the one actuator send.
    _log(client,'request_sending',started,attempt)
    try:
        future=client.call_async(request)
    except Exception as exc:
        _log(client,'dispatch_error',started,attempt)
        raise StartupServiceError(f'startup service dispatch failed: {client.srv_name}; '
                                  'outcome unknown; not retried by single-call transport') from exc
    rclpy.spin_until_future_complete(node,future,timeout_sec=response_budget)
    if not future.done():
        if hasattr(client,'remove_pending_request'):
            client.remove_pending_request(future)
        future.cancel()
        _log(client,'response_timeout',started,attempt)
        raise StartupServiceError(f'startup service response timeout: {client.srv_name}; '
                                  'request sent; outcome unknown; not retried by single-call transport')
    try:
        response=future.result()
    except Exception as exc:
        _log(client,'response_error',started,attempt)
        raise StartupServiceError(f'startup service response failed: {client.srv_name}; '
                                  'request sent; outcome unknown') from exc
    if response is None:
        raise StartupServiceError(f'startup service empty response: {client.srv_name}; request sent')
    _log(client,'response_received',started,attempt)
    return response


def _is_readonly(client, request):
    from std_srvs.srv import Trigger
    from rcl_interfaces.srv import GetParameters
    from fairino_msgs.srv import RemoteCmdInterface
    return ((client.srv_name in ('/real/robot/status','/real/assembly/status') and isinstance(request,Trigger.Request))
        or (client.srv_name=='/fr_command_server/get_parameters' and isinstance(request,GetParameters.Request))
        or (client.srv_name=='/fairino_remote_command_service'
            and isinstance(request,RemoteCmdInterface.Request)
            and request.cmd_str=='GetGripperActivateStatus()'))


def call_readonly_service(node, client, request, *, timeout_sec=15.0, deadline=None):
    if not _is_readonly(client,request):
        raise ValueError('retry policy only permits allowlisted read-only requests')
    end=time.monotonic()+timeout_sec
    if deadline is not None:
        end=min(end,deadline)
    for attempt in range(1,4):
        try:
            return call_startup_service(node,client,request,deadline=end,attempt=attempt)
        except StartupServiceError as exc:
            if attempt==3 or time.monotonic()>=end:
                raise StartupServiceError(
                    f'startup read-only query failed: {client.srv_name}; '
                    f'attempts={attempt}; no actuator request sent by this query; {exc}') from exc
            _log(client,'retry_readonly',time.monotonic(),attempt)
