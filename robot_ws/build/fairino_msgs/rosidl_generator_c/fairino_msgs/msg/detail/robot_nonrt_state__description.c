// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from fairino_msgs:msg/RobotNonrtState.idl
// generated code does not contain a copyright notice

#include "fairino_msgs/msg/detail/robot_nonrt_state__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_fairino_msgs
const rosidl_type_hash_t *
fairino_msgs__msg__RobotNonrtState__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x2f, 0xe3, 0xf7, 0x40, 0x13, 0xdd, 0xa8, 0xf0,
      0x63, 0xa6, 0xd5, 0xf0, 0x7d, 0x54, 0xbd, 0x8d,
      0x71, 0xfb, 0x83, 0xf6, 0x85, 0x9a, 0x55, 0x67,
      0x77, 0xff, 0x3f, 0x42, 0x24, 0x39, 0x77, 0xec,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types

// Hashes for external referenced types
#ifndef NDEBUG
#endif

static char fairino_msgs__msg__RobotNonrtState__TYPE_NAME[] = "fairino_msgs/msg/RobotNonrtState";

// Define type names, field names, and default values
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j1_cur_pos[] = "j1_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j2_cur_pos[] = "j2_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j3_cur_pos[] = "j3_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j4_cur_pos[] = "j4_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j5_cur_pos[] = "j5_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j6_cur_pos[] = "j6_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j1_cur_tor[] = "j1_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j2_cur_tor[] = "j2_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j3_cur_tor[] = "j3_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j4_cur_tor[] = "j4_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j5_cur_tor[] = "j5_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j6_cur_tor[] = "j6_cur_tor";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_x_cur_pos[] = "cart_x_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_y_cur_pos[] = "cart_y_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_z_cur_pos[] = "cart_z_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_a_cur_pos[] = "cart_a_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_b_cur_pos[] = "cart_b_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_c_cur_pos[] = "cart_c_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_x_cur_pos[] = "flange_x_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_y_cur_pos[] = "flange_y_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_z_cur_pos[] = "flange_z_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_a_cur_pos[] = "flange_a_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_b_cur_pos[] = "flange_b_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_c_cur_pos[] = "flange_c_cur_pos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos1[] = "exaxispos1";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus1[] = "exaxistatus1";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos2[] = "exaxispos2";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus2[] = "exaxistatus2";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos3[] = "exaxispos3";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus3[] = "exaxistatus3";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos4[] = "exaxispos4";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus4[] = "exaxistatus4";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fx_data[] = "ft_fx_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fy_data[] = "ft_fy_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fz_data[] = "ft_fz_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_tx_data[] = "ft_tx_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_ty_data[] = "ft_ty_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_tz_data[] = "ft_tz_data";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_actstatus[] = "ft_actstatus";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__robot_mode[] = "robot_mode";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tool_num[] = "tool_num";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__work_num[] = "work_num";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_state[] = "prg_state";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__abnormal_stop[] = "abnormal_stop";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_name[] = "prg_name";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_total_line[] = "prg_total_line";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_cur_line[] = "prg_cur_line";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_output_h[] = "dgt_output_h";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_output_l[] = "dgt_output_l";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_input_h[] = "dgt_input_h";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_input_l[] = "dgt_input_l";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tl_dgt_output_l[] = "tl_dgt_output_l";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tl_dgt_input_l[] = "tl_dgt_input_l";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__emg[] = "emg";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetyboxsig[] = "safetyboxsig";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__robot_motion_done[] = "robot_motion_done";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__grip_motion_done[] = "grip_motion_done";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripper_position[] = "gripper_position";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripper_feedback_valid[] = "gripper_feedback_valid";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldbreakoffstate[] = "weldbreakoffstate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldarcstate[] = "weldarcstate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__welding_voltage[] = "welding_voltage";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__welding_current[] = "welding_current";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldtrackspeed[] = "weldtrackspeed";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__main_error_code[] = "main_error_code";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__sub_error_code[] = "sub_error_code";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__check_sum[] = "check_sum";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__timestamp[] = "timestamp";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__version[] = "version";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tpd_exception[] = "tpd_exception";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm_reboot_robot[] = "alarm_reboot_robot";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__modbusmasterconnectstate[] = "modbusmasterconnectstate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__mdbsslaveconnect[] = "mdbsslaveconnect";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__socket_conn_timeout[] = "socket_conn_timeout";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__socket_read_timeout[] = "socket_read_timeout";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__btn_box_stop_signa[] = "btn_box_stop_signa";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__strangeposflag[] = "strangeposflag";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__drag_alarm[] = "drag_alarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm[] = "alarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetydoor_alarm[] = "safetydoor_alarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetyplanealarm[] = "safetyplanealarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__motionalarm[] = "motionalarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__interferealarm[] = "interferealarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__endluaerrcode[] = "endluaerrcode";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_alarm[] = "dr_alarm";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__udpcmdstate[] = "udpcmdstate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__aliveslavenumerror[] = "aliveslavenumerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripperfaultnum[] = "gripperfaultnum";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slavecomerror[] = "slavecomerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cmdpointerror[] = "cmdpointerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ioerror[] = "ioerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__grippererro[] = "grippererro";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__fileerror[] = "fileerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__paraerror[] = "paraerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxis_out_slimit_error[] = "exaxis_out_slimit_error";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_com_err[] = "dr_com_err";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_err[] = "dr_err";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__out_sflimit_err[] = "out_sflimit_err";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__collision_err[] = "collision_err";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weld_readystate[] = "weld_readystate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm_check_emerg_stop_btn[] = "alarm_check_emerg_stop_btn";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_web_state_com_error[] = "ts_web_state_com_error";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_tm_cmd_com_error[] = "ts_tm_cmd_com_error";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_tm_state_com_error[] = "ts_tm_state_com_error";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ctrlboxerror[] = "ctrlboxerror";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safety_data_state[] = "safety_data_state";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__forcesensorerrstate[] = "forcesensorerrstate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ctrlopenluaerrcode[] = "ctrlopenluaerrcode";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoservoid[] = "auxservoservoid";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoerrcode[] = "auxservoerrcode";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservostate[] = "auxservostate";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoactualpos[] = "auxservoactualpos";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoctualspeed[] = "auxservoctualspeed";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoactualtorque[] = "auxservoactualtorque";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extpioinput[] = "extpioinput";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extpiooutput[] = "extpiooutput";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extadcinput[] = "extadcinput";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extadcoutput[] = "extadcoutput";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__reconnect_flag[] = "reconnect_flag";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxiscoordid[] = "exaxiscoordid";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_status_1[] = "slave_status_1";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_status_2[] = "slave_status_2";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_domain_id[] = "slave_domain_id";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__program_run_state[] = "program_run_state";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__speed_scale_manual[] = "speed_scale_manual";
static char fairino_msgs__msg__RobotNonrtState__FIELD_NAME__speed_scale_auto[] = "speed_scale_auto";

static rosidl_runtime_c__type_description__Field fairino_msgs__msg__RobotNonrtState__FIELDS[] = {
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j1_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j2_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j3_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j4_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j5_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j6_cur_pos, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j1_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j2_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j3_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j4_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j5_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__j6_cur_tor, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_x_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_y_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_z_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_a_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_b_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cart_c_cur_pos, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_x_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_y_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_z_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_a_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_b_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__flange_c_cur_pos, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos1, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus1, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32_ARRAY,
      10,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos2, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus2, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32_ARRAY,
      10,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos3, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus3, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32_ARRAY,
      10,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxispos4, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxistatus4, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32_ARRAY,
      10,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fx_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fy_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_fz_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_tx_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_ty_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_tz_data, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ft_actstatus, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__robot_mode, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tool_num, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__work_num, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_state, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__abnormal_stop, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_name, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_total_line, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__prg_cur_line, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_output_h, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_output_l, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_input_h, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dgt_input_l, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tl_dgt_output_l, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tl_dgt_input_l, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__emg, 3, 3},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetyboxsig, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8_ARRAY,
      6,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__robot_motion_done, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__grip_motion_done, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripper_position, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripper_feedback_valid, 22, 22},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldbreakoffstate, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldarcstate, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__welding_voltage, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__welding_current, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weldtrackspeed, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__main_error_code, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__sub_error_code, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__check_sum, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__timestamp, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT64,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__version, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__tpd_exception, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm_reboot_robot, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__modbusmasterconnectstate, 24, 24},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__mdbsslaveconnect, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__socket_conn_timeout, 19, 19},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__socket_read_timeout, 19, 19},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__btn_box_stop_signa, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__strangeposflag, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__drag_alarm, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetydoor_alarm, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safetyplanealarm, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__motionalarm, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__interferealarm, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__endluaerrcode, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_alarm, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__udpcmdstate, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__aliveslavenumerror, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__gripperfaultnum, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slavecomerror, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8_ARRAY,
      8,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__cmdpointerror, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ioerror, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__grippererro, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__fileerror, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__paraerror, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxis_out_slimit_error, 23, 23},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_com_err, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8_ARRAY,
      6,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__dr_err, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__out_sflimit_err, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__collision_err, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__weld_readystate, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__alarm_check_emerg_stop_btn, 26, 26},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_web_state_com_error, 22, 22},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_tm_cmd_com_error, 19, 19},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ts_tm_state_com_error, 21, 21},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ctrlboxerror, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__safety_data_state, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__forcesensorerrstate, 19, 19},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__ctrlopenluaerrcode, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8_ARRAY,
      4,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoservoid, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoerrcode, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservostate, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoactualpos, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoctualspeed, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__auxservoactualtorque, 20, 20},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extpioinput, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16_ARRAY,
      8,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extpiooutput, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16_ARRAY,
      8,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extadcinput, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16_ARRAY,
      4,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__extadcoutput, 12, 12},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT16_ARRAY,
      4,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__reconnect_flag, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__exaxiscoordid, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_status_1, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_status_2, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__slave_domain_id, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__program_run_state, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT8,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__speed_scale_manual, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {fairino_msgs__msg__RobotNonrtState__FIELD_NAME__speed_scale_auto, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
fairino_msgs__msg__RobotNonrtState__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {fairino_msgs__msg__RobotNonrtState__TYPE_NAME, 32, 32},
      {fairino_msgs__msg__RobotNonrtState__FIELDS, 126, 126},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "#V3.0.5\n"
  "float64 j1_cur_pos\n"
  "float64 j2_cur_pos\n"
  "float64 j3_cur_pos\n"
  "float64 j4_cur_pos\n"
  "float64 j5_cur_pos\n"
  "float64 j6_cur_pos\n"
  "float64 j1_cur_tor\n"
  "float64 j2_cur_tor\n"
  "float64 j3_cur_tor\n"
  "float64 j4_cur_tor\n"
  "float64 j5_cur_tor\n"
  "float64 j6_cur_tor\n"
  "float64 cart_x_cur_pos\n"
  "float64 cart_y_cur_pos\n"
  "float64 cart_z_cur_pos\n"
  "float64 cart_a_cur_pos\n"
  "float64 cart_b_cur_pos\n"
  "float64 cart_c_cur_pos\n"
  "float64 flange_x_cur_pos\n"
  "float64 flange_y_cur_pos\n"
  "float64 flange_z_cur_pos\n"
  "float64 flange_a_cur_pos\n"
  "float64 flange_b_cur_pos\n"
  "float64 flange_c_cur_pos\n"
  "float64 exaxispos1\n"
  "int32[10] exaxistatus1\n"
  "float64 exaxispos2\n"
  "int32[10] exaxistatus2\n"
  "float64 exaxispos3\n"
  "int32[10] exaxistatus3\n"
  "float64 exaxispos4\n"
  "int32[10] exaxistatus4\n"
  "float64 ft_fx_data\n"
  "float64 ft_fy_data\n"
  "float64 ft_fz_data\n"
  "float64 ft_tx_data\n"
  "float64 ft_ty_data\n"
  "float64 ft_tz_data\n"
  "uint8 ft_actstatus\n"
  "uint8 robot_mode\n"
  "uint8 tool_num\n"
  "uint8 work_num\n"
  "uint8 prg_state\n"
  "uint8 abnormal_stop\n"
  "string prg_name\n"
  "uint8 prg_total_line\n"
  "uint8 prg_cur_line\n"
  "uint8 dgt_output_h\n"
  "uint8 dgt_output_l\n"
  "uint8 dgt_input_h\n"
  "uint8 dgt_input_l\n"
  "uint8 tl_dgt_output_l\n"
  "uint8 tl_dgt_input_l\n"
  "uint8 emg\n"
  "uint8[6] safetyboxsig #V2.1 added\n"
  "uint8 robot_motion_done\n"
  "uint8 grip_motion_done\n"
  "uint8 gripper_position\n"
  "bool gripper_feedback_valid\n"
  "uint8 weldbreakoffstate\n"
  "uint8 weldarcstate\n"
  "float64 welding_voltage\n"
  "float64 welding_current\n"
  "float64 weldtrackspeed\n"
  "uint32 main_error_code\n"
  "uint32 sub_error_code\n"
  "uint8 check_sum\n"
  "uint64 timestamp\n"
  "string version\n"
  "uint8 tpd_exception\n"
  "uint8 alarm_reboot_robot\n"
  "uint8 modbusmasterconnectstate\n"
  "uint8 mdbsslaveconnect\n"
  "uint8 socket_conn_timeout\n"
  "uint8 socket_read_timeout\n"
  "uint8 btn_box_stop_signa\n"
  "uint8 strangeposflag\n"
  "uint8 drag_alarm\n"
  "uint8 alarm\n"
  "uint8 safetydoor_alarm\n"
  "uint8 safetyplanealarm\n"
  "uint8 motionalarm\n"
  "uint8 interferealarm\n"
  "uint16 endluaerrcode\n"
  "float64 dr_alarm\n"
  "uint16 udpcmdstate\n"
  "uint8 aliveslavenumerror\n"
  "uint16 gripperfaultnum\n"
  "uint8[8] slavecomerror\n"
  "uint8 cmdpointerror\n"
  "uint8 ioerror\n"
  "uint8 grippererro\n"
  "uint8 fileerror\n"
  "uint8 paraerror\n"
  "uint8 exaxis_out_slimit_error\n"
  "uint8[6] dr_com_err\n"
  "float64 dr_err\n"
  "float64 out_sflimit_err\n"
  "float64 collision_err\n"
  "uint8 weld_readystate\n"
  "uint8 alarm_check_emerg_stop_btn\n"
  "uint8 ts_web_state_com_error\n"
  "uint8 ts_tm_cmd_com_error\n"
  "uint8 ts_tm_state_com_error\n"
  "uint16 ctrlboxerror\n"
  "uint8 safety_data_state\n"
  "uint8 forcesensorerrstate\n"
  "uint8[4] ctrlopenluaerrcode\n"
  "uint8 auxservoservoid\n"
  "int32 auxservoerrcode\n"
  "int32 auxservostate\n"
  "float64 auxservoactualpos\n"
  "float64 auxservoctualspeed\n"
  "float64 auxservoactualtorque\n"
  "uint16[8] extpioinput\n"
  "uint16[8] extpiooutput\n"
  "uint16[4] extadcinput\n"
  "uint16[4] extadcoutput\n"
  "uint8 reconnect_flag\n"
  "uint8 exaxiscoordid\n"
  "float64 slave_status_1\n"
  "float64 slave_status_2\n"
  "int32 slave_domain_id\n"
  "uint8 program_run_state\n"
  "float64 speed_scale_manual\n"
  "float64 speed_scale_auto";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
fairino_msgs__msg__RobotNonrtState__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {fairino_msgs__msg__RobotNonrtState__TYPE_NAME, 32, 32},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 2720, 2720},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
fairino_msgs__msg__RobotNonrtState__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *fairino_msgs__msg__RobotNonrtState__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}
