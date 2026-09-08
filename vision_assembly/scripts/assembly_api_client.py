#!/usr/bin/env python3
"""Operator CLI for the shared ROS assembly API. No direct robot commands."""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

TERMINAL = {'motion_complete_awaiting_physical_verification', 'check_completed', 'check_failed', 'recovery_required'}


def make_request(status, *, execute=False, profile='full', job_id=None, operation_id=None):
    if not execute and profile != 'full':
        raise ValueError('--part requires --execute')
    if profile not in status.get('profiles', []):
        raise RuntimeError('API does not support this profile; update API, no direct fallback')
    return dict(schema='fr5.assembly_cycle/v1', action='assembly.start' if execute else 'assembly.check',
        job_id=job_id or str(uuid4()), operation_id=operation_id or str(uuid4()),
        recipe_revision=status['recipe_revision'], confirm_scene_ready=bool(execute), profile=profile)


def main():
    parser = argparse.ArgumentParser(description='공통 조립 API: 실행/부품별 시험/점검/상태/중단')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true', help='준비된 작업영역·빈 대상슬롯·빈 그리퍼·트레이 부품을 확인한 실제 실행')
    mode.add_argument('--check', action='store_true', help='API를 통한 무동작 장치 점검')
    mode.add_argument('--dry-run', '--status', action='store_true', help='API 상태/지원 프로필 조회만 (기본)')
    mode.add_argument('--stop', action='store_true', help='API 현재 작업에 중단 요청')
    parser.add_argument('--part', choices=['GPU','HBM','PM','VRM','IND','SMD'], help='해당 종류 전부만 배치하는 시험')
    args = parser.parse_args()
    if args.part and not args.execute:
        parser.error('--part requires --execute')
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from std_msgs.msg import String
    from std_srvs.srv import Trigger
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('assembly_operator_client_' + uuid4().hex[:8])
    updates = []
    for topic in ('/real/assembly/event', '/real/assembly/state'):
        node.create_subscription(String, topic, lambda msg: updates.append(json.loads(msg.data)), 100)
    pub = node.create_publisher(String, '/real/assembly/command', 10)
    client = node.create_client(Trigger, '/real/assembly/status')
    request = None
    sent = False
    def publish(payload):
        pub.publish(String(data=json.dumps(payload)))
    def stop():
        publish({k:request[k] for k in ('schema','job_id','operation_id')} | {'action':'assembly.stop'})
    try:
        if not client.wait_for_service(timeout_sec=8):
            raise RuntimeError('조립 API 연결 실패. 직접 실행으로 우회하지 않습니다. ./run_fr5_assembly_stack.sh api-start 확인')
        future = client.call_async(Trigger.Request())
        deadline = time.monotonic()+8
        while not future.done() and time.monotonic()<deadline:
            rclpy.spin_once(node, timeout_sec=.1)
        if not future.done() or not future.result().success:
            raise RuntimeError('API 상태 조회 실패; 실행 요청 없음')
        status = json.loads(future.result().message)
        if not (args.execute or args.check or args.stop):
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
        if args.stop:
            if not status.get('operation_id'):
                raise RuntimeError('중단할 API 작업이 없습니다')
            request = {k:status[k] for k in ('schema','job_id','operation_id')}
            request['action']='assembly.stop'
        else:
            request = make_request(status, execute=args.execute, profile=args.part or 'full')
        deadline=time.monotonic()+8
        while pub.get_subscription_count()==0 and time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.1)
        if pub.get_subscription_count()==0:
            raise RuntimeError('API 명령 구독자 없음; 요청 전송하지 않음')
        # Record correlation IDs before publishing. Unknown delivery never triggers fallback/retry.
        root=Path(__file__).resolve().parents[2]
        receipt=root/'runtime/assembly_api_clients'/f"{request['operation_id']}.json"
        receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(request,indent=2)+'\n')
        updates.clear()
        sent=True
        publish(request)
        print(f"API 요청: {request['action']} / {request['operation_id']}\n진행 기록: {receipt}",flush=True)
        last=None;last_reply=time.monotonic();deadline=time.monotonic()+3600
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.1)
            for event in updates[:]:
                updates.remove(event)
                if event.get('operation_id')!=request['operation_id'] or event.get('job_id')!=request['job_id']:
                    continue
                last_reply=time.monotonic()
                key=(event.get('status'),event.get('step'),tuple(event.get('completed_slots', [])))
                if key!=last:
                    print(json.dumps(event,ensure_ascii=False),flush=True);last=key
                if event.get('status')=='request_rejected':
                    return 1
                if event.get('status') in TERMINAL:
                    return 0 if event['status'] in ('check_completed','motion_complete_awaiting_physical_verification') else 1
            if time.monotonic()-last_reply>15:
                raise RuntimeError('API 응답이 끊겼습니다. 실제 작업 중일 수 있으므로 새 실행을 보내지 말고 --status로 확인하세요.')
        raise RuntimeError('API 대기시간 초과; 작업 취소를 뜻하지 않습니다. --status로 확인하세요.')
    except KeyboardInterrupt:
        if sent:
            stop();print('API 중단 요청 전송. 정지 완료를 확인합니다.',flush=True)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                rclpy.spin_once(node,timeout_sec=.1)
                for event in updates[:]:
                    updates.remove(event)
                    if event.get('operation_id')==request['operation_id'] and event.get('status') in TERMINAL:
                        print(json.dumps(event,ensure_ascii=False));return 130
            print('정지 결과 미확인. API/로봇 상태를 확인하세요.',flush=True)
        return 130
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f'API ERROR: {error}',flush=True)
        raise SystemExit(1)
