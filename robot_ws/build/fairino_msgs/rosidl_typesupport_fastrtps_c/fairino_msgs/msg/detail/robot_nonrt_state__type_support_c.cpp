// generated from rosidl_typesupport_fastrtps_c/resource/idl__type_support_c.cpp.em
// with input from fairino_msgs:msg/RobotNonrtState.idl
// generated code does not contain a copyright notice
#include "fairino_msgs/msg/detail/robot_nonrt_state__rosidl_typesupport_fastrtps_c.h"


#include <cassert>
#include <cstddef>
#include <limits>
#include <string>
#include "rosidl_typesupport_fastrtps_c/identifier.h"
#include "rosidl_typesupport_fastrtps_c/serialization_helpers.hpp"
#include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "fairino_msgs/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "fairino_msgs/msg/detail/robot_nonrt_state__struct.h"
#include "fairino_msgs/msg/detail/robot_nonrt_state__functions.h"
#include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "rosidl_runtime_c/string.h"  // prg_name, version
#include "rosidl_runtime_c/string_functions.h"  // prg_name, version

// forward declare type support functions


using _RobotNonrtState__ros_msg_type = fairino_msgs__msg__RobotNonrtState;


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
bool cdr_serialize_fairino_msgs__msg__RobotNonrtState(
  const fairino_msgs__msg__RobotNonrtState * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: j1_cur_pos
  {
    cdr << ros_message->j1_cur_pos;
  }

  // Field name: j2_cur_pos
  {
    cdr << ros_message->j2_cur_pos;
  }

  // Field name: j3_cur_pos
  {
    cdr << ros_message->j3_cur_pos;
  }

  // Field name: j4_cur_pos
  {
    cdr << ros_message->j4_cur_pos;
  }

  // Field name: j5_cur_pos
  {
    cdr << ros_message->j5_cur_pos;
  }

  // Field name: j6_cur_pos
  {
    cdr << ros_message->j6_cur_pos;
  }

  // Field name: j1_cur_tor
  {
    cdr << ros_message->j1_cur_tor;
  }

  // Field name: j2_cur_tor
  {
    cdr << ros_message->j2_cur_tor;
  }

  // Field name: j3_cur_tor
  {
    cdr << ros_message->j3_cur_tor;
  }

  // Field name: j4_cur_tor
  {
    cdr << ros_message->j4_cur_tor;
  }

  // Field name: j5_cur_tor
  {
    cdr << ros_message->j5_cur_tor;
  }

  // Field name: j6_cur_tor
  {
    cdr << ros_message->j6_cur_tor;
  }

  // Field name: cart_x_cur_pos
  {
    cdr << ros_message->cart_x_cur_pos;
  }

  // Field name: cart_y_cur_pos
  {
    cdr << ros_message->cart_y_cur_pos;
  }

  // Field name: cart_z_cur_pos
  {
    cdr << ros_message->cart_z_cur_pos;
  }

  // Field name: cart_a_cur_pos
  {
    cdr << ros_message->cart_a_cur_pos;
  }

  // Field name: cart_b_cur_pos
  {
    cdr << ros_message->cart_b_cur_pos;
  }

  // Field name: cart_c_cur_pos
  {
    cdr << ros_message->cart_c_cur_pos;
  }

  // Field name: flange_x_cur_pos
  {
    cdr << ros_message->flange_x_cur_pos;
  }

  // Field name: flange_y_cur_pos
  {
    cdr << ros_message->flange_y_cur_pos;
  }

  // Field name: flange_z_cur_pos
  {
    cdr << ros_message->flange_z_cur_pos;
  }

  // Field name: flange_a_cur_pos
  {
    cdr << ros_message->flange_a_cur_pos;
  }

  // Field name: flange_b_cur_pos
  {
    cdr << ros_message->flange_b_cur_pos;
  }

  // Field name: flange_c_cur_pos
  {
    cdr << ros_message->flange_c_cur_pos;
  }

  // Field name: exaxispos1
  {
    cdr << ros_message->exaxispos1;
  }

  // Field name: exaxistatus1
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus1;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos2
  {
    cdr << ros_message->exaxispos2;
  }

  // Field name: exaxistatus2
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus2;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos3
  {
    cdr << ros_message->exaxispos3;
  }

  // Field name: exaxistatus3
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus3;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos4
  {
    cdr << ros_message->exaxispos4;
  }

  // Field name: exaxistatus4
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus4;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: ft_fx_data
  {
    cdr << ros_message->ft_fx_data;
  }

  // Field name: ft_fy_data
  {
    cdr << ros_message->ft_fy_data;
  }

  // Field name: ft_fz_data
  {
    cdr << ros_message->ft_fz_data;
  }

  // Field name: ft_tx_data
  {
    cdr << ros_message->ft_tx_data;
  }

  // Field name: ft_ty_data
  {
    cdr << ros_message->ft_ty_data;
  }

  // Field name: ft_tz_data
  {
    cdr << ros_message->ft_tz_data;
  }

  // Field name: ft_actstatus
  {
    cdr << ros_message->ft_actstatus;
  }

  // Field name: robot_mode
  {
    cdr << ros_message->robot_mode;
  }

  // Field name: tool_num
  {
    cdr << ros_message->tool_num;
  }

  // Field name: work_num
  {
    cdr << ros_message->work_num;
  }

  // Field name: prg_state
  {
    cdr << ros_message->prg_state;
  }

  // Field name: abnormal_stop
  {
    cdr << ros_message->abnormal_stop;
  }

  // Field name: prg_name
  {
    const rosidl_runtime_c__String * str = &ros_message->prg_name;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: prg_total_line
  {
    cdr << ros_message->prg_total_line;
  }

  // Field name: prg_cur_line
  {
    cdr << ros_message->prg_cur_line;
  }

  // Field name: dgt_output_h
  {
    cdr << ros_message->dgt_output_h;
  }

  // Field name: dgt_output_l
  {
    cdr << ros_message->dgt_output_l;
  }

  // Field name: dgt_input_h
  {
    cdr << ros_message->dgt_input_h;
  }

  // Field name: dgt_input_l
  {
    cdr << ros_message->dgt_input_l;
  }

  // Field name: tl_dgt_output_l
  {
    cdr << ros_message->tl_dgt_output_l;
  }

  // Field name: tl_dgt_input_l
  {
    cdr << ros_message->tl_dgt_input_l;
  }

  // Field name: emg
  {
    cdr << ros_message->emg;
  }

  // Field name: safetyboxsig
  {
    size_t size = 6;
    auto array_ptr = ros_message->safetyboxsig;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: robot_motion_done
  {
    cdr << ros_message->robot_motion_done;
  }

  // Field name: grip_motion_done
  {
    cdr << ros_message->grip_motion_done;
  }

  // Field name: gripper_position
  {
    cdr << ros_message->gripper_position;
  }

  // Field name: gripper_feedback_valid
  {
    cdr << (ros_message->gripper_feedback_valid ? true : false);
  }

  // Field name: weldbreakoffstate
  {
    cdr << ros_message->weldbreakoffstate;
  }

  // Field name: weldarcstate
  {
    cdr << ros_message->weldarcstate;
  }

  // Field name: welding_voltage
  {
    cdr << ros_message->welding_voltage;
  }

  // Field name: welding_current
  {
    cdr << ros_message->welding_current;
  }

  // Field name: weldtrackspeed
  {
    cdr << ros_message->weldtrackspeed;
  }

  // Field name: main_error_code
  {
    cdr << ros_message->main_error_code;
  }

  // Field name: sub_error_code
  {
    cdr << ros_message->sub_error_code;
  }

  // Field name: check_sum
  {
    cdr << ros_message->check_sum;
  }

  // Field name: timestamp
  {
    cdr << ros_message->timestamp;
  }

  // Field name: version
  {
    const rosidl_runtime_c__String * str = &ros_message->version;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: tpd_exception
  {
    cdr << ros_message->tpd_exception;
  }

  // Field name: alarm_reboot_robot
  {
    cdr << ros_message->alarm_reboot_robot;
  }

  // Field name: modbusmasterconnectstate
  {
    cdr << ros_message->modbusmasterconnectstate;
  }

  // Field name: mdbsslaveconnect
  {
    cdr << ros_message->mdbsslaveconnect;
  }

  // Field name: socket_conn_timeout
  {
    cdr << ros_message->socket_conn_timeout;
  }

  // Field name: socket_read_timeout
  {
    cdr << ros_message->socket_read_timeout;
  }

  // Field name: btn_box_stop_signa
  {
    cdr << ros_message->btn_box_stop_signa;
  }

  // Field name: strangeposflag
  {
    cdr << ros_message->strangeposflag;
  }

  // Field name: drag_alarm
  {
    cdr << ros_message->drag_alarm;
  }

  // Field name: alarm
  {
    cdr << ros_message->alarm;
  }

  // Field name: safetydoor_alarm
  {
    cdr << ros_message->safetydoor_alarm;
  }

  // Field name: safetyplanealarm
  {
    cdr << ros_message->safetyplanealarm;
  }

  // Field name: motionalarm
  {
    cdr << ros_message->motionalarm;
  }

  // Field name: interferealarm
  {
    cdr << ros_message->interferealarm;
  }

  // Field name: endluaerrcode
  {
    cdr << ros_message->endluaerrcode;
  }

  // Field name: dr_alarm
  {
    cdr << ros_message->dr_alarm;
  }

  // Field name: udpcmdstate
  {
    cdr << ros_message->udpcmdstate;
  }

  // Field name: aliveslavenumerror
  {
    cdr << ros_message->aliveslavenumerror;
  }

  // Field name: gripperfaultnum
  {
    cdr << ros_message->gripperfaultnum;
  }

  // Field name: slavecomerror
  {
    size_t size = 8;
    auto array_ptr = ros_message->slavecomerror;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: cmdpointerror
  {
    cdr << ros_message->cmdpointerror;
  }

  // Field name: ioerror
  {
    cdr << ros_message->ioerror;
  }

  // Field name: grippererro
  {
    cdr << ros_message->grippererro;
  }

  // Field name: fileerror
  {
    cdr << ros_message->fileerror;
  }

  // Field name: paraerror
  {
    cdr << ros_message->paraerror;
  }

  // Field name: exaxis_out_slimit_error
  {
    cdr << ros_message->exaxis_out_slimit_error;
  }

  // Field name: dr_com_err
  {
    size_t size = 6;
    auto array_ptr = ros_message->dr_com_err;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: dr_err
  {
    cdr << ros_message->dr_err;
  }

  // Field name: out_sflimit_err
  {
    cdr << ros_message->out_sflimit_err;
  }

  // Field name: collision_err
  {
    cdr << ros_message->collision_err;
  }

  // Field name: weld_readystate
  {
    cdr << ros_message->weld_readystate;
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    cdr << ros_message->alarm_check_emerg_stop_btn;
  }

  // Field name: ts_web_state_com_error
  {
    cdr << ros_message->ts_web_state_com_error;
  }

  // Field name: ts_tm_cmd_com_error
  {
    cdr << ros_message->ts_tm_cmd_com_error;
  }

  // Field name: ts_tm_state_com_error
  {
    cdr << ros_message->ts_tm_state_com_error;
  }

  // Field name: ctrlboxerror
  {
    cdr << ros_message->ctrlboxerror;
  }

  // Field name: safety_data_state
  {
    cdr << ros_message->safety_data_state;
  }

  // Field name: forcesensorerrstate
  {
    cdr << ros_message->forcesensorerrstate;
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t size = 4;
    auto array_ptr = ros_message->ctrlopenluaerrcode;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: auxservoservoid
  {
    cdr << ros_message->auxservoservoid;
  }

  // Field name: auxservoerrcode
  {
    cdr << ros_message->auxservoerrcode;
  }

  // Field name: auxservostate
  {
    cdr << ros_message->auxservostate;
  }

  // Field name: auxservoactualpos
  {
    cdr << ros_message->auxservoactualpos;
  }

  // Field name: auxservoctualspeed
  {
    cdr << ros_message->auxservoctualspeed;
  }

  // Field name: auxservoactualtorque
  {
    cdr << ros_message->auxservoactualtorque;
  }

  // Field name: extpioinput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpioinput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extpiooutput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpiooutput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extadcinput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcinput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extadcoutput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcoutput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: reconnect_flag
  {
    cdr << ros_message->reconnect_flag;
  }

  // Field name: exaxiscoordid
  {
    cdr << ros_message->exaxiscoordid;
  }

  // Field name: slave_status_1
  {
    cdr << ros_message->slave_status_1;
  }

  // Field name: slave_status_2
  {
    cdr << ros_message->slave_status_2;
  }

  // Field name: slave_domain_id
  {
    cdr << ros_message->slave_domain_id;
  }

  // Field name: program_run_state
  {
    cdr << ros_message->program_run_state;
  }

  // Field name: speed_scale_manual
  {
    cdr << ros_message->speed_scale_manual;
  }

  // Field name: speed_scale_auto
  {
    cdr << ros_message->speed_scale_auto;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
bool cdr_deserialize_fairino_msgs__msg__RobotNonrtState(
  eprosima::fastcdr::Cdr & cdr,
  fairino_msgs__msg__RobotNonrtState * ros_message)
{
  // Field name: j1_cur_pos
  {
    cdr >> ros_message->j1_cur_pos;
  }

  // Field name: j2_cur_pos
  {
    cdr >> ros_message->j2_cur_pos;
  }

  // Field name: j3_cur_pos
  {
    cdr >> ros_message->j3_cur_pos;
  }

  // Field name: j4_cur_pos
  {
    cdr >> ros_message->j4_cur_pos;
  }

  // Field name: j5_cur_pos
  {
    cdr >> ros_message->j5_cur_pos;
  }

  // Field name: j6_cur_pos
  {
    cdr >> ros_message->j6_cur_pos;
  }

  // Field name: j1_cur_tor
  {
    cdr >> ros_message->j1_cur_tor;
  }

  // Field name: j2_cur_tor
  {
    cdr >> ros_message->j2_cur_tor;
  }

  // Field name: j3_cur_tor
  {
    cdr >> ros_message->j3_cur_tor;
  }

  // Field name: j4_cur_tor
  {
    cdr >> ros_message->j4_cur_tor;
  }

  // Field name: j5_cur_tor
  {
    cdr >> ros_message->j5_cur_tor;
  }

  // Field name: j6_cur_tor
  {
    cdr >> ros_message->j6_cur_tor;
  }

  // Field name: cart_x_cur_pos
  {
    cdr >> ros_message->cart_x_cur_pos;
  }

  // Field name: cart_y_cur_pos
  {
    cdr >> ros_message->cart_y_cur_pos;
  }

  // Field name: cart_z_cur_pos
  {
    cdr >> ros_message->cart_z_cur_pos;
  }

  // Field name: cart_a_cur_pos
  {
    cdr >> ros_message->cart_a_cur_pos;
  }

  // Field name: cart_b_cur_pos
  {
    cdr >> ros_message->cart_b_cur_pos;
  }

  // Field name: cart_c_cur_pos
  {
    cdr >> ros_message->cart_c_cur_pos;
  }

  // Field name: flange_x_cur_pos
  {
    cdr >> ros_message->flange_x_cur_pos;
  }

  // Field name: flange_y_cur_pos
  {
    cdr >> ros_message->flange_y_cur_pos;
  }

  // Field name: flange_z_cur_pos
  {
    cdr >> ros_message->flange_z_cur_pos;
  }

  // Field name: flange_a_cur_pos
  {
    cdr >> ros_message->flange_a_cur_pos;
  }

  // Field name: flange_b_cur_pos
  {
    cdr >> ros_message->flange_b_cur_pos;
  }

  // Field name: flange_c_cur_pos
  {
    cdr >> ros_message->flange_c_cur_pos;
  }

  // Field name: exaxispos1
  {
    cdr >> ros_message->exaxispos1;
  }

  // Field name: exaxistatus1
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus1;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: exaxispos2
  {
    cdr >> ros_message->exaxispos2;
  }

  // Field name: exaxistatus2
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus2;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: exaxispos3
  {
    cdr >> ros_message->exaxispos3;
  }

  // Field name: exaxistatus3
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus3;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: exaxispos4
  {
    cdr >> ros_message->exaxispos4;
  }

  // Field name: exaxistatus4
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus4;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: ft_fx_data
  {
    cdr >> ros_message->ft_fx_data;
  }

  // Field name: ft_fy_data
  {
    cdr >> ros_message->ft_fy_data;
  }

  // Field name: ft_fz_data
  {
    cdr >> ros_message->ft_fz_data;
  }

  // Field name: ft_tx_data
  {
    cdr >> ros_message->ft_tx_data;
  }

  // Field name: ft_ty_data
  {
    cdr >> ros_message->ft_ty_data;
  }

  // Field name: ft_tz_data
  {
    cdr >> ros_message->ft_tz_data;
  }

  // Field name: ft_actstatus
  {
    cdr >> ros_message->ft_actstatus;
  }

  // Field name: robot_mode
  {
    cdr >> ros_message->robot_mode;
  }

  // Field name: tool_num
  {
    cdr >> ros_message->tool_num;
  }

  // Field name: work_num
  {
    cdr >> ros_message->work_num;
  }

  // Field name: prg_state
  {
    cdr >> ros_message->prg_state;
  }

  // Field name: abnormal_stop
  {
    cdr >> ros_message->abnormal_stop;
  }

  // Field name: prg_name
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->prg_name.data) {
      rosidl_runtime_c__String__init(&ros_message->prg_name);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->prg_name,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'prg_name'\n");
      return false;
    }
  }

  // Field name: prg_total_line
  {
    cdr >> ros_message->prg_total_line;
  }

  // Field name: prg_cur_line
  {
    cdr >> ros_message->prg_cur_line;
  }

  // Field name: dgt_output_h
  {
    cdr >> ros_message->dgt_output_h;
  }

  // Field name: dgt_output_l
  {
    cdr >> ros_message->dgt_output_l;
  }

  // Field name: dgt_input_h
  {
    cdr >> ros_message->dgt_input_h;
  }

  // Field name: dgt_input_l
  {
    cdr >> ros_message->dgt_input_l;
  }

  // Field name: tl_dgt_output_l
  {
    cdr >> ros_message->tl_dgt_output_l;
  }

  // Field name: tl_dgt_input_l
  {
    cdr >> ros_message->tl_dgt_input_l;
  }

  // Field name: emg
  {
    cdr >> ros_message->emg;
  }

  // Field name: safetyboxsig
  {
    size_t size = 6;
    auto array_ptr = ros_message->safetyboxsig;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: robot_motion_done
  {
    cdr >> ros_message->robot_motion_done;
  }

  // Field name: grip_motion_done
  {
    cdr >> ros_message->grip_motion_done;
  }

  // Field name: gripper_position
  {
    cdr >> ros_message->gripper_position;
  }

  // Field name: gripper_feedback_valid
  {
    uint8_t tmp;
    cdr >> tmp;
    ros_message->gripper_feedback_valid = tmp ? true : false;
  }

  // Field name: weldbreakoffstate
  {
    cdr >> ros_message->weldbreakoffstate;
  }

  // Field name: weldarcstate
  {
    cdr >> ros_message->weldarcstate;
  }

  // Field name: welding_voltage
  {
    cdr >> ros_message->welding_voltage;
  }

  // Field name: welding_current
  {
    cdr >> ros_message->welding_current;
  }

  // Field name: weldtrackspeed
  {
    cdr >> ros_message->weldtrackspeed;
  }

  // Field name: main_error_code
  {
    cdr >> ros_message->main_error_code;
  }

  // Field name: sub_error_code
  {
    cdr >> ros_message->sub_error_code;
  }

  // Field name: check_sum
  {
    cdr >> ros_message->check_sum;
  }

  // Field name: timestamp
  {
    cdr >> ros_message->timestamp;
  }

  // Field name: version
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->version.data) {
      rosidl_runtime_c__String__init(&ros_message->version);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->version,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'version'\n");
      return false;
    }
  }

  // Field name: tpd_exception
  {
    cdr >> ros_message->tpd_exception;
  }

  // Field name: alarm_reboot_robot
  {
    cdr >> ros_message->alarm_reboot_robot;
  }

  // Field name: modbusmasterconnectstate
  {
    cdr >> ros_message->modbusmasterconnectstate;
  }

  // Field name: mdbsslaveconnect
  {
    cdr >> ros_message->mdbsslaveconnect;
  }

  // Field name: socket_conn_timeout
  {
    cdr >> ros_message->socket_conn_timeout;
  }

  // Field name: socket_read_timeout
  {
    cdr >> ros_message->socket_read_timeout;
  }

  // Field name: btn_box_stop_signa
  {
    cdr >> ros_message->btn_box_stop_signa;
  }

  // Field name: strangeposflag
  {
    cdr >> ros_message->strangeposflag;
  }

  // Field name: drag_alarm
  {
    cdr >> ros_message->drag_alarm;
  }

  // Field name: alarm
  {
    cdr >> ros_message->alarm;
  }

  // Field name: safetydoor_alarm
  {
    cdr >> ros_message->safetydoor_alarm;
  }

  // Field name: safetyplanealarm
  {
    cdr >> ros_message->safetyplanealarm;
  }

  // Field name: motionalarm
  {
    cdr >> ros_message->motionalarm;
  }

  // Field name: interferealarm
  {
    cdr >> ros_message->interferealarm;
  }

  // Field name: endluaerrcode
  {
    cdr >> ros_message->endluaerrcode;
  }

  // Field name: dr_alarm
  {
    cdr >> ros_message->dr_alarm;
  }

  // Field name: udpcmdstate
  {
    cdr >> ros_message->udpcmdstate;
  }

  // Field name: aliveslavenumerror
  {
    cdr >> ros_message->aliveslavenumerror;
  }

  // Field name: gripperfaultnum
  {
    cdr >> ros_message->gripperfaultnum;
  }

  // Field name: slavecomerror
  {
    size_t size = 8;
    auto array_ptr = ros_message->slavecomerror;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: cmdpointerror
  {
    cdr >> ros_message->cmdpointerror;
  }

  // Field name: ioerror
  {
    cdr >> ros_message->ioerror;
  }

  // Field name: grippererro
  {
    cdr >> ros_message->grippererro;
  }

  // Field name: fileerror
  {
    cdr >> ros_message->fileerror;
  }

  // Field name: paraerror
  {
    cdr >> ros_message->paraerror;
  }

  // Field name: exaxis_out_slimit_error
  {
    cdr >> ros_message->exaxis_out_slimit_error;
  }

  // Field name: dr_com_err
  {
    size_t size = 6;
    auto array_ptr = ros_message->dr_com_err;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: dr_err
  {
    cdr >> ros_message->dr_err;
  }

  // Field name: out_sflimit_err
  {
    cdr >> ros_message->out_sflimit_err;
  }

  // Field name: collision_err
  {
    cdr >> ros_message->collision_err;
  }

  // Field name: weld_readystate
  {
    cdr >> ros_message->weld_readystate;
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    cdr >> ros_message->alarm_check_emerg_stop_btn;
  }

  // Field name: ts_web_state_com_error
  {
    cdr >> ros_message->ts_web_state_com_error;
  }

  // Field name: ts_tm_cmd_com_error
  {
    cdr >> ros_message->ts_tm_cmd_com_error;
  }

  // Field name: ts_tm_state_com_error
  {
    cdr >> ros_message->ts_tm_state_com_error;
  }

  // Field name: ctrlboxerror
  {
    cdr >> ros_message->ctrlboxerror;
  }

  // Field name: safety_data_state
  {
    cdr >> ros_message->safety_data_state;
  }

  // Field name: forcesensorerrstate
  {
    cdr >> ros_message->forcesensorerrstate;
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t size = 4;
    auto array_ptr = ros_message->ctrlopenluaerrcode;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: auxservoservoid
  {
    cdr >> ros_message->auxservoservoid;
  }

  // Field name: auxservoerrcode
  {
    cdr >> ros_message->auxservoerrcode;
  }

  // Field name: auxservostate
  {
    cdr >> ros_message->auxservostate;
  }

  // Field name: auxservoactualpos
  {
    cdr >> ros_message->auxservoactualpos;
  }

  // Field name: auxservoctualspeed
  {
    cdr >> ros_message->auxservoctualspeed;
  }

  // Field name: auxservoactualtorque
  {
    cdr >> ros_message->auxservoactualtorque;
  }

  // Field name: extpioinput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpioinput;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: extpiooutput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpiooutput;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: extadcinput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcinput;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: extadcoutput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcoutput;
    cdr.deserialize_array(array_ptr, size);
  }

  // Field name: reconnect_flag
  {
    cdr >> ros_message->reconnect_flag;
  }

  // Field name: exaxiscoordid
  {
    cdr >> ros_message->exaxiscoordid;
  }

  // Field name: slave_status_1
  {
    cdr >> ros_message->slave_status_1;
  }

  // Field name: slave_status_2
  {
    cdr >> ros_message->slave_status_2;
  }

  // Field name: slave_domain_id
  {
    cdr >> ros_message->slave_domain_id;
  }

  // Field name: program_run_state
  {
    cdr >> ros_message->program_run_state;
  }

  // Field name: speed_scale_manual
  {
    cdr >> ros_message->speed_scale_manual;
  }

  // Field name: speed_scale_auto
  {
    cdr >> ros_message->speed_scale_auto;
  }

  return true;
}  // NOLINT(readability/fn_size)


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
size_t get_serialized_size_fairino_msgs__msg__RobotNonrtState(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _RobotNonrtState__ros_msg_type * ros_message = static_cast<const _RobotNonrtState__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: j1_cur_pos
  {
    size_t item_size = sizeof(ros_message->j1_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j2_cur_pos
  {
    size_t item_size = sizeof(ros_message->j2_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j3_cur_pos
  {
    size_t item_size = sizeof(ros_message->j3_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j4_cur_pos
  {
    size_t item_size = sizeof(ros_message->j4_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j5_cur_pos
  {
    size_t item_size = sizeof(ros_message->j5_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j6_cur_pos
  {
    size_t item_size = sizeof(ros_message->j6_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j1_cur_tor
  {
    size_t item_size = sizeof(ros_message->j1_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j2_cur_tor
  {
    size_t item_size = sizeof(ros_message->j2_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j3_cur_tor
  {
    size_t item_size = sizeof(ros_message->j3_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j4_cur_tor
  {
    size_t item_size = sizeof(ros_message->j4_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j5_cur_tor
  {
    size_t item_size = sizeof(ros_message->j5_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j6_cur_tor
  {
    size_t item_size = sizeof(ros_message->j6_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_x_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_y_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_z_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_a_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_b_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_c_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_x_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_y_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_z_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_a_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_b_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_c_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos1
  {
    size_t item_size = sizeof(ros_message->exaxispos1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus1
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus1;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos2
  {
    size_t item_size = sizeof(ros_message->exaxispos2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus2
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus2;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos3
  {
    size_t item_size = sizeof(ros_message->exaxispos3);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus3
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus3;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos4
  {
    size_t item_size = sizeof(ros_message->exaxispos4);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus4
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus4;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fx_data
  {
    size_t item_size = sizeof(ros_message->ft_fx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fy_data
  {
    size_t item_size = sizeof(ros_message->ft_fy_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fz_data
  {
    size_t item_size = sizeof(ros_message->ft_fz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_tx_data
  {
    size_t item_size = sizeof(ros_message->ft_tx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_ty_data
  {
    size_t item_size = sizeof(ros_message->ft_ty_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_tz_data
  {
    size_t item_size = sizeof(ros_message->ft_tz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_actstatus
  {
    size_t item_size = sizeof(ros_message->ft_actstatus);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: robot_mode
  {
    size_t item_size = sizeof(ros_message->robot_mode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tool_num
  {
    size_t item_size = sizeof(ros_message->tool_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: work_num
  {
    size_t item_size = sizeof(ros_message->work_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_state
  {
    size_t item_size = sizeof(ros_message->prg_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: abnormal_stop
  {
    size_t item_size = sizeof(ros_message->abnormal_stop);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_name
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->prg_name.size + 1);

  // Field name: prg_total_line
  {
    size_t item_size = sizeof(ros_message->prg_total_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_cur_line
  {
    size_t item_size = sizeof(ros_message->prg_cur_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_output_h
  {
    size_t item_size = sizeof(ros_message->dgt_output_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_output_l
  {
    size_t item_size = sizeof(ros_message->dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_input_h
  {
    size_t item_size = sizeof(ros_message->dgt_input_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_input_l
  {
    size_t item_size = sizeof(ros_message->dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tl_dgt_output_l
  {
    size_t item_size = sizeof(ros_message->tl_dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tl_dgt_input_l
  {
    size_t item_size = sizeof(ros_message->tl_dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: emg
  {
    size_t item_size = sizeof(ros_message->emg);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetyboxsig
  {
    size_t array_size = 6;
    auto array_ptr = ros_message->safetyboxsig;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: robot_motion_done
  {
    size_t item_size = sizeof(ros_message->robot_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: grip_motion_done
  {
    size_t item_size = sizeof(ros_message->grip_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripper_position
  {
    size_t item_size = sizeof(ros_message->gripper_position);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripper_feedback_valid
  {
    size_t item_size = sizeof(ros_message->gripper_feedback_valid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldbreakoffstate
  {
    size_t item_size = sizeof(ros_message->weldbreakoffstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldarcstate
  {
    size_t item_size = sizeof(ros_message->weldarcstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: welding_voltage
  {
    size_t item_size = sizeof(ros_message->welding_voltage);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: welding_current
  {
    size_t item_size = sizeof(ros_message->welding_current);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldtrackspeed
  {
    size_t item_size = sizeof(ros_message->weldtrackspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: main_error_code
  {
    size_t item_size = sizeof(ros_message->main_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: sub_error_code
  {
    size_t item_size = sizeof(ros_message->sub_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: check_sum
  {
    size_t item_size = sizeof(ros_message->check_sum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: timestamp
  {
    size_t item_size = sizeof(ros_message->timestamp);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->version.size + 1);

  // Field name: tpd_exception
  {
    size_t item_size = sizeof(ros_message->tpd_exception);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm_reboot_robot
  {
    size_t item_size = sizeof(ros_message->alarm_reboot_robot);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: modbusmasterconnectstate
  {
    size_t item_size = sizeof(ros_message->modbusmasterconnectstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: mdbsslaveconnect
  {
    size_t item_size = sizeof(ros_message->mdbsslaveconnect);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: socket_conn_timeout
  {
    size_t item_size = sizeof(ros_message->socket_conn_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: socket_read_timeout
  {
    size_t item_size = sizeof(ros_message->socket_read_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: btn_box_stop_signa
  {
    size_t item_size = sizeof(ros_message->btn_box_stop_signa);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: strangeposflag
  {
    size_t item_size = sizeof(ros_message->strangeposflag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: drag_alarm
  {
    size_t item_size = sizeof(ros_message->drag_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm
  {
    size_t item_size = sizeof(ros_message->alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetydoor_alarm
  {
    size_t item_size = sizeof(ros_message->safetydoor_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetyplanealarm
  {
    size_t item_size = sizeof(ros_message->safetyplanealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: motionalarm
  {
    size_t item_size = sizeof(ros_message->motionalarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: interferealarm
  {
    size_t item_size = sizeof(ros_message->interferealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: endluaerrcode
  {
    size_t item_size = sizeof(ros_message->endluaerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_alarm
  {
    size_t item_size = sizeof(ros_message->dr_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: udpcmdstate
  {
    size_t item_size = sizeof(ros_message->udpcmdstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: aliveslavenumerror
  {
    size_t item_size = sizeof(ros_message->aliveslavenumerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripperfaultnum
  {
    size_t item_size = sizeof(ros_message->gripperfaultnum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slavecomerror
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->slavecomerror;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cmdpointerror
  {
    size_t item_size = sizeof(ros_message->cmdpointerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ioerror
  {
    size_t item_size = sizeof(ros_message->ioerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: grippererro
  {
    size_t item_size = sizeof(ros_message->grippererro);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: fileerror
  {
    size_t item_size = sizeof(ros_message->fileerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: paraerror
  {
    size_t item_size = sizeof(ros_message->paraerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxis_out_slimit_error
  {
    size_t item_size = sizeof(ros_message->exaxis_out_slimit_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_com_err
  {
    size_t array_size = 6;
    auto array_ptr = ros_message->dr_com_err;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_err
  {
    size_t item_size = sizeof(ros_message->dr_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: out_sflimit_err
  {
    size_t item_size = sizeof(ros_message->out_sflimit_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: collision_err
  {
    size_t item_size = sizeof(ros_message->collision_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weld_readystate
  {
    size_t item_size = sizeof(ros_message->weld_readystate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    size_t item_size = sizeof(ros_message->alarm_check_emerg_stop_btn);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_web_state_com_error
  {
    size_t item_size = sizeof(ros_message->ts_web_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_tm_cmd_com_error
  {
    size_t item_size = sizeof(ros_message->ts_tm_cmd_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_tm_state_com_error
  {
    size_t item_size = sizeof(ros_message->ts_tm_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ctrlboxerror
  {
    size_t item_size = sizeof(ros_message->ctrlboxerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safety_data_state
  {
    size_t item_size = sizeof(ros_message->safety_data_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: forcesensorerrstate
  {
    size_t item_size = sizeof(ros_message->forcesensorerrstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->ctrlopenluaerrcode;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoservoid
  {
    size_t item_size = sizeof(ros_message->auxservoservoid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoerrcode
  {
    size_t item_size = sizeof(ros_message->auxservoerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservostate
  {
    size_t item_size = sizeof(ros_message->auxservostate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoactualpos
  {
    size_t item_size = sizeof(ros_message->auxservoactualpos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoctualspeed
  {
    size_t item_size = sizeof(ros_message->auxservoctualspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoactualtorque
  {
    size_t item_size = sizeof(ros_message->auxservoactualtorque);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extpioinput
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->extpioinput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extpiooutput
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->extpiooutput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extadcinput
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->extadcinput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extadcoutput
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->extadcoutput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: reconnect_flag
  {
    size_t item_size = sizeof(ros_message->reconnect_flag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxiscoordid
  {
    size_t item_size = sizeof(ros_message->exaxiscoordid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_status_1
  {
    size_t item_size = sizeof(ros_message->slave_status_1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_status_2
  {
    size_t item_size = sizeof(ros_message->slave_status_2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_domain_id
  {
    size_t item_size = sizeof(ros_message->slave_domain_id);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: program_run_state
  {
    size_t item_size = sizeof(ros_message->program_run_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: speed_scale_manual
  {
    size_t item_size = sizeof(ros_message->speed_scale_manual);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: speed_scale_auto
  {
    size_t item_size = sizeof(ros_message->speed_scale_auto);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}


ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
size_t max_serialized_size_fairino_msgs__msg__RobotNonrtState(
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

  // Field name: j1_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j2_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j3_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j4_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j5_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j6_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j1_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j2_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j3_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j4_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j5_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j6_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxispos1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus1
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus2
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos3
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus3
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos4
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus4
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: ft_fx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_fy_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_fz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_tx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_ty_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_tz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_actstatus
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: robot_mode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tool_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: work_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: abnormal_stop
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_name
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

  // Field name: prg_total_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_cur_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_output_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_input_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tl_dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tl_dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: emg
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetyboxsig
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: robot_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: grip_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripper_position
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripper_feedback_valid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: weldbreakoffstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: weldarcstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: welding_voltage
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: welding_current
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: weldtrackspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: main_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: sub_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: check_sum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: timestamp
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: version
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

  // Field name: tpd_exception
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm_reboot_robot
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: modbusmasterconnectstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: mdbsslaveconnect
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: socket_conn_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: socket_read_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: btn_box_stop_signa
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: strangeposflag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: drag_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetydoor_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetyplanealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: motionalarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: interferealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: endluaerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: dr_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: udpcmdstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: aliveslavenumerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripperfaultnum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: slavecomerror
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: cmdpointerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ioerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: grippererro
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: fileerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: paraerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: exaxis_out_slimit_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dr_com_err
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dr_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: out_sflimit_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: collision_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: weld_readystate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_web_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_tm_cmd_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_tm_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ctrlboxerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: safety_data_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: forcesensorerrstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: auxservoservoid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: auxservoerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: auxservostate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: auxservoactualpos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: auxservoctualspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: auxservoactualtorque
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: extpioinput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extpiooutput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extadcinput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extadcoutput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: reconnect_flag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: exaxiscoordid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: slave_status_1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: slave_status_2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: slave_domain_id
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: program_run_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: speed_scale_manual
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: speed_scale_auto
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
    using DataType = fairino_msgs__msg__RobotNonrtState;
    is_plain =
      (
      offsetof(DataType, speed_scale_auto) +
      last_member_size
      ) == ret_val;
  }
  return ret_val;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
bool cdr_serialize_key_fairino_msgs__msg__RobotNonrtState(
  const fairino_msgs__msg__RobotNonrtState * ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  // Field name: j1_cur_pos
  {
    cdr << ros_message->j1_cur_pos;
  }

  // Field name: j2_cur_pos
  {
    cdr << ros_message->j2_cur_pos;
  }

  // Field name: j3_cur_pos
  {
    cdr << ros_message->j3_cur_pos;
  }

  // Field name: j4_cur_pos
  {
    cdr << ros_message->j4_cur_pos;
  }

  // Field name: j5_cur_pos
  {
    cdr << ros_message->j5_cur_pos;
  }

  // Field name: j6_cur_pos
  {
    cdr << ros_message->j6_cur_pos;
  }

  // Field name: j1_cur_tor
  {
    cdr << ros_message->j1_cur_tor;
  }

  // Field name: j2_cur_tor
  {
    cdr << ros_message->j2_cur_tor;
  }

  // Field name: j3_cur_tor
  {
    cdr << ros_message->j3_cur_tor;
  }

  // Field name: j4_cur_tor
  {
    cdr << ros_message->j4_cur_tor;
  }

  // Field name: j5_cur_tor
  {
    cdr << ros_message->j5_cur_tor;
  }

  // Field name: j6_cur_tor
  {
    cdr << ros_message->j6_cur_tor;
  }

  // Field name: cart_x_cur_pos
  {
    cdr << ros_message->cart_x_cur_pos;
  }

  // Field name: cart_y_cur_pos
  {
    cdr << ros_message->cart_y_cur_pos;
  }

  // Field name: cart_z_cur_pos
  {
    cdr << ros_message->cart_z_cur_pos;
  }

  // Field name: cart_a_cur_pos
  {
    cdr << ros_message->cart_a_cur_pos;
  }

  // Field name: cart_b_cur_pos
  {
    cdr << ros_message->cart_b_cur_pos;
  }

  // Field name: cart_c_cur_pos
  {
    cdr << ros_message->cart_c_cur_pos;
  }

  // Field name: flange_x_cur_pos
  {
    cdr << ros_message->flange_x_cur_pos;
  }

  // Field name: flange_y_cur_pos
  {
    cdr << ros_message->flange_y_cur_pos;
  }

  // Field name: flange_z_cur_pos
  {
    cdr << ros_message->flange_z_cur_pos;
  }

  // Field name: flange_a_cur_pos
  {
    cdr << ros_message->flange_a_cur_pos;
  }

  // Field name: flange_b_cur_pos
  {
    cdr << ros_message->flange_b_cur_pos;
  }

  // Field name: flange_c_cur_pos
  {
    cdr << ros_message->flange_c_cur_pos;
  }

  // Field name: exaxispos1
  {
    cdr << ros_message->exaxispos1;
  }

  // Field name: exaxistatus1
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus1;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos2
  {
    cdr << ros_message->exaxispos2;
  }

  // Field name: exaxistatus2
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus2;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos3
  {
    cdr << ros_message->exaxispos3;
  }

  // Field name: exaxistatus3
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus3;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: exaxispos4
  {
    cdr << ros_message->exaxispos4;
  }

  // Field name: exaxistatus4
  {
    size_t size = 10;
    auto array_ptr = ros_message->exaxistatus4;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: ft_fx_data
  {
    cdr << ros_message->ft_fx_data;
  }

  // Field name: ft_fy_data
  {
    cdr << ros_message->ft_fy_data;
  }

  // Field name: ft_fz_data
  {
    cdr << ros_message->ft_fz_data;
  }

  // Field name: ft_tx_data
  {
    cdr << ros_message->ft_tx_data;
  }

  // Field name: ft_ty_data
  {
    cdr << ros_message->ft_ty_data;
  }

  // Field name: ft_tz_data
  {
    cdr << ros_message->ft_tz_data;
  }

  // Field name: ft_actstatus
  {
    cdr << ros_message->ft_actstatus;
  }

  // Field name: robot_mode
  {
    cdr << ros_message->robot_mode;
  }

  // Field name: tool_num
  {
    cdr << ros_message->tool_num;
  }

  // Field name: work_num
  {
    cdr << ros_message->work_num;
  }

  // Field name: prg_state
  {
    cdr << ros_message->prg_state;
  }

  // Field name: abnormal_stop
  {
    cdr << ros_message->abnormal_stop;
  }

  // Field name: prg_name
  {
    const rosidl_runtime_c__String * str = &ros_message->prg_name;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: prg_total_line
  {
    cdr << ros_message->prg_total_line;
  }

  // Field name: prg_cur_line
  {
    cdr << ros_message->prg_cur_line;
  }

  // Field name: dgt_output_h
  {
    cdr << ros_message->dgt_output_h;
  }

  // Field name: dgt_output_l
  {
    cdr << ros_message->dgt_output_l;
  }

  // Field name: dgt_input_h
  {
    cdr << ros_message->dgt_input_h;
  }

  // Field name: dgt_input_l
  {
    cdr << ros_message->dgt_input_l;
  }

  // Field name: tl_dgt_output_l
  {
    cdr << ros_message->tl_dgt_output_l;
  }

  // Field name: tl_dgt_input_l
  {
    cdr << ros_message->tl_dgt_input_l;
  }

  // Field name: emg
  {
    cdr << ros_message->emg;
  }

  // Field name: safetyboxsig
  {
    size_t size = 6;
    auto array_ptr = ros_message->safetyboxsig;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: robot_motion_done
  {
    cdr << ros_message->robot_motion_done;
  }

  // Field name: grip_motion_done
  {
    cdr << ros_message->grip_motion_done;
  }

  // Field name: gripper_position
  {
    cdr << ros_message->gripper_position;
  }

  // Field name: gripper_feedback_valid
  {
    cdr << (ros_message->gripper_feedback_valid ? true : false);
  }

  // Field name: weldbreakoffstate
  {
    cdr << ros_message->weldbreakoffstate;
  }

  // Field name: weldarcstate
  {
    cdr << ros_message->weldarcstate;
  }

  // Field name: welding_voltage
  {
    cdr << ros_message->welding_voltage;
  }

  // Field name: welding_current
  {
    cdr << ros_message->welding_current;
  }

  // Field name: weldtrackspeed
  {
    cdr << ros_message->weldtrackspeed;
  }

  // Field name: main_error_code
  {
    cdr << ros_message->main_error_code;
  }

  // Field name: sub_error_code
  {
    cdr << ros_message->sub_error_code;
  }

  // Field name: check_sum
  {
    cdr << ros_message->check_sum;
  }

  // Field name: timestamp
  {
    cdr << ros_message->timestamp;
  }

  // Field name: version
  {
    const rosidl_runtime_c__String * str = &ros_message->version;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  // Field name: tpd_exception
  {
    cdr << ros_message->tpd_exception;
  }

  // Field name: alarm_reboot_robot
  {
    cdr << ros_message->alarm_reboot_robot;
  }

  // Field name: modbusmasterconnectstate
  {
    cdr << ros_message->modbusmasterconnectstate;
  }

  // Field name: mdbsslaveconnect
  {
    cdr << ros_message->mdbsslaveconnect;
  }

  // Field name: socket_conn_timeout
  {
    cdr << ros_message->socket_conn_timeout;
  }

  // Field name: socket_read_timeout
  {
    cdr << ros_message->socket_read_timeout;
  }

  // Field name: btn_box_stop_signa
  {
    cdr << ros_message->btn_box_stop_signa;
  }

  // Field name: strangeposflag
  {
    cdr << ros_message->strangeposflag;
  }

  // Field name: drag_alarm
  {
    cdr << ros_message->drag_alarm;
  }

  // Field name: alarm
  {
    cdr << ros_message->alarm;
  }

  // Field name: safetydoor_alarm
  {
    cdr << ros_message->safetydoor_alarm;
  }

  // Field name: safetyplanealarm
  {
    cdr << ros_message->safetyplanealarm;
  }

  // Field name: motionalarm
  {
    cdr << ros_message->motionalarm;
  }

  // Field name: interferealarm
  {
    cdr << ros_message->interferealarm;
  }

  // Field name: endluaerrcode
  {
    cdr << ros_message->endluaerrcode;
  }

  // Field name: dr_alarm
  {
    cdr << ros_message->dr_alarm;
  }

  // Field name: udpcmdstate
  {
    cdr << ros_message->udpcmdstate;
  }

  // Field name: aliveslavenumerror
  {
    cdr << ros_message->aliveslavenumerror;
  }

  // Field name: gripperfaultnum
  {
    cdr << ros_message->gripperfaultnum;
  }

  // Field name: slavecomerror
  {
    size_t size = 8;
    auto array_ptr = ros_message->slavecomerror;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: cmdpointerror
  {
    cdr << ros_message->cmdpointerror;
  }

  // Field name: ioerror
  {
    cdr << ros_message->ioerror;
  }

  // Field name: grippererro
  {
    cdr << ros_message->grippererro;
  }

  // Field name: fileerror
  {
    cdr << ros_message->fileerror;
  }

  // Field name: paraerror
  {
    cdr << ros_message->paraerror;
  }

  // Field name: exaxis_out_slimit_error
  {
    cdr << ros_message->exaxis_out_slimit_error;
  }

  // Field name: dr_com_err
  {
    size_t size = 6;
    auto array_ptr = ros_message->dr_com_err;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: dr_err
  {
    cdr << ros_message->dr_err;
  }

  // Field name: out_sflimit_err
  {
    cdr << ros_message->out_sflimit_err;
  }

  // Field name: collision_err
  {
    cdr << ros_message->collision_err;
  }

  // Field name: weld_readystate
  {
    cdr << ros_message->weld_readystate;
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    cdr << ros_message->alarm_check_emerg_stop_btn;
  }

  // Field name: ts_web_state_com_error
  {
    cdr << ros_message->ts_web_state_com_error;
  }

  // Field name: ts_tm_cmd_com_error
  {
    cdr << ros_message->ts_tm_cmd_com_error;
  }

  // Field name: ts_tm_state_com_error
  {
    cdr << ros_message->ts_tm_state_com_error;
  }

  // Field name: ctrlboxerror
  {
    cdr << ros_message->ctrlboxerror;
  }

  // Field name: safety_data_state
  {
    cdr << ros_message->safety_data_state;
  }

  // Field name: forcesensorerrstate
  {
    cdr << ros_message->forcesensorerrstate;
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t size = 4;
    auto array_ptr = ros_message->ctrlopenluaerrcode;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: auxservoservoid
  {
    cdr << ros_message->auxservoservoid;
  }

  // Field name: auxservoerrcode
  {
    cdr << ros_message->auxservoerrcode;
  }

  // Field name: auxservostate
  {
    cdr << ros_message->auxservostate;
  }

  // Field name: auxservoactualpos
  {
    cdr << ros_message->auxservoactualpos;
  }

  // Field name: auxservoctualspeed
  {
    cdr << ros_message->auxservoctualspeed;
  }

  // Field name: auxservoactualtorque
  {
    cdr << ros_message->auxservoactualtorque;
  }

  // Field name: extpioinput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpioinput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extpiooutput
  {
    size_t size = 8;
    auto array_ptr = ros_message->extpiooutput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extadcinput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcinput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: extadcoutput
  {
    size_t size = 4;
    auto array_ptr = ros_message->extadcoutput;
    cdr.serialize_array(array_ptr, size);
  }

  // Field name: reconnect_flag
  {
    cdr << ros_message->reconnect_flag;
  }

  // Field name: exaxiscoordid
  {
    cdr << ros_message->exaxiscoordid;
  }

  // Field name: slave_status_1
  {
    cdr << ros_message->slave_status_1;
  }

  // Field name: slave_status_2
  {
    cdr << ros_message->slave_status_2;
  }

  // Field name: slave_domain_id
  {
    cdr << ros_message->slave_domain_id;
  }

  // Field name: program_run_state
  {
    cdr << ros_message->program_run_state;
  }

  // Field name: speed_scale_manual
  {
    cdr << ros_message->speed_scale_manual;
  }

  // Field name: speed_scale_auto
  {
    cdr << ros_message->speed_scale_auto;
  }

  return true;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
size_t get_serialized_size_key_fairino_msgs__msg__RobotNonrtState(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _RobotNonrtState__ros_msg_type * ros_message = static_cast<const _RobotNonrtState__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;

  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // Field name: j1_cur_pos
  {
    size_t item_size = sizeof(ros_message->j1_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j2_cur_pos
  {
    size_t item_size = sizeof(ros_message->j2_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j3_cur_pos
  {
    size_t item_size = sizeof(ros_message->j3_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j4_cur_pos
  {
    size_t item_size = sizeof(ros_message->j4_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j5_cur_pos
  {
    size_t item_size = sizeof(ros_message->j5_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j6_cur_pos
  {
    size_t item_size = sizeof(ros_message->j6_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j1_cur_tor
  {
    size_t item_size = sizeof(ros_message->j1_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j2_cur_tor
  {
    size_t item_size = sizeof(ros_message->j2_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j3_cur_tor
  {
    size_t item_size = sizeof(ros_message->j3_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j4_cur_tor
  {
    size_t item_size = sizeof(ros_message->j4_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j5_cur_tor
  {
    size_t item_size = sizeof(ros_message->j5_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: j6_cur_tor
  {
    size_t item_size = sizeof(ros_message->j6_cur_tor);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_x_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_y_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_z_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_a_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_b_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cart_c_cur_pos
  {
    size_t item_size = sizeof(ros_message->cart_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_x_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_x_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_y_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_y_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_z_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_z_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_a_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_a_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_b_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_b_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: flange_c_cur_pos
  {
    size_t item_size = sizeof(ros_message->flange_c_cur_pos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos1
  {
    size_t item_size = sizeof(ros_message->exaxispos1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus1
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus1;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos2
  {
    size_t item_size = sizeof(ros_message->exaxispos2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus2
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus2;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos3
  {
    size_t item_size = sizeof(ros_message->exaxispos3);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus3
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus3;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxispos4
  {
    size_t item_size = sizeof(ros_message->exaxispos4);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxistatus4
  {
    size_t array_size = 10;
    auto array_ptr = ros_message->exaxistatus4;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fx_data
  {
    size_t item_size = sizeof(ros_message->ft_fx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fy_data
  {
    size_t item_size = sizeof(ros_message->ft_fy_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_fz_data
  {
    size_t item_size = sizeof(ros_message->ft_fz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_tx_data
  {
    size_t item_size = sizeof(ros_message->ft_tx_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_ty_data
  {
    size_t item_size = sizeof(ros_message->ft_ty_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_tz_data
  {
    size_t item_size = sizeof(ros_message->ft_tz_data);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ft_actstatus
  {
    size_t item_size = sizeof(ros_message->ft_actstatus);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: robot_mode
  {
    size_t item_size = sizeof(ros_message->robot_mode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tool_num
  {
    size_t item_size = sizeof(ros_message->tool_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: work_num
  {
    size_t item_size = sizeof(ros_message->work_num);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_state
  {
    size_t item_size = sizeof(ros_message->prg_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: abnormal_stop
  {
    size_t item_size = sizeof(ros_message->abnormal_stop);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_name
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->prg_name.size + 1);

  // Field name: prg_total_line
  {
    size_t item_size = sizeof(ros_message->prg_total_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: prg_cur_line
  {
    size_t item_size = sizeof(ros_message->prg_cur_line);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_output_h
  {
    size_t item_size = sizeof(ros_message->dgt_output_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_output_l
  {
    size_t item_size = sizeof(ros_message->dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_input_h
  {
    size_t item_size = sizeof(ros_message->dgt_input_h);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dgt_input_l
  {
    size_t item_size = sizeof(ros_message->dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tl_dgt_output_l
  {
    size_t item_size = sizeof(ros_message->tl_dgt_output_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: tl_dgt_input_l
  {
    size_t item_size = sizeof(ros_message->tl_dgt_input_l);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: emg
  {
    size_t item_size = sizeof(ros_message->emg);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetyboxsig
  {
    size_t array_size = 6;
    auto array_ptr = ros_message->safetyboxsig;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: robot_motion_done
  {
    size_t item_size = sizeof(ros_message->robot_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: grip_motion_done
  {
    size_t item_size = sizeof(ros_message->grip_motion_done);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripper_position
  {
    size_t item_size = sizeof(ros_message->gripper_position);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripper_feedback_valid
  {
    size_t item_size = sizeof(ros_message->gripper_feedback_valid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldbreakoffstate
  {
    size_t item_size = sizeof(ros_message->weldbreakoffstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldarcstate
  {
    size_t item_size = sizeof(ros_message->weldarcstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: welding_voltage
  {
    size_t item_size = sizeof(ros_message->welding_voltage);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: welding_current
  {
    size_t item_size = sizeof(ros_message->welding_current);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weldtrackspeed
  {
    size_t item_size = sizeof(ros_message->weldtrackspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: main_error_code
  {
    size_t item_size = sizeof(ros_message->main_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: sub_error_code
  {
    size_t item_size = sizeof(ros_message->sub_error_code);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: check_sum
  {
    size_t item_size = sizeof(ros_message->check_sum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: timestamp
  {
    size_t item_size = sizeof(ros_message->timestamp);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: version
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->version.size + 1);

  // Field name: tpd_exception
  {
    size_t item_size = sizeof(ros_message->tpd_exception);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm_reboot_robot
  {
    size_t item_size = sizeof(ros_message->alarm_reboot_robot);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: modbusmasterconnectstate
  {
    size_t item_size = sizeof(ros_message->modbusmasterconnectstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: mdbsslaveconnect
  {
    size_t item_size = sizeof(ros_message->mdbsslaveconnect);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: socket_conn_timeout
  {
    size_t item_size = sizeof(ros_message->socket_conn_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: socket_read_timeout
  {
    size_t item_size = sizeof(ros_message->socket_read_timeout);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: btn_box_stop_signa
  {
    size_t item_size = sizeof(ros_message->btn_box_stop_signa);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: strangeposflag
  {
    size_t item_size = sizeof(ros_message->strangeposflag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: drag_alarm
  {
    size_t item_size = sizeof(ros_message->drag_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm
  {
    size_t item_size = sizeof(ros_message->alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetydoor_alarm
  {
    size_t item_size = sizeof(ros_message->safetydoor_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safetyplanealarm
  {
    size_t item_size = sizeof(ros_message->safetyplanealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: motionalarm
  {
    size_t item_size = sizeof(ros_message->motionalarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: interferealarm
  {
    size_t item_size = sizeof(ros_message->interferealarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: endluaerrcode
  {
    size_t item_size = sizeof(ros_message->endluaerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_alarm
  {
    size_t item_size = sizeof(ros_message->dr_alarm);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: udpcmdstate
  {
    size_t item_size = sizeof(ros_message->udpcmdstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: aliveslavenumerror
  {
    size_t item_size = sizeof(ros_message->aliveslavenumerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: gripperfaultnum
  {
    size_t item_size = sizeof(ros_message->gripperfaultnum);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slavecomerror
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->slavecomerror;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: cmdpointerror
  {
    size_t item_size = sizeof(ros_message->cmdpointerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ioerror
  {
    size_t item_size = sizeof(ros_message->ioerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: grippererro
  {
    size_t item_size = sizeof(ros_message->grippererro);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: fileerror
  {
    size_t item_size = sizeof(ros_message->fileerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: paraerror
  {
    size_t item_size = sizeof(ros_message->paraerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxis_out_slimit_error
  {
    size_t item_size = sizeof(ros_message->exaxis_out_slimit_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_com_err
  {
    size_t array_size = 6;
    auto array_ptr = ros_message->dr_com_err;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: dr_err
  {
    size_t item_size = sizeof(ros_message->dr_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: out_sflimit_err
  {
    size_t item_size = sizeof(ros_message->out_sflimit_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: collision_err
  {
    size_t item_size = sizeof(ros_message->collision_err);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: weld_readystate
  {
    size_t item_size = sizeof(ros_message->weld_readystate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    size_t item_size = sizeof(ros_message->alarm_check_emerg_stop_btn);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_web_state_com_error
  {
    size_t item_size = sizeof(ros_message->ts_web_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_tm_cmd_com_error
  {
    size_t item_size = sizeof(ros_message->ts_tm_cmd_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ts_tm_state_com_error
  {
    size_t item_size = sizeof(ros_message->ts_tm_state_com_error);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ctrlboxerror
  {
    size_t item_size = sizeof(ros_message->ctrlboxerror);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: safety_data_state
  {
    size_t item_size = sizeof(ros_message->safety_data_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: forcesensorerrstate
  {
    size_t item_size = sizeof(ros_message->forcesensorerrstate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->ctrlopenluaerrcode;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoservoid
  {
    size_t item_size = sizeof(ros_message->auxservoservoid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoerrcode
  {
    size_t item_size = sizeof(ros_message->auxservoerrcode);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservostate
  {
    size_t item_size = sizeof(ros_message->auxservostate);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoactualpos
  {
    size_t item_size = sizeof(ros_message->auxservoactualpos);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoctualspeed
  {
    size_t item_size = sizeof(ros_message->auxservoctualspeed);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: auxservoactualtorque
  {
    size_t item_size = sizeof(ros_message->auxservoactualtorque);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extpioinput
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->extpioinput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extpiooutput
  {
    size_t array_size = 8;
    auto array_ptr = ros_message->extpiooutput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extadcinput
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->extadcinput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: extadcoutput
  {
    size_t array_size = 4;
    auto array_ptr = ros_message->extadcoutput;
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: reconnect_flag
  {
    size_t item_size = sizeof(ros_message->reconnect_flag);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: exaxiscoordid
  {
    size_t item_size = sizeof(ros_message->exaxiscoordid);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_status_1
  {
    size_t item_size = sizeof(ros_message->slave_status_1);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_status_2
  {
    size_t item_size = sizeof(ros_message->slave_status_2);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: slave_domain_id
  {
    size_t item_size = sizeof(ros_message->slave_domain_id);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: program_run_state
  {
    size_t item_size = sizeof(ros_message->program_run_state);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: speed_scale_manual
  {
    size_t item_size = sizeof(ros_message->speed_scale_manual);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  // Field name: speed_scale_auto
  {
    size_t item_size = sizeof(ros_message->speed_scale_auto);
    current_alignment += item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }

  return current_alignment - initial_alignment;
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_fairino_msgs
size_t max_serialized_size_key_fairino_msgs__msg__RobotNonrtState(
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
  // Field name: j1_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j2_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j3_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j4_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j5_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j6_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j1_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j2_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j3_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j4_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j5_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: j6_cur_tor
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: cart_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_x_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_y_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_z_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_a_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_b_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: flange_c_cur_pos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxispos1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus1
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus2
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos3
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus3
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: exaxispos4
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: exaxistatus4
  {
    size_t array_size = 10;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: ft_fx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_fy_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_fz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_tx_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_ty_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_tz_data
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: ft_actstatus
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: robot_mode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tool_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: work_num
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: abnormal_stop
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_name
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

  // Field name: prg_total_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: prg_cur_line
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_output_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_input_h
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tl_dgt_output_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: tl_dgt_input_l
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: emg
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetyboxsig
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: robot_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: grip_motion_done
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripper_position
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripper_feedback_valid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: weldbreakoffstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: weldarcstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: welding_voltage
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: welding_current
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: weldtrackspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: main_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: sub_error_code
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: check_sum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: timestamp
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: version
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

  // Field name: tpd_exception
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm_reboot_robot
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: modbusmasterconnectstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: mdbsslaveconnect
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: socket_conn_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: socket_read_timeout
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: btn_box_stop_signa
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: strangeposflag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: drag_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetydoor_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: safetyplanealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: motionalarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: interferealarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: endluaerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: dr_alarm
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: udpcmdstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: aliveslavenumerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: gripperfaultnum
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: slavecomerror
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: cmdpointerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ioerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: grippererro
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: fileerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: paraerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: exaxis_out_slimit_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dr_com_err
  {
    size_t array_size = 6;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: dr_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: out_sflimit_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: collision_err
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: weld_readystate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: alarm_check_emerg_stop_btn
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_web_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_tm_cmd_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ts_tm_state_com_error
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ctrlboxerror
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: safety_data_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: forcesensorerrstate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: ctrlopenluaerrcode
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: auxservoservoid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: auxservoerrcode
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: auxservostate
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: auxservoactualpos
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: auxservoctualspeed
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: auxservoactualtorque
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: extpioinput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extpiooutput
  {
    size_t array_size = 8;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extadcinput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: extadcoutput
  {
    size_t array_size = 4;
    last_member_size = array_size * sizeof(uint16_t);
    current_alignment += array_size * sizeof(uint16_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint16_t));
  }

  // Field name: reconnect_flag
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: exaxiscoordid
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: slave_status_1
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: slave_status_2
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: slave_domain_id
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint32_t);
    current_alignment += array_size * sizeof(uint32_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint32_t));
  }

  // Field name: program_run_state
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint8_t);
    current_alignment += array_size * sizeof(uint8_t);
  }

  // Field name: speed_scale_manual
  {
    size_t array_size = 1;
    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }

  // Field name: speed_scale_auto
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
    using DataType = fairino_msgs__msg__RobotNonrtState;
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
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const fairino_msgs__msg__RobotNonrtState * ros_message = static_cast<const fairino_msgs__msg__RobotNonrtState *>(untyped_ros_message);
  (void)ros_message;
  return cdr_serialize_fairino_msgs__msg__RobotNonrtState(ros_message, cdr);
}

static bool _RobotNonrtState__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  fairino_msgs__msg__RobotNonrtState * ros_message = static_cast<fairino_msgs__msg__RobotNonrtState *>(untyped_ros_message);
  (void)ros_message;
  return cdr_deserialize_fairino_msgs__msg__RobotNonrtState(cdr, ros_message);
}

static uint32_t _RobotNonrtState__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_fairino_msgs__msg__RobotNonrtState(
      untyped_ros_message, 0));
}

static size_t _RobotNonrtState__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_fairino_msgs__msg__RobotNonrtState(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_RobotNonrtState = {
  "fairino_msgs::msg",
  "RobotNonrtState",
  _RobotNonrtState__cdr_serialize,
  _RobotNonrtState__cdr_deserialize,
  _RobotNonrtState__get_serialized_size,
  _RobotNonrtState__max_serialized_size,
  nullptr
};

static rosidl_message_type_support_t _RobotNonrtState__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_RobotNonrtState,
  get_message_typesupport_handle_function,
  &fairino_msgs__msg__RobotNonrtState__get_type_hash,
  &fairino_msgs__msg__RobotNonrtState__get_type_description,
  &fairino_msgs__msg__RobotNonrtState__get_type_description_sources,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, fairino_msgs, msg, RobotNonrtState)() {
  return &_RobotNonrtState__type_support;
}

#if defined(__cplusplus)
}
#endif
