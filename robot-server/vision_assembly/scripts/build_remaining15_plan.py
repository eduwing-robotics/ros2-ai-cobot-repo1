"""Join fresh, scoped tray/board captures and build a read-only 15-part plan."""
import argparse
import json
import time
from pathlib import Path
from full_cycle_plan import build_plan, atomic_write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tray',type=Path,required=True)
    p.add_argument('--board',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--exclude-released-hbm02',action='store_true')
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    tray=json.loads(a.tray.read_text());board=json.loads(a.board.read_text())
    if a.output.exists():raise RuntimeError('refusing to overwrite plan')
    if not 0<=time.time()-tray['timestamp_unix']<=600:raise RuntimeError('tray capture expired')
    if not 0<=time.time()-board['board_capture']['captured_unix']<=120:raise RuntimeError('board capture expired')
    selected=[f'HBM-{i:02d}' for i in range(2,9)]+[f'PM-{i:02d}' for i in range(2,5)]+[f'VRM-{i:02d}' for i in range(2,6)]+['IND-02']
    if a.exclude_released_hbm02:selected.remove('HBM-02')
    if tray.get('authorized_selected_slots')!=selected or len(tray['parts'])!=len(selected):raise RuntimeError('wrong tray scope')
    board['tray_capture']={'parts':tray['parts'],'captured_unix':tray['timestamp_unix'],'handeye_sha256':tray['handeye_sha256']}
    board['tray_captured']=True;board['authorized_selected_slots']=selected
    recipes=json.loads((root/'config/part_gripper_recipes.json').read_text())
    slots=json.loads((root/'config/assembly_slots_r1.json').read_text())
    plan=build_plan(board,recipes,slots,selected_slots=selected)
    plan['source_captures']={'tray_file':str(a.tray),'board_file':str(a.board),'tray_captured_unix':tray['timestamp_unix'],'board_captured_unix':board['board_capture']['captured_unix']}
    atomic_write_json(a.output,plan)
    print('PLANNED ONLY:',len(plan['plan']),[i['slot_code'] for i in plan['plan']])

if __name__=='__main__':main()
