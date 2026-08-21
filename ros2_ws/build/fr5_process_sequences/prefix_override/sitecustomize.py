import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/juchan-yoon/FR5_robot_control/ros2_ws/install/fr5_process_sequences'
