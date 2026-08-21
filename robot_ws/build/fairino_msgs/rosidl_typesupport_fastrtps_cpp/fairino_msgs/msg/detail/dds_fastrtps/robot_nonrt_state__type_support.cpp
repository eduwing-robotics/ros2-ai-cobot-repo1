// generated from rosidl_typesupport_fastrtps_cpp/resource/idl__type_support.cpp.em
// with input from fairino_msgs:msg/RobotNonrtState.idl
// generated code does not contain a copyright notice
#include "fairino_msgs/msg/detail/robot_nonrt_state__rosidl_typesupport_fastrtps_cpp.hpp"
#include "fairino_msgs/msg/detail/robot_nonrt_state__functions.h"
#include "fairino_msgs/msg/detail/robot_nonrt_state__struct.hpp"

#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_fastrtps_cpp/identifier.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_fastrtps_cpp/serialization_helpers.hpp"
#include "rosidl_typesupport_fastrtps_cpp/wstring_conversion.hpp"
#include "fastcdr/Cdr.h"


// forward declaration of message dependencies and their conversion functions

namespace fairino_msgs
{

namespace msg
{

namespace typesupport_fastrtps_cpp
{


bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
cdr_serialize(
  const fairino_msgs::msg::RobotNonrtState & ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Member: j1_cur_pos
  cdr << ros_message.j1_cur_pos;

  // Member: j2_cur_pos
  cdr << ros_message.j2_cur_pos;

  // Member: j3_cur_pos
  cdr << ros_message.j3_cur_pos;

  // Member: j4_cur_pos
  cdr << ros_message.j4_cur_pos;

  // Member: j5_cur_pos
  cdr << ros_message.j5_cur_pos;

  // Member: j6_cur_pos
  cdr << ros_message.j6_cur_pos;

  // Member: j1_cur_tor
  cdr << ros_message.j1_cur_tor;

  // Member: j2_cur_tor
  cdr << ros_message.j2_cur_tor;

  // Member: j3_cur_tor
  cdr << ros_message.j3_cur_tor;

  // Member: j4_cur_tor
  cdr << ros_message.j4_cur_tor;

  // Member: j5_cur_tor
  cdr << ros_message.j5_cur_tor;

  // Member: j6_cur_tor
  cdr << ros_message.j6_cur_tor;

  // Member: cart_x_cur_pos
  cdr << ros_message.cart_x_cur_pos;

  // Member: cart_y_cur_pos
  cdr << ros_message.cart_y_cur_pos;

  // Member: cart_z_cur_pos
  cdr << ros_message.cart_z_cur_pos;

  // Member: cart_a_cur_pos
  cdr << ros_message.cart_a_cur_pos;

  // Member: cart_b_cur_pos
  cdr << ros_message.cart_b_cur_pos;

  // Member: cart_c_cur_pos
  cdr << ros_message.cart_c_cur_pos;

  // Member: flange_x_cur_pos
  cdr << ros_message.flange_x_cur_pos;

  // Member: flange_y_cur_pos
  cdr << ros_message.flange_y_cur_pos;

  // Member: flange_z_cur_pos
  cdr << ros_message.flange_z_cur_pos;

  // Member: flange_a_cur_pos
  cdr << ros_message.flange_a_cur_pos;

  // Member: flange_b_cur_pos
  cdr << ros_message.flange_b_cur_pos;

  // Member: flange_c_cur_pos
  cdr << ros_message.flange_c_cur_pos;

  // Member: exaxispos1
  cdr << ros_message.exaxispos1;

  // Member: exaxistatus1
  {
    cdr << ros_message.exaxistatus1;
  }

  // Member: exaxispos2
  cdr << ros_message.exaxispos2;

  // Member: exaxistatus2
  {
    cdr << ros_message.exaxistatus2;
  }

  // Member: exaxispos3
  cdr << ros_message.exaxispos3;

  // Member: exaxistatus3
  {
    cdr << ros_message.exaxistatus3;
  }

  // Member: exaxispos4
  cdr << ros_message.exaxispos4;

  // Member: exaxistatus4
  {
    cdr << ros_message.exaxistatus4;
  }

  // Member: ft_fx_data
  cdr << ros_message.ft_fx_data;

  // Member: ft_fy_data
  cdr << ros_message.ft_fy_data;

  // Member: ft_fz_data
  cdr << ros_message.ft_fz_data;

  // Member: ft_tx_data
  cdr << ros_message.ft_tx_data;

  // Member: ft_ty_data
  cdr << ros_message.ft_ty_data;

  // Member: ft_tz_data
  cdr << ros_message.ft_tz_data;

  // Member: ft_actstatus
  cdr << ros_message.ft_actstatus;

  // Member: robot_mode
  cdr << ros_message.robot_mode;

  // Member: tool_num
  cdr << ros_message.tool_num;

  // Member: work_num
  cdr << ros_message.work_num;

  // Member: prg_state
  cdr << ros_message.prg_state;

  // Member: abnormal_stop
  cdr << ros_message.abnormal_stop;

  // Member: prg_name
  cdr << ros_message.prg_name;

  // Member: prg_total_line
  cdr << ros_message.prg_total_line;

  // Member: prg_cur_line
  cdr << ros_message.prg_cur_line;

  // Member: dgt_output_h
  cdr << ros_message.dgt_output_h;

  // Member: dgt_output_l
  cdr << ros_message.dgt_output_l;

  // Member: dgt_input_h
  cdr << ros_message.dgt_input_h;

  // Member: dgt_input_l
  cdr << ros_message.dgt_input_l;

  // Member: tl_dgt_output_l
  cdr << ros_message.tl_dgt_output_l;

  // Member: tl_dgt_input_l
  cdr << ros_message.tl_dgt_input_l;

  // Member: emg
  cdr << ros_message.emg;

  // Member: safetyboxsig
  {
    cdr << ros_message.safetyboxsig;
  }

  // Member: robot_motion_done
  cdr << ros_message.robot_motion_done;

  // Member: grip_motion_done
  cdr << ros_message.grip_motion_done;

  // Member: weldbreakoffstate
  cdr << ros_message.weldbreakoffstate;

  // Member: weldarcstate
  cdr << ros_message.weldarcstate;

  // Member: welding_voltage
  cdr << ros_message.welding_voltage;

  // Member: welding_current
  cdr << ros_message.welding_current;

  // Member: weldtrackspeed
  cdr << ros_message.weldtrackspeed;

  // Member: main_error_code
  cdr << ros_message.main_error_code;

  // Member: sub_error_code
  cdr << ros_message.sub_error_code;

  // Member: check_sum
  cdr << ros_message.check_sum;

  // Member: timestamp
  cdr << ros_message.timestamp;

  // Member: version
  cdr << ros_message.version;

  // Member: tpd_exception
  cdr << ros_message.tpd_exception;

  // Member: alarm_reboot_robot
  cdr << ros_message.alarm_reboot_robot;

  // Member: modbusmasterconnectstate
  cdr << ros_message.modbusmasterconnectstate;

  // Member: mdbsslaveconnect
  cdr << ros_message.mdbsslaveconnect;

  // Member: socket_conn_timeout
  cdr << ros_message.socket_conn_timeout;

  // Member: socket_read_timeout
  cdr << ros_message.socket_read_timeout;

  // Member: btn_box_stop_signa
  cdr << ros_message.btn_box_stop_signa;

  // Member: strangeposflag
  cdr << ros_message.strangeposflag;

  // Member: drag_alarm
  cdr << ros_message.drag_alarm;

  // Member: alarm
  cdr << ros_message.alarm;

  // Member: safetydoor_alarm
  cdr << ros_message.safetydoor_alarm;

  // Member: safetyplanealarm
  cdr << ros_message.safetyplanealarm;

  // Member: motionalarm
  cdr << ros_message.motionalarm;

  // Member: interferealarm
  cdr << ros_message.interferealarm;

  // Member: endluaerrcode
  cdr << ros_message.endluaerrcode;

  // Member: dr_alarm
  cdr << ros_message.dr_alarm;

  // Member: udpcmdstate
  cdr << ros_message.udpcmdstate;

  // Member: aliveslavenumerror
  cdr << ros_message.aliveslavenumerror;

  // Member: gripperfaultnum
  cdr << ros_message.gripperfaultnum;

  // Member: slavecomerror
  {
    cdr << ros_message.slavecomerror;
  }

  // Member: cmdpointerror
  cdr << ros_message.cmdpointerror;

  // Member: ioerror
  cdr << ros_message.ioerror;

  // Member: grippererro
  cdr << ros_message.grippererro;

  // Member: fileerror
  cdr << ros_message.fileerror;

  // Member: paraerror
  cdr << ros_message.paraerror;

  // Member: exaxis_out_slimit_error
  cdr << ros_message.exaxis_out_slimit_error;

  // Member: dr_com_err
  {
    cdr << ros_message.dr_com_err;
  }

  // Member: dr_err
  cdr << ros_message.dr_err;

  // Member: out_sflimit_err
  cdr << ros_message.out_sflimit_err;

  // Member: collision_err
  cdr << ros_message.collision_err;

  // Member: weld_readystate
  cdr << ros_message.weld_readystate;

  // Member: alarm_check_emerg_stop_btn
  cdr << ros_message.alarm_check_emerg_stop_btn;

  // Member: ts_web_state_com_error
  cdr << ros_message.ts_web_state_com_error;

  // Member: ts_tm_cmd_com_error
  cdr << ros_message.ts_tm_cmd_com_error;

  // Member: ts_tm_state_com_error
  cdr << ros_message.ts_tm_state_com_error;

  // Member: ctrlboxerror
  cdr << ros_message.ctrlboxerror;

  // Member: safety_data_state
  cdr << ros_message.safety_data_state;

  // Member: forcesensorerrstate
  cdr << ros_message.forcesensorerrstate;

  // Member: ctrlopenluaerrcode
  {
    cdr << ros_message.ctrlopenluaerrcode;
  }

  // Member: auxservoservoid
  cdr << ros_message.auxservoservoid;

  // Member: auxservoerrcode
  cdr << ros_message.auxservoerrcode;

  // Member: auxservostate
  cdr << ros_message.auxservostate;

  // Member: auxservoactualpos
  cdr << ros_message.auxservoactualpos;

  // Member: auxservoctualspeed
  cdr << ros_message.auxservoctualspeed;

  // Member: auxservoactualtorque
  cdr << ros_message.auxservoactualtorque;

  // Member: extpioinput
  {
    cdr << ros_message.extpioinput;
  }

  // Member: extpiooutput
  {
    cdr << ros_message.extpiooutput;
  }

  // Member: extadcinput
  {
    cdr << ros_message.extadcinput;
  }

  // Member: extadcoutput
  {
    cdr << ros_message.extadcoutput;
  }

  // Member: reconnect_flag
  cdr << ros_message.reconnect_flag;

  // Member: exaxiscoordid
  cdr << ros_message.exaxiscoordid;

  // Member: slave_status_1
  cdr << ros_message.slave_status_1;

  // Member: slave_status_2
  cdr << ros_message.slave_status_2;

  // Member: slave_domain_id
  cdr << ros_message.slave_domain_id;

  // Member: program_run_state
  cdr << ros_message.program_run_state;

  // Member: speed_scale_manual
  cdr << ros_message.speed_scale_manual;

  // Member: speed_scale_auto
  cdr << ros_message.speed_scale_auto;

  return true;
}

bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  fairino_msgs::msg::RobotNonrtState & ros_message)
{
  // Member: j1_cur_pos
  cdr >> ros_message.j1_cur_pos;

  // Member: j2_cur_pos
  cdr >> ros_message.j2_cur_pos;

  // Member: j3_cur_pos
  cdr >> ros_message.j3_cur_pos;

  // Member: j4_cur_pos
  cdr >> ros_message.j4_cur_pos;

  // Member: j5_cur_pos
  cdr >> ros_message.j5_cur_pos;

  // Member: j6_cur_pos
  cdr >> ros_message.j6_cur_pos;

  // Member: j1_cur_tor
  cdr >> ros_message.j1_cur_tor;

  // Member: j2_cur_tor
  cdr >> ros_message.j2_cur_tor;

  // Member: j3_cur_tor
  cdr >> ros_message.j3_cur_tor;

  // Member: j4_cur_tor
  cdr >> ros_message.j4_cur_tor;

  // Member: j5_cur_tor
  cdr >> ros_message.j5_cur_tor;

  // Member: j6_cur_tor
  cdr >> ros_message.j6_cur_tor;

  // Member: cart_x_cur_pos
  cdr >> ros_message.cart_x_cur_pos;

  // Member: cart_y_cur_pos
  cdr >> ros_message.cart_y_cur_pos;

  // Member: cart_z_cur_pos
  cdr >> ros_message.cart_z_cur_pos;

  // Member: cart_a_cur_pos
  cdr >> ros_message.cart_a_cur_pos;

  // Member: cart_b_cur_pos
  cdr >> ros_message.cart_b_cur_pos;

  // Member: cart_c_cur_pos
  cdr >> ros_message.cart_c_cur_pos;

  // Member: flange_x_cur_pos
  cdr >> ros_message.flange_x_cur_pos;

  // Member: flange_y_cur_pos
  cdr >> ros_message.flange_y_cur_pos;

  // Member: flange_z_cur_pos
  cdr >> ros_message.flange_z_cur_pos;

  // Member: flange_a_cur_pos
  cdr >> ros_message.flange_a_cur_pos;

  // Member: flange_b_cur_pos
  cdr >> ros_message.flange_b_cur_pos;

  // Member: flange_c_cur_pos
  cdr >> ros_message.flange_c_cur_pos;

  // Member: exaxispos1
  cdr >> ros_message.exaxispos1;

  // Member: exaxistatus1
  {
    cdr >> ros_message.exaxistatus1;
  }

  // Member: exaxispos2
  cdr >> ros_message.exaxispos2;

  // Member: exaxistatus2
  {
    cdr >> ros_message.exaxistatus2;
  }

  // Member: exaxispos3
  cdr >> ros_message.exaxispos3;

  // Member: exaxistatus3
  {
    cdr >> ros_message.exaxistatus3;
  }

  // Member: exaxispos4
  cdr >> ros_message.exaxispos4;

  // Member: exaxistatus4
  {
    cdr >> ros_message.exaxistatus4;
  }

  // Member: ft_fx_data
  cdr >> ros_message.ft_fx_data;

  // Member: ft_fy_data
  cdr >> ros_message.ft_fy_data;

  // Member: ft_fz_data
  cdr >> ros_message.ft_fz_data;

  // Member: ft_tx_data
  cdr >> ros_message.ft_tx_data;

  // Member: ft_ty_data
  cdr >> ros_message.ft_ty_data;

  // Member: ft_tz_data
  cdr >> ros_message.ft_tz_data;

  // Member: ft_actstatus
  cdr >> ros_message.ft_actstatus;

  // Member: robot_mode
  cdr >> ros_message.robot_mode;

  // Member: tool_num
  cdr >> ros_message.tool_num;

  // Member: work_num
  cdr >> ros_message.work_num;

  // Member: prg_state
  cdr >> ros_message.prg_state;

  // Member: abnormal_stop
  cdr >> ros_message.abnormal_stop;

  // Member: prg_name
  cdr >> ros_message.prg_name;

  // Member: prg_total_line
  cdr >> ros_message.prg_total_line;

  // Member: prg_cur_line
  cdr >> ros_message.prg_cur_line;

  // Member: dgt_output_h
  cdr >> ros_message.dgt_output_h;

  // Member: dgt_output_l
  cdr >> ros_message.dgt_output_l;

  // Member: dgt_input_h
  cdr >> ros_message.dgt_input_h;

  // Member: dgt_input_l
  cdr >> ros_message.dgt_input_l;

  // Member: tl_dgt_output_l
  cdr >> ros_message.tl_dgt_output_l;

  // Member: tl_dgt_input_l
  cdr >> ros_message.tl_dgt_input_l;

  // Member: emg
  cdr >> ros_message.emg;

  // Member: safetyboxsig
  {
    cdr >> ros_message.safetyboxsig;
  }

  // Member: robot_motion_done
  cdr >> ros_message.robot_motion_done;

  // Member: grip_motion_done
  cdr >> ros_message.grip_motion_done;

  // Member: weldbreakoffstate
  cdr >> ros_message.weldbreakoffstate;

  // Member: weldarcstate
  cdr >> ros_message.weldarcstate;

  // Member: welding_voltage
  cdr >> ros_message.welding_voltage;

  // Member: welding_current
  cdr >> ros_message.welding_current;

  // Member: weldtrackspeed
  cdr >> ros_message.weldtrackspeed;

  // Member: main_error_code
  cdr >> ros_message.main_error_code;

  // Member: sub_error_code
  cdr >> ros_message.sub_error_code;

  // Member: check_sum
  cdr >> ros_message.check_sum;

  // Member: timestamp
  cdr >> ros_message.timestamp;

  // Member: version
  cdr >> ros_message.version;

  // Member: tpd_exception
  cdr >> ros_message.tpd_exception;

  // Member: alarm_reboot_robot
  cdr >> ros_message.alarm_reboot_robot;

  // Member: modbusmasterconnectstate
  cdr >> ros_message.modbusmasterconnectstate;

  // Member: mdbsslaveconnect
  cdr >> ros_message.mdbsslaveconnect;

  // Member: socket_conn_timeout
  cdr >> ros_message.socket_conn_timeout;

  // Member: socket_read_timeout
  cdr >> ros_message.socket_read_timeout;

  // Member: btn_box_stop_signa
  cdr >> ros_message.btn_box_stop_signa;

  // Member: strangeposflag
  cdr >> ros_message.strangeposflag;

  // Member: drag_alarm
  cdr >> ros_message.drag_alarm;

  // Member: alarm
  cdr >> ros_message.alarm;

  // Member: safetydoor_alarm
  cdr >> ros_message.safetydoor_alarm;

  // Member: safetyplanealarm
  cdr >> ros_message.safetyplanealarm;

  // Member: motionalarm
  cdr >> ros_message.motionalarm;

  // Member: interferealarm
  cdr >> ros_message.interferealarm;

  // Member: endluaerrcode
  cdr >> ros_message.endluaerrcode;

  // Member: dr_alarm
  cdr >> ros_message.dr_alarm;

  // Member: udpcmdstate
  cdr >> ros_message.udpcmdstate;

  // Member: aliveslavenumerror
  cdr >> ros_message.aliveslavenumerror;

  // Member: gripperfaultnum
  cdr >> ros_message.gripperfaultnum;

  // Member: slavecomerror
  {
    cdr >> ros_message.slavecomerror;
  }

  // Member: cmdpointerror
  cdr >> ros_message.cmdpointerror;

  // Member: ioerror
  cdr >> ros_message.ioerror;

  // Member: grippererro
  cdr >> ros_message.grippererro;

  // Member: fileerror
  cdr >> ros_message.fileerror;

  // Member: paraerror
  cdr >> ros_message.paraerror;

  // Member: exaxis_out_slimit_error
  cdr >> ros_message.exaxis_out_slimit_error;

  // Member: dr_com_err
  {
    cdr >> ros_message.dr_com_err;
  }

  // Member: dr_err
  cdr >> ros_message.dr_err;

  // Member: out_sflimit_err
  cdr >> ros_message.out_sflimit_err;

  // Member: collision_err
  cdr >> ros_message.collision_err;

  // Member: weld_readystate
  cdr >> ros_message.weld_readystate;

  // Member: alarm_check_emerg_stop_btn
  cdr >> ros_message.alarm_check_emerg_stop_btn;

  // Member: ts_web_state_com_error
  cdr >> ros_message.ts_web_state_com_error;

  // Member: ts_tm_cmd_com_error
  cdr >> ros_message.ts_tm_cmd_com_error;

  // Member: ts_tm_state_com_error
  cdr >> ros_message.ts_tm_state_com_error;

  // Member: ctrlboxerror
  cdr >> ros_message.ctrlboxerror;

  // Member: safety_data_state
  cdr >> ros_message.safety_data_state;

  // Member: forcesensorerrstate
  cdr >> ros_message.forcesensorerrstate;

  // Member: ctrlopenluaerrcode
  {
    cdr >> ros_message.ctrlopenluaerrcode;
  }

  // Member: auxservoservoid
  cdr >> ros_message.auxservoservoid;

  // Member: auxservoerrcode
  cdr >> ros_message.auxservoerrcode;

  // Member: auxservostate
  cdr >> ros_message.auxservostate;

  // Member: auxservoactualpos
  cdr >> ros_message.auxservoactualpos;

  // Member: auxservoctualspeed
  cdr >> ros_message.auxservoctualspeed;

  // Member: auxservoactualtorque
  cdr >> ros_message.auxservoactualtorque;

  // Member: extpioinput
  {
    cdr >> ros_message.extpioinput;
  }

  // Member: extpiooutput
  {
    cdr >> ros_message.extpiooutput;
  }

  // Member: extadcinput
  {
    cdr >> ros_message.extadcinput;
  }

  // Member: extadcoutput
  {
    cdr >> ros_message.extadcoutput;
  }

  // Member: reconnect_flag
  cdr >> ros_message.reconnect_flag;

  // Member: exaxiscoordid
  cdr >> ros_message.exaxiscoordid;

  // Member: slave_status_1
  cdr >> ros_message.slave_status_1;

  // Member: slave_status_2
  cdr >> ros_message.slave_status_2;

  // Member: slave_domain_id
  cdr >> ros_message.slave_domain_id;

  // Member: program_run_state
  cdr >> ros_message.program_run_state;

  // Member: speed_scale_manual
  cdr >> ros_message.speed_scale_manual;

  // Member: speed_scale_auto
  cdr >> ros_message.speed_scale_auto;

  return true;
}  // NOLINT(readability/fn_size)


size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
get_serialized_size(
  const fairino_msgs::msg::RobotNonrtState & ros_message,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Member: j1_cur_pos
  {
    size_t item_size = sizeof(ros_message.j1_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j2_cur_pos
  {
    size_t item_size = sizeof(ros_message.j2_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j3_cur_pos
  {
    size_t item_size = sizeof(ros_message.j3_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j4_cur_pos
  {
    size_t item_size = sizeof(ros_message.j4_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j5_cur_pos
  {
    size_t item_size = sizeof(ros_message.j5_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j6_cur_pos
  {
    size_t item_size = sizeof(ros_message.j6_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j1_cur_tor
  {
    size_t item_size = sizeof(ros_message.j1_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j2_cur_tor
  {
    size_t item_size = sizeof(ros_message.j2_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j3_cur_tor
  {
    size_t item_size = sizeof(ros_message.j3_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j4_cur_tor
  {
    size_t item_size = sizeof(ros_message.j4_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j5_cur_tor
  {
    size_t item_size = sizeof(ros_message.j5_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j6_cur_tor
  {
    size_t item_size = sizeof(ros_message.j6_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_x_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_y_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_z_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_a_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_b_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_c_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_x_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_y_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_z_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_a_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_b_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_c_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos1
  {
    size_t item_size = sizeof(ros_message.exaxispos1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus1
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus1[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos2
  {
    size_t item_size = sizeof(ros_message.exaxispos2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus2
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus2[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos3
  {
    size_t item_size = sizeof(ros_message.exaxispos3);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus3
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus3[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos4
  {
    size_t item_size = sizeof(ros_message.exaxispos4);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus4
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus4[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fx_data
  {
    size_t item_size = sizeof(ros_message.ft_fx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fy_data
  {
    size_t item_size = sizeof(ros_message.ft_fy_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fz_data
  {
    size_t item_size = sizeof(ros_message.ft_fz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_tx_data
  {
    size_t item_size = sizeof(ros_message.ft_tx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_ty_data
  {
    size_t item_size = sizeof(ros_message.ft_ty_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_tz_data
  {
    size_t item_size = sizeof(ros_message.ft_tz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_actstatus
  {
    size_t item_size = sizeof(ros_message.ft_actstatus);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: robot_mode
  {
    size_t item_size = sizeof(ros_message.robot_mode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tool_num
  {
    size_t item_size = sizeof(ros_message.tool_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: work_num
  {
    size_t item_size = sizeof(ros_message.work_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_state
  {
    size_t item_size = sizeof(ros_message.prg_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: abnormal_stop
  {
    size_t item_size = sizeof(ros_message.abnormal_stop);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_name
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message.prg_name.size() + 1);

  // Member: prg_total_line
  {
    size_t item_size = sizeof(ros_message.prg_total_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_cur_line
  {
    size_t item_size = sizeof(ros_message.prg_cur_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_output_h
  {
    size_t item_size = sizeof(ros_message.dgt_output_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_output_l
  {
    size_t item_size = sizeof(ros_message.dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_input_h
  {
    size_t item_size = sizeof(ros_message.dgt_input_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_input_l
  {
    size_t item_size = sizeof(ros_message.dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tl_dgt_output_l
  {
    size_t item_size = sizeof(ros_message.tl_dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tl_dgt_input_l
  {
    size_t item_size = sizeof(ros_message.tl_dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: emg
  {
    size_t item_size = sizeof(ros_message.emg);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetyboxsig
  {
    size_t array_size = 6;
    size_t item_size = sizeof(ros_message.safetyboxsig[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: robot_motion_done
  {
    size_t item_size = sizeof(ros_message.robot_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: grip_motion_done
  {
    size_t item_size = sizeof(ros_message.grip_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldbreakoffstate
  {
    size_t item_size = sizeof(ros_message.weldbreakoffstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldarcstate
  {
    size_t item_size = sizeof(ros_message.weldarcstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: welding_voltage
  {
    size_t item_size = sizeof(ros_message.welding_voltage);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: welding_current
  {
    size_t item_size = sizeof(ros_message.welding_current);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldtrackspeed
  {
    size_t item_size = sizeof(ros_message.weldtrackspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: main_error_code
  {
    size_t item_size = sizeof(ros_message.main_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: sub_error_code
  {
    size_t item_size = sizeof(ros_message.sub_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: check_sum
  {
    size_t item_size = sizeof(ros_message.check_sum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: timestamp
  {
    size_t item_size = sizeof(ros_message.timestamp);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message.version.size() + 1);

  // Member: tpd_exception
  {
    size_t item_size = sizeof(ros_message.tpd_exception);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm_reboot_robot
  {
    size_t item_size = sizeof(ros_message.alarm_reboot_robot);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: modbusmasterconnectstate
  {
    size_t item_size = sizeof(ros_message.modbusmasterconnectstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: mdbsslaveconnect
  {
    size_t item_size = sizeof(ros_message.mdbsslaveconnect);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: socket_conn_timeout
  {
    size_t item_size = sizeof(ros_message.socket_conn_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: socket_read_timeout
  {
    size_t item_size = sizeof(ros_message.socket_read_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: btn_box_stop_signa
  {
    size_t item_size = sizeof(ros_message.btn_box_stop_signa);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: strangeposflag
  {
    size_t item_size = sizeof(ros_message.strangeposflag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: drag_alarm
  {
    size_t item_size = sizeof(ros_message.drag_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm
  {
    size_t item_size = sizeof(ros_message.alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetydoor_alarm
  {
    size_t item_size = sizeof(ros_message.safetydoor_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetyplanealarm
  {
    size_t item_size = sizeof(ros_message.safetyplanealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: motionalarm
  {
    size_t item_size = sizeof(ros_message.motionalarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: interferealarm
  {
    size_t item_size = sizeof(ros_message.interferealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: endluaerrcode
  {
    size_t item_size = sizeof(ros_message.endluaerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_alarm
  {
    size_t item_size = sizeof(ros_message.dr_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: udpcmdstate
  {
    size_t item_size = sizeof(ros_message.udpcmdstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: aliveslavenumerror
  {
    size_t item_size = sizeof(ros_message.aliveslavenumerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: gripperfaultnum
  {
    size_t item_size = sizeof(ros_message.gripperfaultnum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slavecomerror
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.slavecomerror[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cmdpointerror
  {
    size_t item_size = sizeof(ros_message.cmdpointerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ioerror
  {
    size_t item_size = sizeof(ros_message.ioerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: grippererro
  {
    size_t item_size = sizeof(ros_message.grippererro);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: fileerror
  {
    size_t item_size = sizeof(ros_message.fileerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: paraerror
  {
    size_t item_size = sizeof(ros_message.paraerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxis_out_slimit_error
  {
    size_t item_size = sizeof(ros_message.exaxis_out_slimit_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_com_err
  {
    size_t array_size = 6;
    size_t item_size = sizeof(ros_message.dr_com_err[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_err
  {
    size_t item_size = sizeof(ros_message.dr_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: out_sflimit_err
  {
    size_t item_size = sizeof(ros_message.out_sflimit_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: collision_err
  {
    size_t item_size = sizeof(ros_message.collision_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weld_readystate
  {
    size_t item_size = sizeof(ros_message.weld_readystate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm_check_emerg_stop_btn
  {
    size_t item_size = sizeof(ros_message.alarm_check_emerg_stop_btn);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_web_state_com_error
  {
    size_t item_size = sizeof(ros_message.ts_web_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_tm_cmd_com_error
  {
    size_t item_size = sizeof(ros_message.ts_tm_cmd_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_tm_state_com_error
  {
    size_t item_size = sizeof(ros_message.ts_tm_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ctrlboxerror
  {
    size_t item_size = sizeof(ros_message.ctrlboxerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safety_data_state
  {
    size_t item_size = sizeof(ros_message.safety_data_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: forcesensorerrstate
  {
    size_t item_size = sizeof(ros_message.forcesensorerrstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.ctrlopenluaerrcode[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoservoid
  {
    size_t item_size = sizeof(ros_message.auxservoservoid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoerrcode
  {
    size_t item_size = sizeof(ros_message.auxservoerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservostate
  {
    size_t item_size = sizeof(ros_message.auxservostate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoactualpos
  {
    size_t item_size = sizeof(ros_message.auxservoactualpos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoctualspeed
  {
    size_t item_size = sizeof(ros_message.auxservoctualspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoactualtorque
  {
    size_t item_size = sizeof(ros_message.auxservoactualtorque);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extpioinput
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.extpioinput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extpiooutput
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.extpiooutput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extadcinput
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.extadcinput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extadcoutput
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.extadcoutput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: reconnect_flag
  {
    size_t item_size = sizeof(ros_message.reconnect_flag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxiscoordid
  {
    size_t item_size = sizeof(ros_message.exaxiscoordid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_status_1
  {
    size_t item_size = sizeof(ros_message.slave_status_1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_status_2
  {
    size_t item_size = sizeof(ros_message.slave_status_2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_domain_id
  {
    size_t item_size = sizeof(ros_message.slave_domain_id);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: program_run_state
  {
    size_t item_size = sizeof(ros_message.program_run_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: speed_scale_manual
  {
    size_t item_size = sizeof(ros_message.speed_scale_manual);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: speed_scale_auto
  {
    size_t item_size = sizeof(ros_message.speed_scale_auto);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}


size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
max_serialized_size_RobotNonrtState(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Member: j1_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j2_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j3_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j4_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j5_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j6_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j1_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j2_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j3_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j4_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j5_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: j6_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: cart_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: flange_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: exaxispos1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: exaxistatus1
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: exaxispos2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: exaxistatus2
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: exaxispos3
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: exaxistatus3
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: exaxispos4
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: exaxistatus4
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: ft_fx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_fy_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_fz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_tx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_ty_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_tz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: ft_actstatus
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: robot_mode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: tool_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: work_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: prg_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: abnormal_stop
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: prg_name
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }
  // Member: prg_total_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: prg_cur_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dgt_output_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dgt_input_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: tl_dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: tl_dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: emg
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: safetyboxsig
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: robot_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: grip_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: weldbreakoffstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: weldarcstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: welding_voltage
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: welding_current
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: weldtrackspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: main_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: sub_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: check_sum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: timestamp
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: version
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }
  // Member: tpd_exception
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: alarm_reboot_robot
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: modbusmasterconnectstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: mdbsslaveconnect
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: socket_conn_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: socket_read_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: btn_box_stop_signa
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: strangeposflag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: drag_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: safetydoor_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: safetyplanealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: motionalarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: interferealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: endluaerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: dr_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: udpcmdstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: aliveslavenumerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: gripperfaultnum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: slavecomerror
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: cmdpointerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ioerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: grippererro
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: fileerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: paraerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: exaxis_out_slimit_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dr_com_err
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: dr_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: out_sflimit_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: collision_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: weld_readystate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: alarm_check_emerg_stop_btn
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ts_web_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ts_tm_cmd_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ts_tm_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ctrlboxerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: safety_data_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: forcesensorerrstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: auxservoservoid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: auxservoerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: auxservostate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: auxservoactualpos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: auxservoctualspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: auxservoactualtorque
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: extpioinput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: extpiooutput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: extadcinput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: extadcoutput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }
  // Member: reconnect_flag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: exaxiscoordid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: slave_status_1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: slave_status_2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: slave_domain_id
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }
  // Member: program_run_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }
  // Member: speed_scale_manual
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // Member: speed_scale_auto
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = fairino_msgs::msg::RobotNonrtState;
    is_plain =
      (
      offsetof(DataType, speed_scale_auto) +
      last_member_size
      ) == ret_val;
  }

  return ret_val;
}

bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
cdr_serialize_key(
  const fairino_msgs::msg::RobotNonrtState & ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Member: j1_cur_pos
  cdr << ros_message.j1_cur_pos;

  // Member: j2_cur_pos
  cdr << ros_message.j2_cur_pos;

  // Member: j3_cur_pos
  cdr << ros_message.j3_cur_pos;

  // Member: j4_cur_pos
  cdr << ros_message.j4_cur_pos;

  // Member: j5_cur_pos
  cdr << ros_message.j5_cur_pos;

  // Member: j6_cur_pos
  cdr << ros_message.j6_cur_pos;

  // Member: j1_cur_tor
  cdr << ros_message.j1_cur_tor;

  // Member: j2_cur_tor
  cdr << ros_message.j2_cur_tor;

  // Member: j3_cur_tor
  cdr << ros_message.j3_cur_tor;

  // Member: j4_cur_tor
  cdr << ros_message.j4_cur_tor;

  // Member: j5_cur_tor
  cdr << ros_message.j5_cur_tor;

  // Member: j6_cur_tor
  cdr << ros_message.j6_cur_tor;

  // Member: cart_x_cur_pos
  cdr << ros_message.cart_x_cur_pos;

  // Member: cart_y_cur_pos
  cdr << ros_message.cart_y_cur_pos;

  // Member: cart_z_cur_pos
  cdr << ros_message.cart_z_cur_pos;

  // Member: cart_a_cur_pos
  cdr << ros_message.cart_a_cur_pos;

  // Member: cart_b_cur_pos
  cdr << ros_message.cart_b_cur_pos;

  // Member: cart_c_cur_pos
  cdr << ros_message.cart_c_cur_pos;

  // Member: flange_x_cur_pos
  cdr << ros_message.flange_x_cur_pos;

  // Member: flange_y_cur_pos
  cdr << ros_message.flange_y_cur_pos;

  // Member: flange_z_cur_pos
  cdr << ros_message.flange_z_cur_pos;

  // Member: flange_a_cur_pos
  cdr << ros_message.flange_a_cur_pos;

  // Member: flange_b_cur_pos
  cdr << ros_message.flange_b_cur_pos;

  // Member: flange_c_cur_pos
  cdr << ros_message.flange_c_cur_pos;

  // Member: exaxispos1
  cdr << ros_message.exaxispos1;

  // Member: exaxistatus1
  {
    cdr << ros_message.exaxistatus1;
  }

  // Member: exaxispos2
  cdr << ros_message.exaxispos2;

  // Member: exaxistatus2
  {
    cdr << ros_message.exaxistatus2;
  }

  // Member: exaxispos3
  cdr << ros_message.exaxispos3;

  // Member: exaxistatus3
  {
    cdr << ros_message.exaxistatus3;
  }

  // Member: exaxispos4
  cdr << ros_message.exaxispos4;

  // Member: exaxistatus4
  {
    cdr << ros_message.exaxistatus4;
  }

  // Member: ft_fx_data
  cdr << ros_message.ft_fx_data;

  // Member: ft_fy_data
  cdr << ros_message.ft_fy_data;

  // Member: ft_fz_data
  cdr << ros_message.ft_fz_data;

  // Member: ft_tx_data
  cdr << ros_message.ft_tx_data;

  // Member: ft_ty_data
  cdr << ros_message.ft_ty_data;

  // Member: ft_tz_data
  cdr << ros_message.ft_tz_data;

  // Member: ft_actstatus
  cdr << ros_message.ft_actstatus;

  // Member: robot_mode
  cdr << ros_message.robot_mode;

  // Member: tool_num
  cdr << ros_message.tool_num;

  // Member: work_num
  cdr << ros_message.work_num;

  // Member: prg_state
  cdr << ros_message.prg_state;

  // Member: abnormal_stop
  cdr << ros_message.abnormal_stop;

  // Member: prg_name
  cdr << ros_message.prg_name;

  // Member: prg_total_line
  cdr << ros_message.prg_total_line;

  // Member: prg_cur_line
  cdr << ros_message.prg_cur_line;

  // Member: dgt_output_h
  cdr << ros_message.dgt_output_h;

  // Member: dgt_output_l
  cdr << ros_message.dgt_output_l;

  // Member: dgt_input_h
  cdr << ros_message.dgt_input_h;

  // Member: dgt_input_l
  cdr << ros_message.dgt_input_l;

  // Member: tl_dgt_output_l
  cdr << ros_message.tl_dgt_output_l;

  // Member: tl_dgt_input_l
  cdr << ros_message.tl_dgt_input_l;

  // Member: emg
  cdr << ros_message.emg;

  // Member: safetyboxsig
  {
    cdr << ros_message.safetyboxsig;
  }

  // Member: robot_motion_done
  cdr << ros_message.robot_motion_done;

  // Member: grip_motion_done
  cdr << ros_message.grip_motion_done;

  // Member: weldbreakoffstate
  cdr << ros_message.weldbreakoffstate;

  // Member: weldarcstate
  cdr << ros_message.weldarcstate;

  // Member: welding_voltage
  cdr << ros_message.welding_voltage;

  // Member: welding_current
  cdr << ros_message.welding_current;

  // Member: weldtrackspeed
  cdr << ros_message.weldtrackspeed;

  // Member: main_error_code
  cdr << ros_message.main_error_code;

  // Member: sub_error_code
  cdr << ros_message.sub_error_code;

  // Member: check_sum
  cdr << ros_message.check_sum;

  // Member: timestamp
  cdr << ros_message.timestamp;

  // Member: version
  cdr << ros_message.version;

  // Member: tpd_exception
  cdr << ros_message.tpd_exception;

  // Member: alarm_reboot_robot
  cdr << ros_message.alarm_reboot_robot;

  // Member: modbusmasterconnectstate
  cdr << ros_message.modbusmasterconnectstate;

  // Member: mdbsslaveconnect
  cdr << ros_message.mdbsslaveconnect;

  // Member: socket_conn_timeout
  cdr << ros_message.socket_conn_timeout;

  // Member: socket_read_timeout
  cdr << ros_message.socket_read_timeout;

  // Member: btn_box_stop_signa
  cdr << ros_message.btn_box_stop_signa;

  // Member: strangeposflag
  cdr << ros_message.strangeposflag;

  // Member: drag_alarm
  cdr << ros_message.drag_alarm;

  // Member: alarm
  cdr << ros_message.alarm;

  // Member: safetydoor_alarm
  cdr << ros_message.safetydoor_alarm;

  // Member: safetyplanealarm
  cdr << ros_message.safetyplanealarm;

  // Member: motionalarm
  cdr << ros_message.motionalarm;

  // Member: interferealarm
  cdr << ros_message.interferealarm;

  // Member: endluaerrcode
  cdr << ros_message.endluaerrcode;

  // Member: dr_alarm
  cdr << ros_message.dr_alarm;

  // Member: udpcmdstate
  cdr << ros_message.udpcmdstate;

  // Member: aliveslavenumerror
  cdr << ros_message.aliveslavenumerror;

  // Member: gripperfaultnum
  cdr << ros_message.gripperfaultnum;

  // Member: slavecomerror
  {
    cdr << ros_message.slavecomerror;
  }

  // Member: cmdpointerror
  cdr << ros_message.cmdpointerror;

  // Member: ioerror
  cdr << ros_message.ioerror;

  // Member: grippererro
  cdr << ros_message.grippererro;

  // Member: fileerror
  cdr << ros_message.fileerror;

  // Member: paraerror
  cdr << ros_message.paraerror;

  // Member: exaxis_out_slimit_error
  cdr << ros_message.exaxis_out_slimit_error;

  // Member: dr_com_err
  {
    cdr << ros_message.dr_com_err;
  }

  // Member: dr_err
  cdr << ros_message.dr_err;

  // Member: out_sflimit_err
  cdr << ros_message.out_sflimit_err;

  // Member: collision_err
  cdr << ros_message.collision_err;

  // Member: weld_readystate
  cdr << ros_message.weld_readystate;

  // Member: alarm_check_emerg_stop_btn
  cdr << ros_message.alarm_check_emerg_stop_btn;

  // Member: ts_web_state_com_error
  cdr << ros_message.ts_web_state_com_error;

  // Member: ts_tm_cmd_com_error
  cdr << ros_message.ts_tm_cmd_com_error;

  // Member: ts_tm_state_com_error
  cdr << ros_message.ts_tm_state_com_error;

  // Member: ctrlboxerror
  cdr << ros_message.ctrlboxerror;

  // Member: safety_data_state
  cdr << ros_message.safety_data_state;

  // Member: forcesensorerrstate
  cdr << ros_message.forcesensorerrstate;

  // Member: ctrlopenluaerrcode
  {
    cdr << ros_message.ctrlopenluaerrcode;
  }

  // Member: auxservoservoid
  cdr << ros_message.auxservoservoid;

  // Member: auxservoerrcode
  cdr << ros_message.auxservoerrcode;

  // Member: auxservostate
  cdr << ros_message.auxservostate;

  // Member: auxservoactualpos
  cdr << ros_message.auxservoactualpos;

  // Member: auxservoctualspeed
  cdr << ros_message.auxservoctualspeed;

  // Member: auxservoactualtorque
  cdr << ros_message.auxservoactualtorque;

  // Member: extpioinput
  {
    cdr << ros_message.extpioinput;
  }

  // Member: extpiooutput
  {
    cdr << ros_message.extpiooutput;
  }

  // Member: extadcinput
  {
    cdr << ros_message.extadcinput;
  }

  // Member: extadcoutput
  {
    cdr << ros_message.extadcoutput;
  }

  // Member: reconnect_flag
  cdr << ros_message.reconnect_flag;

  // Member: exaxiscoordid
  cdr << ros_message.exaxiscoordid;

  // Member: slave_status_1
  cdr << ros_message.slave_status_1;

  // Member: slave_status_2
  cdr << ros_message.slave_status_2;

  // Member: slave_domain_id
  cdr << ros_message.slave_domain_id;

  // Member: program_run_state
  cdr << ros_message.program_run_state;

  // Member: speed_scale_manual
  cdr << ros_message.speed_scale_manual;

  // Member: speed_scale_auto
  cdr << ros_message.speed_scale_auto;

  return true;
}

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
get_serialized_size_key(
  const fairino_msgs::msg::RobotNonrtState & ros_message,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Member: j1_cur_pos
  {
    size_t item_size = sizeof(ros_message.j1_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j2_cur_pos
  {
    size_t item_size = sizeof(ros_message.j2_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j3_cur_pos
  {
    size_t item_size = sizeof(ros_message.j3_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j4_cur_pos
  {
    size_t item_size = sizeof(ros_message.j4_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j5_cur_pos
  {
    size_t item_size = sizeof(ros_message.j5_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j6_cur_pos
  {
    size_t item_size = sizeof(ros_message.j6_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j1_cur_tor
  {
    size_t item_size = sizeof(ros_message.j1_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j2_cur_tor
  {
    size_t item_size = sizeof(ros_message.j2_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j3_cur_tor
  {
    size_t item_size = sizeof(ros_message.j3_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j4_cur_tor
  {
    size_t item_size = sizeof(ros_message.j4_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j5_cur_tor
  {
    size_t item_size = sizeof(ros_message.j5_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: j6_cur_tor
  {
    size_t item_size = sizeof(ros_message.j6_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_x_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_y_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_z_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_a_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_b_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cart_c_cur_pos
  {
    size_t item_size = sizeof(ros_message.cart_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_x_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_y_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_z_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_a_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_b_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: flange_c_cur_pos
  {
    size_t item_size = sizeof(ros_message.flange_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos1
  {
    size_t item_size = sizeof(ros_message.exaxispos1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus1
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus1[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos2
  {
    size_t item_size = sizeof(ros_message.exaxispos2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus2
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus2[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos3
  {
    size_t item_size = sizeof(ros_message.exaxispos3);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus3
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus3[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxispos4
  {
    size_t item_size = sizeof(ros_message.exaxispos4);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxistatus4
  {
    size_t array_size = 10;
    size_t item_size = sizeof(ros_message.exaxistatus4[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fx_data
  {
    size_t item_size = sizeof(ros_message.ft_fx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fy_data
  {
    size_t item_size = sizeof(ros_message.ft_fy_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_fz_data
  {
    size_t item_size = sizeof(ros_message.ft_fz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_tx_data
  {
    size_t item_size = sizeof(ros_message.ft_tx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_ty_data
  {
    size_t item_size = sizeof(ros_message.ft_ty_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_tz_data
  {
    size_t item_size = sizeof(ros_message.ft_tz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ft_actstatus
  {
    size_t item_size = sizeof(ros_message.ft_actstatus);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: robot_mode
  {
    size_t item_size = sizeof(ros_message.robot_mode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tool_num
  {
    size_t item_size = sizeof(ros_message.tool_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: work_num
  {
    size_t item_size = sizeof(ros_message.work_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_state
  {
    size_t item_size = sizeof(ros_message.prg_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: abnormal_stop
  {
    size_t item_size = sizeof(ros_message.abnormal_stop);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_name
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message.prg_name.size() + 1);

  // Member: prg_total_line
  {
    size_t item_size = sizeof(ros_message.prg_total_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: prg_cur_line
  {
    size_t item_size = sizeof(ros_message.prg_cur_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_output_h
  {
    size_t item_size = sizeof(ros_message.dgt_output_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_output_l
  {
    size_t item_size = sizeof(ros_message.dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_input_h
  {
    size_t item_size = sizeof(ros_message.dgt_input_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dgt_input_l
  {
    size_t item_size = sizeof(ros_message.dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tl_dgt_output_l
  {
    size_t item_size = sizeof(ros_message.tl_dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: tl_dgt_input_l
  {
    size_t item_size = sizeof(ros_message.tl_dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: emg
  {
    size_t item_size = sizeof(ros_message.emg);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetyboxsig
  {
    size_t array_size = 6;
    size_t item_size = sizeof(ros_message.safetyboxsig[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: robot_motion_done
  {
    size_t item_size = sizeof(ros_message.robot_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: grip_motion_done
  {
    size_t item_size = sizeof(ros_message.grip_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldbreakoffstate
  {
    size_t item_size = sizeof(ros_message.weldbreakoffstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldarcstate
  {
    size_t item_size = sizeof(ros_message.weldarcstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: welding_voltage
  {
    size_t item_size = sizeof(ros_message.welding_voltage);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: welding_current
  {
    size_t item_size = sizeof(ros_message.welding_current);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weldtrackspeed
  {
    size_t item_size = sizeof(ros_message.weldtrackspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: main_error_code
  {
    size_t item_size = sizeof(ros_message.main_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: sub_error_code
  {
    size_t item_size = sizeof(ros_message.sub_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: check_sum
  {
    size_t item_size = sizeof(ros_message.check_sum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: timestamp
  {
    size_t item_size = sizeof(ros_message.timestamp);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message.version.size() + 1);

  // Member: tpd_exception
  {
    size_t item_size = sizeof(ros_message.tpd_exception);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm_reboot_robot
  {
    size_t item_size = sizeof(ros_message.alarm_reboot_robot);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: modbusmasterconnectstate
  {
    size_t item_size = sizeof(ros_message.modbusmasterconnectstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: mdbsslaveconnect
  {
    size_t item_size = sizeof(ros_message.mdbsslaveconnect);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: socket_conn_timeout
  {
    size_t item_size = sizeof(ros_message.socket_conn_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: socket_read_timeout
  {
    size_t item_size = sizeof(ros_message.socket_read_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: btn_box_stop_signa
  {
    size_t item_size = sizeof(ros_message.btn_box_stop_signa);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: strangeposflag
  {
    size_t item_size = sizeof(ros_message.strangeposflag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: drag_alarm
  {
    size_t item_size = sizeof(ros_message.drag_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm
  {
    size_t item_size = sizeof(ros_message.alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetydoor_alarm
  {
    size_t item_size = sizeof(ros_message.safetydoor_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safetyplanealarm
  {
    size_t item_size = sizeof(ros_message.safetyplanealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: motionalarm
  {
    size_t item_size = sizeof(ros_message.motionalarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: interferealarm
  {
    size_t item_size = sizeof(ros_message.interferealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: endluaerrcode
  {
    size_t item_size = sizeof(ros_message.endluaerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_alarm
  {
    size_t item_size = sizeof(ros_message.dr_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: udpcmdstate
  {
    size_t item_size = sizeof(ros_message.udpcmdstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: aliveslavenumerror
  {
    size_t item_size = sizeof(ros_message.aliveslavenumerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: gripperfaultnum
  {
    size_t item_size = sizeof(ros_message.gripperfaultnum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slavecomerror
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.slavecomerror[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: cmdpointerror
  {
    size_t item_size = sizeof(ros_message.cmdpointerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ioerror
  {
    size_t item_size = sizeof(ros_message.ioerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: grippererro
  {
    size_t item_size = sizeof(ros_message.grippererro);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: fileerror
  {
    size_t item_size = sizeof(ros_message.fileerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: paraerror
  {
    size_t item_size = sizeof(ros_message.paraerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxis_out_slimit_error
  {
    size_t item_size = sizeof(ros_message.exaxis_out_slimit_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_com_err
  {
    size_t array_size = 6;
    size_t item_size = sizeof(ros_message.dr_com_err[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: dr_err
  {
    size_t item_size = sizeof(ros_message.dr_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: out_sflimit_err
  {
    size_t item_size = sizeof(ros_message.out_sflimit_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: collision_err
  {
    size_t item_size = sizeof(ros_message.collision_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: weld_readystate
  {
    size_t item_size = sizeof(ros_message.weld_readystate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: alarm_check_emerg_stop_btn
  {
    size_t item_size = sizeof(ros_message.alarm_check_emerg_stop_btn);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_web_state_com_error
  {
    size_t item_size = sizeof(ros_message.ts_web_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_tm_cmd_com_error
  {
    size_t item_size = sizeof(ros_message.ts_tm_cmd_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ts_tm_state_com_error
  {
    size_t item_size = sizeof(ros_message.ts_tm_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ctrlboxerror
  {
    size_t item_size = sizeof(ros_message.ctrlboxerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: safety_data_state
  {
    size_t item_size = sizeof(ros_message.safety_data_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: forcesensorerrstate
  {
    size_t item_size = sizeof(ros_message.forcesensorerrstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.ctrlopenluaerrcode[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoservoid
  {
    size_t item_size = sizeof(ros_message.auxservoservoid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoerrcode
  {
    size_t item_size = sizeof(ros_message.auxservoerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservostate
  {
    size_t item_size = sizeof(ros_message.auxservostate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoactualpos
  {
    size_t item_size = sizeof(ros_message.auxservoactualpos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoctualspeed
  {
    size_t item_size = sizeof(ros_message.auxservoctualspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: auxservoactualtorque
  {
    size_t item_size = sizeof(ros_message.auxservoactualtorque);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extpioinput
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.extpioinput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extpiooutput
  {
    size_t array_size = 8;
    size_t item_size = sizeof(ros_message.extpiooutput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extadcinput
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.extadcinput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: extadcoutput
  {
    size_t array_size = 4;
    size_t item_size = sizeof(ros_message.extadcoutput[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: reconnect_flag
  {
    size_t item_size = sizeof(ros_message.reconnect_flag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: exaxiscoordid
  {
    size_t item_size = sizeof(ros_message.exaxiscoordid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_status_1
  {
    size_t item_size = sizeof(ros_message.slave_status_1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_status_2
  {
    size_t item_size = sizeof(ros_message.slave_status_2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: slave_domain_id
  {
    size_t item_size = sizeof(ros_message.slave_domain_id);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: program_run_state
  {
    size_t item_size = sizeof(ros_message.program_run_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: speed_scale_manual
  {
    size_t item_size = sizeof(ros_message.speed_scale_manual);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Member: speed_scale_auto
  {
    size_t item_size = sizeof(ros_message.speed_scale_auto);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_fairino_msgs
max_serialized_size_key_RobotNonrtState(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // Member: j1_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j2_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j3_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j4_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j5_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j6_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j1_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j2_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j3_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j4_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j5_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: j6_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: cart_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: flange_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: exaxispos1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: exaxistatus1
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: exaxispos2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: exaxistatus2
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: exaxispos3
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: exaxistatus3
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: exaxispos4
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: exaxistatus4
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: ft_fx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_fy_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_fz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_tx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_ty_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_tz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: ft_actstatus
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: robot_mode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: tool_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: work_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: prg_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: abnormal_stop
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: prg_name
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Member: prg_total_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: prg_cur_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dgt_output_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dgt_input_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: tl_dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: tl_dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: emg
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: safetyboxsig
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: robot_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: grip_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: weldbreakoffstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: weldarcstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: welding_voltage
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: welding_current
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: weldtrackspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: main_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: sub_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: check_sum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: timestamp
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: version
  {
    size_t array_size = 1;
    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  // Member: tpd_exception
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: alarm_reboot_robot
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: modbusmasterconnectstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: mdbsslaveconnect
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: socket_conn_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: socket_read_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: btn_box_stop_signa
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: strangeposflag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: drag_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: safetydoor_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: safetyplanealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: motionalarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: interferealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: endluaerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: dr_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: udpcmdstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: aliveslavenumerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: gripperfaultnum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: slavecomerror
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: cmdpointerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ioerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: grippererro
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: fileerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: paraerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: exaxis_out_slimit_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dr_com_err
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: dr_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: out_sflimit_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: collision_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: weld_readystate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: alarm_check_emerg_stop_btn
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ts_web_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ts_tm_cmd_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ts_tm_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ctrlboxerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: safety_data_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: forcesensorerrstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: auxservoservoid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: auxservoerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: auxservostate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: auxservoactualpos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: auxservoctualspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: auxservoactualtorque
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: extpioinput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: extpiooutput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: extadcinput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: extadcoutput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Member: reconnect_flag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: exaxiscoordid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: slave_status_1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: slave_status_2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: slave_domain_id
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Member: program_run_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Member: speed_scale_manual
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Member: speed_scale_auto
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = fairino_msgs::msg::RobotNonrtState;
    is_plain =
      (
      offsetof(DataType, speed_scale_auto) +
      last_member_size
      ) == ret_val;
  }

  return ret_val;
}


static bool _RobotNonrtState__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  auto typed_message =
    static_cast<const fairino_msgs::msg::RobotNonrtState *>(
    untyped_ros_message);
  return cdr_serialize(*typed_message, cdr);
}

static bool _RobotNonrtState__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  auto typed_message =
    static_cast<fairino_msgs::msg::RobotNonrtState *>(
    untyped_ros_message);
  return cdr_deserialize(cdr, *typed_message);
}

static uint32_t _RobotNonrtState__get_serialized_size(
  const void * untyped_ros_message)
{
  auto typed_message =
    static_cast<const fairino_msgs::msg::RobotNonrtState *>(
    untyped_ros_message);
  return static_cast<uint32_t>(get_serialized_size(*typed_message, 0));
}

static size_t _RobotNonrtState__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_RobotNonrtState(full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}

static message_type_support_callbacks_t _RobotNonrtState__callbacks = {
  "fairino_msgs::msg",
  "RobotNonrtState",
  _RobotNonrtState__cdr_serialize,
  _RobotNonrtState__cdr_deserialize,
  _RobotNonrtState__get_serialized_size,
  _RobotNonrtState__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _RobotNonrtState__handle = {
  rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
  &_RobotNonrtState__callbacks,
  get_message_typesupport_handle_function,
  &fairino_msgs__msg__RobotNonrtState__get_type_hash,
  &fairino_msgs__msg__RobotNonrtState__get_type_description,
  &fairino_msgs__msg__RobotNonrtState__get_type_description_sources,
};

}  // namespace typesupport_fastrtps_cpp

}  // namespace msg

}  // namespace fairino_msgs

namespace rosidl_typesupport_fastrtps_cpp
{

template<>
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_EXPORT_fairino_msgs
const rosidl_message_type_support_t *
get_message_type_support_handle<fairino_msgs::msg::RobotNonrtState>()
{
  return &fairino_msgs::msg::typesupport_fastrtps_cpp::_RobotNonrtState__handle;
}

}  // namespace rosidl_typesupport_fastrtps_cpp

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, fairino_msgs, msg, RobotNonrtState)() {
  return &fairino_msgs::msg::typesupport_fastrtps_cpp::_RobotNonrtState__handle;
}

#ifdef __cplusplus
}
#endif
