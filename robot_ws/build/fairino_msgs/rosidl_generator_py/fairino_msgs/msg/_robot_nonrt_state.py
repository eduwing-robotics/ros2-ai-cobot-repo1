# generated from rosidl_generator_py/resource/_idl.py.em
# with input from fairino_msgs:msg/RobotNonrtState.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import math  # noqa: E402, I100

# Member 'exaxistatus1'
# Member 'exaxistatus2'
# Member 'exaxistatus3'
# Member 'exaxistatus4'
# Member 'safetyboxsig'
# Member 'slavecomerror'
# Member 'dr_com_err'
# Member 'ctrlopenluaerrcode'
# Member 'extpioinput'
# Member 'extpiooutput'
# Member 'extadcinput'
# Member 'extadcoutput'
import numpy  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_RobotNonrtState(type):
    """Metaclass of message 'RobotNonrtState'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('fairino_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'fairino_msgs.msg.RobotNonrtState')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__robot_nonrt_state
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__robot_nonrt_state
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__robot_nonrt_state
            cls._TYPE_SUPPORT = module.type_support_msg__msg__robot_nonrt_state
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__robot_nonrt_state

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class RobotNonrtState(metaclass=Metaclass_RobotNonrtState):
    """Message class 'RobotNonrtState'."""

    __slots__ = [
        '_j1_cur_pos',
        '_j2_cur_pos',
        '_j3_cur_pos',
        '_j4_cur_pos',
        '_j5_cur_pos',
        '_j6_cur_pos',
        '_j1_cur_tor',
        '_j2_cur_tor',
        '_j3_cur_tor',
        '_j4_cur_tor',
        '_j5_cur_tor',
        '_j6_cur_tor',
        '_cart_x_cur_pos',
        '_cart_y_cur_pos',
        '_cart_z_cur_pos',
        '_cart_a_cur_pos',
        '_cart_b_cur_pos',
        '_cart_c_cur_pos',
        '_flange_x_cur_pos',
        '_flange_y_cur_pos',
        '_flange_z_cur_pos',
        '_flange_a_cur_pos',
        '_flange_b_cur_pos',
        '_flange_c_cur_pos',
        '_exaxispos1',
        '_exaxistatus1',
        '_exaxispos2',
        '_exaxistatus2',
        '_exaxispos3',
        '_exaxistatus3',
        '_exaxispos4',
        '_exaxistatus4',
        '_ft_fx_data',
        '_ft_fy_data',
        '_ft_fz_data',
        '_ft_tx_data',
        '_ft_ty_data',
        '_ft_tz_data',
        '_ft_actstatus',
        '_robot_mode',
        '_tool_num',
        '_work_num',
        '_prg_state',
        '_abnormal_stop',
        '_prg_name',
        '_prg_total_line',
        '_prg_cur_line',
        '_dgt_output_h',
        '_dgt_output_l',
        '_dgt_input_h',
        '_dgt_input_l',
        '_tl_dgt_output_l',
        '_tl_dgt_input_l',
        '_emg',
        '_safetyboxsig',
        '_robot_motion_done',
        '_grip_motion_done',
        '_gripper_position',
        '_gripper_feedback_valid',
        '_weldbreakoffstate',
        '_weldarcstate',
        '_welding_voltage',
        '_welding_current',
        '_weldtrackspeed',
        '_main_error_code',
        '_sub_error_code',
        '_check_sum',
        '_timestamp',
        '_version',
        '_tpd_exception',
        '_alarm_reboot_robot',
        '_modbusmasterconnectstate',
        '_mdbsslaveconnect',
        '_socket_conn_timeout',
        '_socket_read_timeout',
        '_btn_box_stop_signa',
        '_strangeposflag',
        '_drag_alarm',
        '_alarm',
        '_safetydoor_alarm',
        '_safetyplanealarm',
        '_motionalarm',
        '_interferealarm',
        '_endluaerrcode',
        '_dr_alarm',
        '_udpcmdstate',
        '_aliveslavenumerror',
        '_gripperfaultnum',
        '_slavecomerror',
        '_cmdpointerror',
        '_ioerror',
        '_grippererro',
        '_fileerror',
        '_paraerror',
        '_exaxis_out_slimit_error',
        '_dr_com_err',
        '_dr_err',
        '_out_sflimit_err',
        '_collision_err',
        '_weld_readystate',
        '_alarm_check_emerg_stop_btn',
        '_ts_web_state_com_error',
        '_ts_tm_cmd_com_error',
        '_ts_tm_state_com_error',
        '_ctrlboxerror',
        '_safety_data_state',
        '_forcesensorerrstate',
        '_ctrlopenluaerrcode',
        '_auxservoservoid',
        '_auxservoerrcode',
        '_auxservostate',
        '_auxservoactualpos',
        '_auxservoctualspeed',
        '_auxservoactualtorque',
        '_extpioinput',
        '_extpiooutput',
        '_extadcinput',
        '_extadcoutput',
        '_reconnect_flag',
        '_exaxiscoordid',
        '_slave_status_1',
        '_slave_status_2',
        '_slave_domain_id',
        '_program_run_state',
        '_speed_scale_manual',
        '_speed_scale_auto',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'j1_cur_pos': 'double',
        'j2_cur_pos': 'double',
        'j3_cur_pos': 'double',
        'j4_cur_pos': 'double',
        'j5_cur_pos': 'double',
        'j6_cur_pos': 'double',
        'j1_cur_tor': 'double',
        'j2_cur_tor': 'double',
        'j3_cur_tor': 'double',
        'j4_cur_tor': 'double',
        'j5_cur_tor': 'double',
        'j6_cur_tor': 'double',
        'cart_x_cur_pos': 'double',
        'cart_y_cur_pos': 'double',
        'cart_z_cur_pos': 'double',
        'cart_a_cur_pos': 'double',
        'cart_b_cur_pos': 'double',
        'cart_c_cur_pos': 'double',
        'flange_x_cur_pos': 'double',
        'flange_y_cur_pos': 'double',
        'flange_z_cur_pos': 'double',
        'flange_a_cur_pos': 'double',
        'flange_b_cur_pos': 'double',
        'flange_c_cur_pos': 'double',
        'exaxispos1': 'double',
        'exaxistatus1': 'int32[10]',
        'exaxispos2': 'double',
        'exaxistatus2': 'int32[10]',
        'exaxispos3': 'double',
        'exaxistatus3': 'int32[10]',
        'exaxispos4': 'double',
        'exaxistatus4': 'int32[10]',
        'ft_fx_data': 'double',
        'ft_fy_data': 'double',
        'ft_fz_data': 'double',
        'ft_tx_data': 'double',
        'ft_ty_data': 'double',
        'ft_tz_data': 'double',
        'ft_actstatus': 'uint8',
        'robot_mode': 'uint8',
        'tool_num': 'uint8',
        'work_num': 'uint8',
        'prg_state': 'uint8',
        'abnormal_stop': 'uint8',
        'prg_name': 'string',
        'prg_total_line': 'uint8',
        'prg_cur_line': 'uint8',
        'dgt_output_h': 'uint8',
        'dgt_output_l': 'uint8',
        'dgt_input_h': 'uint8',
        'dgt_input_l': 'uint8',
        'tl_dgt_output_l': 'uint8',
        'tl_dgt_input_l': 'uint8',
        'emg': 'uint8',
        'safetyboxsig': 'uint8[6]',
        'robot_motion_done': 'uint8',
        'grip_motion_done': 'uint8',
        'gripper_position': 'uint8',
        'gripper_feedback_valid': 'boolean',
        'weldbreakoffstate': 'uint8',
        'weldarcstate': 'uint8',
        'welding_voltage': 'double',
        'welding_current': 'double',
        'weldtrackspeed': 'double',
        'main_error_code': 'uint32',
        'sub_error_code': 'uint32',
        'check_sum': 'uint8',
        'timestamp': 'uint64',
        'version': 'string',
        'tpd_exception': 'uint8',
        'alarm_reboot_robot': 'uint8',
        'modbusmasterconnectstate': 'uint8',
        'mdbsslaveconnect': 'uint8',
        'socket_conn_timeout': 'uint8',
        'socket_read_timeout': 'uint8',
        'btn_box_stop_signa': 'uint8',
        'strangeposflag': 'uint8',
        'drag_alarm': 'uint8',
        'alarm': 'uint8',
        'safetydoor_alarm': 'uint8',
        'safetyplanealarm': 'uint8',
        'motionalarm': 'uint8',
        'interferealarm': 'uint8',
        'endluaerrcode': 'uint16',
        'dr_alarm': 'double',
        'udpcmdstate': 'uint16',
        'aliveslavenumerror': 'uint8',
        'gripperfaultnum': 'uint16',
        'slavecomerror': 'uint8[8]',
        'cmdpointerror': 'uint8',
        'ioerror': 'uint8',
        'grippererro': 'uint8',
        'fileerror': 'uint8',
        'paraerror': 'uint8',
        'exaxis_out_slimit_error': 'uint8',
        'dr_com_err': 'uint8[6]',
        'dr_err': 'double',
        'out_sflimit_err': 'double',
        'collision_err': 'double',
        'weld_readystate': 'uint8',
        'alarm_check_emerg_stop_btn': 'uint8',
        'ts_web_state_com_error': 'uint8',
        'ts_tm_cmd_com_error': 'uint8',
        'ts_tm_state_com_error': 'uint8',
        'ctrlboxerror': 'uint16',
        'safety_data_state': 'uint8',
        'forcesensorerrstate': 'uint8',
        'ctrlopenluaerrcode': 'uint8[4]',
        'auxservoservoid': 'uint8',
        'auxservoerrcode': 'int32',
        'auxservostate': 'int32',
        'auxservoactualpos': 'double',
        'auxservoctualspeed': 'double',
        'auxservoactualtorque': 'double',
        'extpioinput': 'uint16[8]',
        'extpiooutput': 'uint16[8]',
        'extadcinput': 'uint16[4]',
        'extadcoutput': 'uint16[4]',
        'reconnect_flag': 'uint8',
        'exaxiscoordid': 'uint8',
        'slave_status_1': 'double',
        'slave_status_2': 'double',
        'slave_domain_id': 'int32',
        'program_run_state': 'uint8',
        'speed_scale_manual': 'double',
        'speed_scale_auto': 'double',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('int32'), 10),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('int32'), 10),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('int32'), 10),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('int32'), 10),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint8'), 6),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint32'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint32'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint64'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint16'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint16'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint16'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint8'), 8),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint8'), 6),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint16'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint8'), 4),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint16'), 8),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint16'), 8),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint16'), 4),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('uint16'), 4),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
    )

    def __init__(self, **kwargs):
        if 'check_fields' in kwargs:
            self._check_fields = kwargs['check_fields']
        else:
            self._check_fields = ros_python_check_fields == '1'
        if self._check_fields:
            assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
                'Invalid arguments passed to constructor: %s' % \
                ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.j1_cur_pos = kwargs.get('j1_cur_pos', float())
        self.j2_cur_pos = kwargs.get('j2_cur_pos', float())
        self.j3_cur_pos = kwargs.get('j3_cur_pos', float())
        self.j4_cur_pos = kwargs.get('j4_cur_pos', float())
        self.j5_cur_pos = kwargs.get('j5_cur_pos', float())
        self.j6_cur_pos = kwargs.get('j6_cur_pos', float())
        self.j1_cur_tor = kwargs.get('j1_cur_tor', float())
        self.j2_cur_tor = kwargs.get('j2_cur_tor', float())
        self.j3_cur_tor = kwargs.get('j3_cur_tor', float())
        self.j4_cur_tor = kwargs.get('j4_cur_tor', float())
        self.j5_cur_tor = kwargs.get('j5_cur_tor', float())
        self.j6_cur_tor = kwargs.get('j6_cur_tor', float())
        self.cart_x_cur_pos = kwargs.get('cart_x_cur_pos', float())
        self.cart_y_cur_pos = kwargs.get('cart_y_cur_pos', float())
        self.cart_z_cur_pos = kwargs.get('cart_z_cur_pos', float())
        self.cart_a_cur_pos = kwargs.get('cart_a_cur_pos', float())
        self.cart_b_cur_pos = kwargs.get('cart_b_cur_pos', float())
        self.cart_c_cur_pos = kwargs.get('cart_c_cur_pos', float())
        self.flange_x_cur_pos = kwargs.get('flange_x_cur_pos', float())
        self.flange_y_cur_pos = kwargs.get('flange_y_cur_pos', float())
        self.flange_z_cur_pos = kwargs.get('flange_z_cur_pos', float())
        self.flange_a_cur_pos = kwargs.get('flange_a_cur_pos', float())
        self.flange_b_cur_pos = kwargs.get('flange_b_cur_pos', float())
        self.flange_c_cur_pos = kwargs.get('flange_c_cur_pos', float())
        self.exaxispos1 = kwargs.get('exaxispos1', float())
        if 'exaxistatus1' not in kwargs:
            self.exaxistatus1 = numpy.zeros(10, dtype=numpy.int32)
        else:
            self.exaxistatus1 = kwargs.get('exaxistatus1')
        self.exaxispos2 = kwargs.get('exaxispos2', float())
        if 'exaxistatus2' not in kwargs:
            self.exaxistatus2 = numpy.zeros(10, dtype=numpy.int32)
        else:
            self.exaxistatus2 = kwargs.get('exaxistatus2')
        self.exaxispos3 = kwargs.get('exaxispos3', float())
        if 'exaxistatus3' not in kwargs:
            self.exaxistatus3 = numpy.zeros(10, dtype=numpy.int32)
        else:
            self.exaxistatus3 = kwargs.get('exaxistatus3')
        self.exaxispos4 = kwargs.get('exaxispos4', float())
        if 'exaxistatus4' not in kwargs:
            self.exaxistatus4 = numpy.zeros(10, dtype=numpy.int32)
        else:
            self.exaxistatus4 = kwargs.get('exaxistatus4')
        self.ft_fx_data = kwargs.get('ft_fx_data', float())
        self.ft_fy_data = kwargs.get('ft_fy_data', float())
        self.ft_fz_data = kwargs.get('ft_fz_data', float())
        self.ft_tx_data = kwargs.get('ft_tx_data', float())
        self.ft_ty_data = kwargs.get('ft_ty_data', float())
        self.ft_tz_data = kwargs.get('ft_tz_data', float())
        self.ft_actstatus = kwargs.get('ft_actstatus', int())
        self.robot_mode = kwargs.get('robot_mode', int())
        self.tool_num = kwargs.get('tool_num', int())
        self.work_num = kwargs.get('work_num', int())
        self.prg_state = kwargs.get('prg_state', int())
        self.abnormal_stop = kwargs.get('abnormal_stop', int())
        self.prg_name = kwargs.get('prg_name', str())
        self.prg_total_line = kwargs.get('prg_total_line', int())
        self.prg_cur_line = kwargs.get('prg_cur_line', int())
        self.dgt_output_h = kwargs.get('dgt_output_h', int())
        self.dgt_output_l = kwargs.get('dgt_output_l', int())
        self.dgt_input_h = kwargs.get('dgt_input_h', int())
        self.dgt_input_l = kwargs.get('dgt_input_l', int())
        self.tl_dgt_output_l = kwargs.get('tl_dgt_output_l', int())
        self.tl_dgt_input_l = kwargs.get('tl_dgt_input_l', int())
        self.emg = kwargs.get('emg', int())
        if 'safetyboxsig' not in kwargs:
            self.safetyboxsig = numpy.zeros(6, dtype=numpy.uint8)
        else:
            self.safetyboxsig = kwargs.get('safetyboxsig')
        self.robot_motion_done = kwargs.get('robot_motion_done', int())
        self.grip_motion_done = kwargs.get('grip_motion_done', int())
        self.gripper_position = kwargs.get('gripper_position', int())
        self.gripper_feedback_valid = kwargs.get('gripper_feedback_valid', bool())
        self.weldbreakoffstate = kwargs.get('weldbreakoffstate', int())
        self.weldarcstate = kwargs.get('weldarcstate', int())
        self.welding_voltage = kwargs.get('welding_voltage', float())
        self.welding_current = kwargs.get('welding_current', float())
        self.weldtrackspeed = kwargs.get('weldtrackspeed', float())
        self.main_error_code = kwargs.get('main_error_code', int())
        self.sub_error_code = kwargs.get('sub_error_code', int())
        self.check_sum = kwargs.get('check_sum', int())
        self.timestamp = kwargs.get('timestamp', int())
        self.version = kwargs.get('version', str())
        self.tpd_exception = kwargs.get('tpd_exception', int())
        self.alarm_reboot_robot = kwargs.get('alarm_reboot_robot', int())
        self.modbusmasterconnectstate = kwargs.get('modbusmasterconnectstate', int())
        self.mdbsslaveconnect = kwargs.get('mdbsslaveconnect', int())
        self.socket_conn_timeout = kwargs.get('socket_conn_timeout', int())
        self.socket_read_timeout = kwargs.get('socket_read_timeout', int())
        self.btn_box_stop_signa = kwargs.get('btn_box_stop_signa', int())
        self.strangeposflag = kwargs.get('strangeposflag', int())
        self.drag_alarm = kwargs.get('drag_alarm', int())
        self.alarm = kwargs.get('alarm', int())
        self.safetydoor_alarm = kwargs.get('safetydoor_alarm', int())
        self.safetyplanealarm = kwargs.get('safetyplanealarm', int())
        self.motionalarm = kwargs.get('motionalarm', int())
        self.interferealarm = kwargs.get('interferealarm', int())
        self.endluaerrcode = kwargs.get('endluaerrcode', int())
        self.dr_alarm = kwargs.get('dr_alarm', float())
        self.udpcmdstate = kwargs.get('udpcmdstate', int())
        self.aliveslavenumerror = kwargs.get('aliveslavenumerror', int())
        self.gripperfaultnum = kwargs.get('gripperfaultnum', int())
        if 'slavecomerror' not in kwargs:
            self.slavecomerror = numpy.zeros(8, dtype=numpy.uint8)
        else:
            self.slavecomerror = kwargs.get('slavecomerror')
        self.cmdpointerror = kwargs.get('cmdpointerror', int())
        self.ioerror = kwargs.get('ioerror', int())
        self.grippererro = kwargs.get('grippererro', int())
        self.fileerror = kwargs.get('fileerror', int())
        self.paraerror = kwargs.get('paraerror', int())
        self.exaxis_out_slimit_error = kwargs.get('exaxis_out_slimit_error', int())
        if 'dr_com_err' not in kwargs:
            self.dr_com_err = numpy.zeros(6, dtype=numpy.uint8)
        else:
            self.dr_com_err = kwargs.get('dr_com_err')
        self.dr_err = kwargs.get('dr_err', float())
        self.out_sflimit_err = kwargs.get('out_sflimit_err', float())
        self.collision_err = kwargs.get('collision_err', float())
        self.weld_readystate = kwargs.get('weld_readystate', int())
        self.alarm_check_emerg_stop_btn = kwargs.get('alarm_check_emerg_stop_btn', int())
        self.ts_web_state_com_error = kwargs.get('ts_web_state_com_error', int())
        self.ts_tm_cmd_com_error = kwargs.get('ts_tm_cmd_com_error', int())
        self.ts_tm_state_com_error = kwargs.get('ts_tm_state_com_error', int())
        self.ctrlboxerror = kwargs.get('ctrlboxerror', int())
        self.safety_data_state = kwargs.get('safety_data_state', int())
        self.forcesensorerrstate = kwargs.get('forcesensorerrstate', int())
        if 'ctrlopenluaerrcode' not in kwargs:
            self.ctrlopenluaerrcode = numpy.zeros(4, dtype=numpy.uint8)
        else:
            self.ctrlopenluaerrcode = kwargs.get('ctrlopenluaerrcode')
        self.auxservoservoid = kwargs.get('auxservoservoid', int())
        self.auxservoerrcode = kwargs.get('auxservoerrcode', int())
        self.auxservostate = kwargs.get('auxservostate', int())
        self.auxservoactualpos = kwargs.get('auxservoactualpos', float())
        self.auxservoctualspeed = kwargs.get('auxservoctualspeed', float())
        self.auxservoactualtorque = kwargs.get('auxservoactualtorque', float())
        if 'extpioinput' not in kwargs:
            self.extpioinput = numpy.zeros(8, dtype=numpy.uint16)
        else:
            self.extpioinput = kwargs.get('extpioinput')
        if 'extpiooutput' not in kwargs:
            self.extpiooutput = numpy.zeros(8, dtype=numpy.uint16)
        else:
            self.extpiooutput = kwargs.get('extpiooutput')
        if 'extadcinput' not in kwargs:
            self.extadcinput = numpy.zeros(4, dtype=numpy.uint16)
        else:
            self.extadcinput = kwargs.get('extadcinput')
        if 'extadcoutput' not in kwargs:
            self.extadcoutput = numpy.zeros(4, dtype=numpy.uint16)
        else:
            self.extadcoutput = kwargs.get('extadcoutput')
        self.reconnect_flag = kwargs.get('reconnect_flag', int())
        self.exaxiscoordid = kwargs.get('exaxiscoordid', int())
        self.slave_status_1 = kwargs.get('slave_status_1', float())
        self.slave_status_2 = kwargs.get('slave_status_2', float())
        self.slave_domain_id = kwargs.get('slave_domain_id', int())
        self.program_run_state = kwargs.get('program_run_state', int())
        self.speed_scale_manual = kwargs.get('speed_scale_manual', float())
        self.speed_scale_auto = kwargs.get('speed_scale_auto', float())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.get_fields_and_field_types().keys(), self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    if self._check_fields:
                        assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.j1_cur_pos != other.j1_cur_pos:
            return False
        if self.j2_cur_pos != other.j2_cur_pos:
            return False
        if self.j3_cur_pos != other.j3_cur_pos:
            return False
        if self.j4_cur_pos != other.j4_cur_pos:
            return False
        if self.j5_cur_pos != other.j5_cur_pos:
            return False
        if self.j6_cur_pos != other.j6_cur_pos:
            return False
        if self.j1_cur_tor != other.j1_cur_tor:
            return False
        if self.j2_cur_tor != other.j2_cur_tor:
            return False
        if self.j3_cur_tor != other.j3_cur_tor:
            return False
        if self.j4_cur_tor != other.j4_cur_tor:
            return False
        if self.j5_cur_tor != other.j5_cur_tor:
            return False
        if self.j6_cur_tor != other.j6_cur_tor:
            return False
        if self.cart_x_cur_pos != other.cart_x_cur_pos:
            return False
        if self.cart_y_cur_pos != other.cart_y_cur_pos:
            return False
        if self.cart_z_cur_pos != other.cart_z_cur_pos:
            return False
        if self.cart_a_cur_pos != other.cart_a_cur_pos:
            return False
        if self.cart_b_cur_pos != other.cart_b_cur_pos:
            return False
        if self.cart_c_cur_pos != other.cart_c_cur_pos:
            return False
        if self.flange_x_cur_pos != other.flange_x_cur_pos:
            return False
        if self.flange_y_cur_pos != other.flange_y_cur_pos:
            return False
        if self.flange_z_cur_pos != other.flange_z_cur_pos:
            return False
        if self.flange_a_cur_pos != other.flange_a_cur_pos:
            return False
        if self.flange_b_cur_pos != other.flange_b_cur_pos:
            return False
        if self.flange_c_cur_pos != other.flange_c_cur_pos:
            return False
        if self.exaxispos1 != other.exaxispos1:
            return False
        if any(self.exaxistatus1 != other.exaxistatus1):
            return False
        if self.exaxispos2 != other.exaxispos2:
            return False
        if any(self.exaxistatus2 != other.exaxistatus2):
            return False
        if self.exaxispos3 != other.exaxispos3:
            return False
        if any(self.exaxistatus3 != other.exaxistatus3):
            return False
        if self.exaxispos4 != other.exaxispos4:
            return False
        if any(self.exaxistatus4 != other.exaxistatus4):
            return False
        if self.ft_fx_data != other.ft_fx_data:
            return False
        if self.ft_fy_data != other.ft_fy_data:
            return False
        if self.ft_fz_data != other.ft_fz_data:
            return False
        if self.ft_tx_data != other.ft_tx_data:
            return False
        if self.ft_ty_data != other.ft_ty_data:
            return False
        if self.ft_tz_data != other.ft_tz_data:
            return False
        if self.ft_actstatus != other.ft_actstatus:
            return False
        if self.robot_mode != other.robot_mode:
            return False
        if self.tool_num != other.tool_num:
            return False
        if self.work_num != other.work_num:
            return False
        if self.prg_state != other.prg_state:
            return False
        if self.abnormal_stop != other.abnormal_stop:
            return False
        if self.prg_name != other.prg_name:
            return False
        if self.prg_total_line != other.prg_total_line:
            return False
        if self.prg_cur_line != other.prg_cur_line:
            return False
        if self.dgt_output_h != other.dgt_output_h:
            return False
        if self.dgt_output_l != other.dgt_output_l:
            return False
        if self.dgt_input_h != other.dgt_input_h:
            return False
        if self.dgt_input_l != other.dgt_input_l:
            return False
        if self.tl_dgt_output_l != other.tl_dgt_output_l:
            return False
        if self.tl_dgt_input_l != other.tl_dgt_input_l:
            return False
        if self.emg != other.emg:
            return False
        if any(self.safetyboxsig != other.safetyboxsig):
            return False
        if self.robot_motion_done != other.robot_motion_done:
            return False
        if self.grip_motion_done != other.grip_motion_done:
            return False
        if self.gripper_position != other.gripper_position:
            return False
        if self.gripper_feedback_valid != other.gripper_feedback_valid:
            return False
        if self.weldbreakoffstate != other.weldbreakoffstate:
            return False
        if self.weldarcstate != other.weldarcstate:
            return False
        if self.welding_voltage != other.welding_voltage:
            return False
        if self.welding_current != other.welding_current:
            return False
        if self.weldtrackspeed != other.weldtrackspeed:
            return False
        if self.main_error_code != other.main_error_code:
            return False
        if self.sub_error_code != other.sub_error_code:
            return False
        if self.check_sum != other.check_sum:
            return False
        if self.timestamp != other.timestamp:
            return False
        if self.version != other.version:
            return False
        if self.tpd_exception != other.tpd_exception:
            return False
        if self.alarm_reboot_robot != other.alarm_reboot_robot:
            return False
        if self.modbusmasterconnectstate != other.modbusmasterconnectstate:
            return False
        if self.mdbsslaveconnect != other.mdbsslaveconnect:
            return False
        if self.socket_conn_timeout != other.socket_conn_timeout:
            return False
        if self.socket_read_timeout != other.socket_read_timeout:
            return False
        if self.btn_box_stop_signa != other.btn_box_stop_signa:
            return False
        if self.strangeposflag != other.strangeposflag:
            return False
        if self.drag_alarm != other.drag_alarm:
            return False
        if self.alarm != other.alarm:
            return False
        if self.safetydoor_alarm != other.safetydoor_alarm:
            return False
        if self.safetyplanealarm != other.safetyplanealarm:
            return False
        if self.motionalarm != other.motionalarm:
            return False
        if self.interferealarm != other.interferealarm:
            return False
        if self.endluaerrcode != other.endluaerrcode:
            return False
        if self.dr_alarm != other.dr_alarm:
            return False
        if self.udpcmdstate != other.udpcmdstate:
            return False
        if self.aliveslavenumerror != other.aliveslavenumerror:
            return False
        if self.gripperfaultnum != other.gripperfaultnum:
            return False
        if any(self.slavecomerror != other.slavecomerror):
            return False
        if self.cmdpointerror != other.cmdpointerror:
            return False
        if self.ioerror != other.ioerror:
            return False
        if self.grippererro != other.grippererro:
            return False
        if self.fileerror != other.fileerror:
            return False
        if self.paraerror != other.paraerror:
            return False
        if self.exaxis_out_slimit_error != other.exaxis_out_slimit_error:
            return False
        if any(self.dr_com_err != other.dr_com_err):
            return False
        if self.dr_err != other.dr_err:
            return False
        if self.out_sflimit_err != other.out_sflimit_err:
            return False
        if self.collision_err != other.collision_err:
            return False
        if self.weld_readystate != other.weld_readystate:
            return False
        if self.alarm_check_emerg_stop_btn != other.alarm_check_emerg_stop_btn:
            return False
        if self.ts_web_state_com_error != other.ts_web_state_com_error:
            return False
        if self.ts_tm_cmd_com_error != other.ts_tm_cmd_com_error:
            return False
        if self.ts_tm_state_com_error != other.ts_tm_state_com_error:
            return False
        if self.ctrlboxerror != other.ctrlboxerror:
            return False
        if self.safety_data_state != other.safety_data_state:
            return False
        if self.forcesensorerrstate != other.forcesensorerrstate:
            return False
        if any(self.ctrlopenluaerrcode != other.ctrlopenluaerrcode):
            return False
        if self.auxservoservoid != other.auxservoservoid:
            return False
        if self.auxservoerrcode != other.auxservoerrcode:
            return False
        if self.auxservostate != other.auxservostate:
            return False
        if self.auxservoactualpos != other.auxservoactualpos:
            return False
        if self.auxservoctualspeed != other.auxservoctualspeed:
            return False
        if self.auxservoactualtorque != other.auxservoactualtorque:
            return False
        if any(self.extpioinput != other.extpioinput):
            return False
        if any(self.extpiooutput != other.extpiooutput):
            return False
        if any(self.extadcinput != other.extadcinput):
            return False
        if any(self.extadcoutput != other.extadcoutput):
            return False
        if self.reconnect_flag != other.reconnect_flag:
            return False
        if self.exaxiscoordid != other.exaxiscoordid:
            return False
        if self.slave_status_1 != other.slave_status_1:
            return False
        if self.slave_status_2 != other.slave_status_2:
            return False
        if self.slave_domain_id != other.slave_domain_id:
            return False
        if self.program_run_state != other.program_run_state:
            return False
        if self.speed_scale_manual != other.speed_scale_manual:
            return False
        if self.speed_scale_auto != other.speed_scale_auto:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def j1_cur_pos(self):
        """Message field 'j1_cur_pos'."""
        return self._j1_cur_pos

    @j1_cur_pos.setter
    def j1_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j1_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j1_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j1_cur_pos = value

    @builtins.property
    def j2_cur_pos(self):
        """Message field 'j2_cur_pos'."""
        return self._j2_cur_pos

    @j2_cur_pos.setter
    def j2_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j2_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j2_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j2_cur_pos = value

    @builtins.property
    def j3_cur_pos(self):
        """Message field 'j3_cur_pos'."""
        return self._j3_cur_pos

    @j3_cur_pos.setter
    def j3_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j3_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j3_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j3_cur_pos = value

    @builtins.property
    def j4_cur_pos(self):
        """Message field 'j4_cur_pos'."""
        return self._j4_cur_pos

    @j4_cur_pos.setter
    def j4_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j4_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j4_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j4_cur_pos = value

    @builtins.property
    def j5_cur_pos(self):
        """Message field 'j5_cur_pos'."""
        return self._j5_cur_pos

    @j5_cur_pos.setter
    def j5_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j5_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j5_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j5_cur_pos = value

    @builtins.property
    def j6_cur_pos(self):
        """Message field 'j6_cur_pos'."""
        return self._j6_cur_pos

    @j6_cur_pos.setter
    def j6_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j6_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j6_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j6_cur_pos = value

    @builtins.property
    def j1_cur_tor(self):
        """Message field 'j1_cur_tor'."""
        return self._j1_cur_tor

    @j1_cur_tor.setter
    def j1_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j1_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j1_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j1_cur_tor = value

    @builtins.property
    def j2_cur_tor(self):
        """Message field 'j2_cur_tor'."""
        return self._j2_cur_tor

    @j2_cur_tor.setter
    def j2_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j2_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j2_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j2_cur_tor = value

    @builtins.property
    def j3_cur_tor(self):
        """Message field 'j3_cur_tor'."""
        return self._j3_cur_tor

    @j3_cur_tor.setter
    def j3_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j3_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j3_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j3_cur_tor = value

    @builtins.property
    def j4_cur_tor(self):
        """Message field 'j4_cur_tor'."""
        return self._j4_cur_tor

    @j4_cur_tor.setter
    def j4_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j4_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j4_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j4_cur_tor = value

    @builtins.property
    def j5_cur_tor(self):
        """Message field 'j5_cur_tor'."""
        return self._j5_cur_tor

    @j5_cur_tor.setter
    def j5_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j5_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j5_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j5_cur_tor = value

    @builtins.property
    def j6_cur_tor(self):
        """Message field 'j6_cur_tor'."""
        return self._j6_cur_tor

    @j6_cur_tor.setter
    def j6_cur_tor(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'j6_cur_tor' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'j6_cur_tor' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._j6_cur_tor = value

    @builtins.property
    def cart_x_cur_pos(self):
        """Message field 'cart_x_cur_pos'."""
        return self._cart_x_cur_pos

    @cart_x_cur_pos.setter
    def cart_x_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_x_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_x_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_x_cur_pos = value

    @builtins.property
    def cart_y_cur_pos(self):
        """Message field 'cart_y_cur_pos'."""
        return self._cart_y_cur_pos

    @cart_y_cur_pos.setter
    def cart_y_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_y_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_y_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_y_cur_pos = value

    @builtins.property
    def cart_z_cur_pos(self):
        """Message field 'cart_z_cur_pos'."""
        return self._cart_z_cur_pos

    @cart_z_cur_pos.setter
    def cart_z_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_z_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_z_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_z_cur_pos = value

    @builtins.property
    def cart_a_cur_pos(self):
        """Message field 'cart_a_cur_pos'."""
        return self._cart_a_cur_pos

    @cart_a_cur_pos.setter
    def cart_a_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_a_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_a_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_a_cur_pos = value

    @builtins.property
    def cart_b_cur_pos(self):
        """Message field 'cart_b_cur_pos'."""
        return self._cart_b_cur_pos

    @cart_b_cur_pos.setter
    def cart_b_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_b_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_b_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_b_cur_pos = value

    @builtins.property
    def cart_c_cur_pos(self):
        """Message field 'cart_c_cur_pos'."""
        return self._cart_c_cur_pos

    @cart_c_cur_pos.setter
    def cart_c_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'cart_c_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'cart_c_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._cart_c_cur_pos = value

    @builtins.property
    def flange_x_cur_pos(self):
        """Message field 'flange_x_cur_pos'."""
        return self._flange_x_cur_pos

    @flange_x_cur_pos.setter
    def flange_x_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_x_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_x_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_x_cur_pos = value

    @builtins.property
    def flange_y_cur_pos(self):
        """Message field 'flange_y_cur_pos'."""
        return self._flange_y_cur_pos

    @flange_y_cur_pos.setter
    def flange_y_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_y_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_y_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_y_cur_pos = value

    @builtins.property
    def flange_z_cur_pos(self):
        """Message field 'flange_z_cur_pos'."""
        return self._flange_z_cur_pos

    @flange_z_cur_pos.setter
    def flange_z_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_z_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_z_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_z_cur_pos = value

    @builtins.property
    def flange_a_cur_pos(self):
        """Message field 'flange_a_cur_pos'."""
        return self._flange_a_cur_pos

    @flange_a_cur_pos.setter
    def flange_a_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_a_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_a_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_a_cur_pos = value

    @builtins.property
    def flange_b_cur_pos(self):
        """Message field 'flange_b_cur_pos'."""
        return self._flange_b_cur_pos

    @flange_b_cur_pos.setter
    def flange_b_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_b_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_b_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_b_cur_pos = value

    @builtins.property
    def flange_c_cur_pos(self):
        """Message field 'flange_c_cur_pos'."""
        return self._flange_c_cur_pos

    @flange_c_cur_pos.setter
    def flange_c_cur_pos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'flange_c_cur_pos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'flange_c_cur_pos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._flange_c_cur_pos = value

    @builtins.property
    def exaxispos1(self):
        """Message field 'exaxispos1'."""
        return self._exaxispos1

    @exaxispos1.setter
    def exaxispos1(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'exaxispos1' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'exaxispos1' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._exaxispos1 = value

    @builtins.property
    def exaxistatus1(self):
        """Message field 'exaxistatus1'."""
        return self._exaxistatus1

    @exaxistatus1.setter
    def exaxistatus1(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.int32, \
                    "The 'exaxistatus1' numpy.ndarray() must have the dtype of 'numpy.int32'"
                assert value.size == 10, \
                    "The 'exaxistatus1' numpy.ndarray() must have a size of 10"
                self._exaxistatus1 = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 10 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'exaxistatus1' field must be a set or sequence with length 10 and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._exaxistatus1 = numpy.array(value, dtype=numpy.int32)

    @builtins.property
    def exaxispos2(self):
        """Message field 'exaxispos2'."""
        return self._exaxispos2

    @exaxispos2.setter
    def exaxispos2(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'exaxispos2' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'exaxispos2' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._exaxispos2 = value

    @builtins.property
    def exaxistatus2(self):
        """Message field 'exaxistatus2'."""
        return self._exaxistatus2

    @exaxistatus2.setter
    def exaxistatus2(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.int32, \
                    "The 'exaxistatus2' numpy.ndarray() must have the dtype of 'numpy.int32'"
                assert value.size == 10, \
                    "The 'exaxistatus2' numpy.ndarray() must have a size of 10"
                self._exaxistatus2 = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 10 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'exaxistatus2' field must be a set or sequence with length 10 and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._exaxistatus2 = numpy.array(value, dtype=numpy.int32)

    @builtins.property
    def exaxispos3(self):
        """Message field 'exaxispos3'."""
        return self._exaxispos3

    @exaxispos3.setter
    def exaxispos3(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'exaxispos3' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'exaxispos3' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._exaxispos3 = value

    @builtins.property
    def exaxistatus3(self):
        """Message field 'exaxistatus3'."""
        return self._exaxistatus3

    @exaxistatus3.setter
    def exaxistatus3(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.int32, \
                    "The 'exaxistatus3' numpy.ndarray() must have the dtype of 'numpy.int32'"
                assert value.size == 10, \
                    "The 'exaxistatus3' numpy.ndarray() must have a size of 10"
                self._exaxistatus3 = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 10 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'exaxistatus3' field must be a set or sequence with length 10 and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._exaxistatus3 = numpy.array(value, dtype=numpy.int32)

    @builtins.property
    def exaxispos4(self):
        """Message field 'exaxispos4'."""
        return self._exaxispos4

    @exaxispos4.setter
    def exaxispos4(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'exaxispos4' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'exaxispos4' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._exaxispos4 = value

    @builtins.property
    def exaxistatus4(self):
        """Message field 'exaxistatus4'."""
        return self._exaxistatus4

    @exaxistatus4.setter
    def exaxistatus4(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.int32, \
                    "The 'exaxistatus4' numpy.ndarray() must have the dtype of 'numpy.int32'"
                assert value.size == 10, \
                    "The 'exaxistatus4' numpy.ndarray() must have a size of 10"
                self._exaxistatus4 = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 10 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'exaxistatus4' field must be a set or sequence with length 10 and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._exaxistatus4 = numpy.array(value, dtype=numpy.int32)

    @builtins.property
    def ft_fx_data(self):
        """Message field 'ft_fx_data'."""
        return self._ft_fx_data

    @ft_fx_data.setter
    def ft_fx_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_fx_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_fx_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_fx_data = value

    @builtins.property
    def ft_fy_data(self):
        """Message field 'ft_fy_data'."""
        return self._ft_fy_data

    @ft_fy_data.setter
    def ft_fy_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_fy_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_fy_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_fy_data = value

    @builtins.property
    def ft_fz_data(self):
        """Message field 'ft_fz_data'."""
        return self._ft_fz_data

    @ft_fz_data.setter
    def ft_fz_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_fz_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_fz_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_fz_data = value

    @builtins.property
    def ft_tx_data(self):
        """Message field 'ft_tx_data'."""
        return self._ft_tx_data

    @ft_tx_data.setter
    def ft_tx_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_tx_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_tx_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_tx_data = value

    @builtins.property
    def ft_ty_data(self):
        """Message field 'ft_ty_data'."""
        return self._ft_ty_data

    @ft_ty_data.setter
    def ft_ty_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_ty_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_ty_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_ty_data = value

    @builtins.property
    def ft_tz_data(self):
        """Message field 'ft_tz_data'."""
        return self._ft_tz_data

    @ft_tz_data.setter
    def ft_tz_data(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'ft_tz_data' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'ft_tz_data' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._ft_tz_data = value

    @builtins.property
    def ft_actstatus(self):
        """Message field 'ft_actstatus'."""
        return self._ft_actstatus

    @ft_actstatus.setter
    def ft_actstatus(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ft_actstatus' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'ft_actstatus' field must be an unsigned integer in [0, 255]"
        self._ft_actstatus = value

    @builtins.property
    def robot_mode(self):
        """Message field 'robot_mode'."""
        return self._robot_mode

    @robot_mode.setter
    def robot_mode(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'robot_mode' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'robot_mode' field must be an unsigned integer in [0, 255]"
        self._robot_mode = value

    @builtins.property
    def tool_num(self):
        """Message field 'tool_num'."""
        return self._tool_num

    @tool_num.setter
    def tool_num(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'tool_num' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'tool_num' field must be an unsigned integer in [0, 255]"
        self._tool_num = value

    @builtins.property
    def work_num(self):
        """Message field 'work_num'."""
        return self._work_num

    @work_num.setter
    def work_num(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'work_num' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'work_num' field must be an unsigned integer in [0, 255]"
        self._work_num = value

    @builtins.property
    def prg_state(self):
        """Message field 'prg_state'."""
        return self._prg_state

    @prg_state.setter
    def prg_state(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'prg_state' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'prg_state' field must be an unsigned integer in [0, 255]"
        self._prg_state = value

    @builtins.property
    def abnormal_stop(self):
        """Message field 'abnormal_stop'."""
        return self._abnormal_stop

    @abnormal_stop.setter
    def abnormal_stop(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'abnormal_stop' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'abnormal_stop' field must be an unsigned integer in [0, 255]"
        self._abnormal_stop = value

    @builtins.property
    def prg_name(self):
        """Message field 'prg_name'."""
        return self._prg_name

    @prg_name.setter
    def prg_name(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'prg_name' field must be of type 'str'"
        self._prg_name = value

    @builtins.property
    def prg_total_line(self):
        """Message field 'prg_total_line'."""
        return self._prg_total_line

    @prg_total_line.setter
    def prg_total_line(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'prg_total_line' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'prg_total_line' field must be an unsigned integer in [0, 255]"
        self._prg_total_line = value

    @builtins.property
    def prg_cur_line(self):
        """Message field 'prg_cur_line'."""
        return self._prg_cur_line

    @prg_cur_line.setter
    def prg_cur_line(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'prg_cur_line' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'prg_cur_line' field must be an unsigned integer in [0, 255]"
        self._prg_cur_line = value

    @builtins.property
    def dgt_output_h(self):
        """Message field 'dgt_output_h'."""
        return self._dgt_output_h

    @dgt_output_h.setter
    def dgt_output_h(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'dgt_output_h' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'dgt_output_h' field must be an unsigned integer in [0, 255]"
        self._dgt_output_h = value

    @builtins.property
    def dgt_output_l(self):
        """Message field 'dgt_output_l'."""
        return self._dgt_output_l

    @dgt_output_l.setter
    def dgt_output_l(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'dgt_output_l' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'dgt_output_l' field must be an unsigned integer in [0, 255]"
        self._dgt_output_l = value

    @builtins.property
    def dgt_input_h(self):
        """Message field 'dgt_input_h'."""
        return self._dgt_input_h

    @dgt_input_h.setter
    def dgt_input_h(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'dgt_input_h' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'dgt_input_h' field must be an unsigned integer in [0, 255]"
        self._dgt_input_h = value

    @builtins.property
    def dgt_input_l(self):
        """Message field 'dgt_input_l'."""
        return self._dgt_input_l

    @dgt_input_l.setter
    def dgt_input_l(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'dgt_input_l' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'dgt_input_l' field must be an unsigned integer in [0, 255]"
        self._dgt_input_l = value

    @builtins.property
    def tl_dgt_output_l(self):
        """Message field 'tl_dgt_output_l'."""
        return self._tl_dgt_output_l

    @tl_dgt_output_l.setter
    def tl_dgt_output_l(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'tl_dgt_output_l' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'tl_dgt_output_l' field must be an unsigned integer in [0, 255]"
        self._tl_dgt_output_l = value

    @builtins.property
    def tl_dgt_input_l(self):
        """Message field 'tl_dgt_input_l'."""
        return self._tl_dgt_input_l

    @tl_dgt_input_l.setter
    def tl_dgt_input_l(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'tl_dgt_input_l' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'tl_dgt_input_l' field must be an unsigned integer in [0, 255]"
        self._tl_dgt_input_l = value

    @builtins.property
    def emg(self):
        """Message field 'emg'."""
        return self._emg

    @emg.setter
    def emg(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'emg' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'emg' field must be an unsigned integer in [0, 255]"
        self._emg = value

    @builtins.property
    def safetyboxsig(self):
        """Message field 'safetyboxsig'."""
        return self._safetyboxsig

    @safetyboxsig.setter
    def safetyboxsig(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint8, \
                    "The 'safetyboxsig' numpy.ndarray() must have the dtype of 'numpy.uint8'"
                assert value.size == 6, \
                    "The 'safetyboxsig' numpy.ndarray() must have a size of 6"
                self._safetyboxsig = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 6 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 256 for val in value)), \
                "The 'safetyboxsig' field must be a set or sequence with length 6 and each value of type 'int' and each unsigned integer in [0, 255]"
        self._safetyboxsig = numpy.array(value, dtype=numpy.uint8)

    @builtins.property
    def robot_motion_done(self):
        """Message field 'robot_motion_done'."""
        return self._robot_motion_done

    @robot_motion_done.setter
    def robot_motion_done(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'robot_motion_done' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'robot_motion_done' field must be an unsigned integer in [0, 255]"
        self._robot_motion_done = value

    @builtins.property
    def grip_motion_done(self):
        """Message field 'grip_motion_done'."""
        return self._grip_motion_done

    @grip_motion_done.setter
    def grip_motion_done(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'grip_motion_done' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'grip_motion_done' field must be an unsigned integer in [0, 255]"
        self._grip_motion_done = value

    @builtins.property
    def gripper_position(self):
        """Message field 'gripper_position'."""
        return self._gripper_position

    @gripper_position.setter
    def gripper_position(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'gripper_position' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'gripper_position' field must be an unsigned integer in [0, 255]"
        self._gripper_position = value

    @builtins.property
    def gripper_feedback_valid(self):
        """Message field 'gripper_feedback_valid'."""
        return self._gripper_feedback_valid

    @gripper_feedback_valid.setter
    def gripper_feedback_valid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'gripper_feedback_valid' field must be of type 'bool'"
        self._gripper_feedback_valid = value

    @builtins.property
    def weldbreakoffstate(self):
        """Message field 'weldbreakoffstate'."""
        return self._weldbreakoffstate

    @weldbreakoffstate.setter
    def weldbreakoffstate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'weldbreakoffstate' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'weldbreakoffstate' field must be an unsigned integer in [0, 255]"
        self._weldbreakoffstate = value

    @builtins.property
    def weldarcstate(self):
        """Message field 'weldarcstate'."""
        return self._weldarcstate

    @weldarcstate.setter
    def weldarcstate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'weldarcstate' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'weldarcstate' field must be an unsigned integer in [0, 255]"
        self._weldarcstate = value

    @builtins.property
    def welding_voltage(self):
        """Message field 'welding_voltage'."""
        return self._welding_voltage

    @welding_voltage.setter
    def welding_voltage(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'welding_voltage' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'welding_voltage' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._welding_voltage = value

    @builtins.property
    def welding_current(self):
        """Message field 'welding_current'."""
        return self._welding_current

    @welding_current.setter
    def welding_current(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'welding_current' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'welding_current' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._welding_current = value

    @builtins.property
    def weldtrackspeed(self):
        """Message field 'weldtrackspeed'."""
        return self._weldtrackspeed

    @weldtrackspeed.setter
    def weldtrackspeed(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'weldtrackspeed' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'weldtrackspeed' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._weldtrackspeed = value

    @builtins.property
    def main_error_code(self):
        """Message field 'main_error_code'."""
        return self._main_error_code

    @main_error_code.setter
    def main_error_code(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'main_error_code' field must be of type 'int'"
            assert value >= 0 and value < 4294967296, \
                "The 'main_error_code' field must be an unsigned integer in [0, 4294967295]"
        self._main_error_code = value

    @builtins.property
    def sub_error_code(self):
        """Message field 'sub_error_code'."""
        return self._sub_error_code

    @sub_error_code.setter
    def sub_error_code(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'sub_error_code' field must be of type 'int'"
            assert value >= 0 and value < 4294967296, \
                "The 'sub_error_code' field must be an unsigned integer in [0, 4294967295]"
        self._sub_error_code = value

    @builtins.property
    def check_sum(self):
        """Message field 'check_sum'."""
        return self._check_sum

    @check_sum.setter
    def check_sum(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'check_sum' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'check_sum' field must be an unsigned integer in [0, 255]"
        self._check_sum = value

    @builtins.property
    def timestamp(self):
        """Message field 'timestamp'."""
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'timestamp' field must be of type 'int'"
            assert value >= 0 and value < 18446744073709551616, \
                "The 'timestamp' field must be an unsigned integer in [0, 18446744073709551615]"
        self._timestamp = value

    @builtins.property
    def version(self):
        """Message field 'version'."""
        return self._version

    @version.setter
    def version(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'version' field must be of type 'str'"
        self._version = value

    @builtins.property
    def tpd_exception(self):
        """Message field 'tpd_exception'."""
        return self._tpd_exception

    @tpd_exception.setter
    def tpd_exception(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'tpd_exception' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'tpd_exception' field must be an unsigned integer in [0, 255]"
        self._tpd_exception = value

    @builtins.property
    def alarm_reboot_robot(self):
        """Message field 'alarm_reboot_robot'."""
        return self._alarm_reboot_robot

    @alarm_reboot_robot.setter
    def alarm_reboot_robot(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'alarm_reboot_robot' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'alarm_reboot_robot' field must be an unsigned integer in [0, 255]"
        self._alarm_reboot_robot = value

    @builtins.property
    def modbusmasterconnectstate(self):
        """Message field 'modbusmasterconnectstate'."""
        return self._modbusmasterconnectstate

    @modbusmasterconnectstate.setter
    def modbusmasterconnectstate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'modbusmasterconnectstate' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'modbusmasterconnectstate' field must be an unsigned integer in [0, 255]"
        self._modbusmasterconnectstate = value

    @builtins.property
    def mdbsslaveconnect(self):
        """Message field 'mdbsslaveconnect'."""
        return self._mdbsslaveconnect

    @mdbsslaveconnect.setter
    def mdbsslaveconnect(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'mdbsslaveconnect' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'mdbsslaveconnect' field must be an unsigned integer in [0, 255]"
        self._mdbsslaveconnect = value

    @builtins.property
    def socket_conn_timeout(self):
        """Message field 'socket_conn_timeout'."""
        return self._socket_conn_timeout

    @socket_conn_timeout.setter
    def socket_conn_timeout(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'socket_conn_timeout' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'socket_conn_timeout' field must be an unsigned integer in [0, 255]"
        self._socket_conn_timeout = value

    @builtins.property
    def socket_read_timeout(self):
        """Message field 'socket_read_timeout'."""
        return self._socket_read_timeout

    @socket_read_timeout.setter
    def socket_read_timeout(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'socket_read_timeout' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'socket_read_timeout' field must be an unsigned integer in [0, 255]"
        self._socket_read_timeout = value

    @builtins.property
    def btn_box_stop_signa(self):
        """Message field 'btn_box_stop_signa'."""
        return self._btn_box_stop_signa

    @btn_box_stop_signa.setter
    def btn_box_stop_signa(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'btn_box_stop_signa' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'btn_box_stop_signa' field must be an unsigned integer in [0, 255]"
        self._btn_box_stop_signa = value

    @builtins.property
    def strangeposflag(self):
        """Message field 'strangeposflag'."""
        return self._strangeposflag

    @strangeposflag.setter
    def strangeposflag(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'strangeposflag' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'strangeposflag' field must be an unsigned integer in [0, 255]"
        self._strangeposflag = value

    @builtins.property
    def drag_alarm(self):
        """Message field 'drag_alarm'."""
        return self._drag_alarm

    @drag_alarm.setter
    def drag_alarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'drag_alarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'drag_alarm' field must be an unsigned integer in [0, 255]"
        self._drag_alarm = value

    @builtins.property
    def alarm(self):
        """Message field 'alarm'."""
        return self._alarm

    @alarm.setter
    def alarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'alarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'alarm' field must be an unsigned integer in [0, 255]"
        self._alarm = value

    @builtins.property
    def safetydoor_alarm(self):
        """Message field 'safetydoor_alarm'."""
        return self._safetydoor_alarm

    @safetydoor_alarm.setter
    def safetydoor_alarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'safetydoor_alarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'safetydoor_alarm' field must be an unsigned integer in [0, 255]"
        self._safetydoor_alarm = value

    @builtins.property
    def safetyplanealarm(self):
        """Message field 'safetyplanealarm'."""
        return self._safetyplanealarm

    @safetyplanealarm.setter
    def safetyplanealarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'safetyplanealarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'safetyplanealarm' field must be an unsigned integer in [0, 255]"
        self._safetyplanealarm = value

    @builtins.property
    def motionalarm(self):
        """Message field 'motionalarm'."""
        return self._motionalarm

    @motionalarm.setter
    def motionalarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'motionalarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'motionalarm' field must be an unsigned integer in [0, 255]"
        self._motionalarm = value

    @builtins.property
    def interferealarm(self):
        """Message field 'interferealarm'."""
        return self._interferealarm

    @interferealarm.setter
    def interferealarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'interferealarm' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'interferealarm' field must be an unsigned integer in [0, 255]"
        self._interferealarm = value

    @builtins.property
    def endluaerrcode(self):
        """Message field 'endluaerrcode'."""
        return self._endluaerrcode

    @endluaerrcode.setter
    def endluaerrcode(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'endluaerrcode' field must be of type 'int'"
            assert value >= 0 and value < 65536, \
                "The 'endluaerrcode' field must be an unsigned integer in [0, 65535]"
        self._endluaerrcode = value

    @builtins.property
    def dr_alarm(self):
        """Message field 'dr_alarm'."""
        return self._dr_alarm

    @dr_alarm.setter
    def dr_alarm(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'dr_alarm' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'dr_alarm' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._dr_alarm = value

    @builtins.property
    def udpcmdstate(self):
        """Message field 'udpcmdstate'."""
        return self._udpcmdstate

    @udpcmdstate.setter
    def udpcmdstate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'udpcmdstate' field must be of type 'int'"
            assert value >= 0 and value < 65536, \
                "The 'udpcmdstate' field must be an unsigned integer in [0, 65535]"
        self._udpcmdstate = value

    @builtins.property
    def aliveslavenumerror(self):
        """Message field 'aliveslavenumerror'."""
        return self._aliveslavenumerror

    @aliveslavenumerror.setter
    def aliveslavenumerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'aliveslavenumerror' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'aliveslavenumerror' field must be an unsigned integer in [0, 255]"
        self._aliveslavenumerror = value

    @builtins.property
    def gripperfaultnum(self):
        """Message field 'gripperfaultnum'."""
        return self._gripperfaultnum

    @gripperfaultnum.setter
    def gripperfaultnum(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'gripperfaultnum' field must be of type 'int'"
            assert value >= 0 and value < 65536, \
                "The 'gripperfaultnum' field must be an unsigned integer in [0, 65535]"
        self._gripperfaultnum = value

    @builtins.property
    def slavecomerror(self):
        """Message field 'slavecomerror'."""
        return self._slavecomerror

    @slavecomerror.setter
    def slavecomerror(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint8, \
                    "The 'slavecomerror' numpy.ndarray() must have the dtype of 'numpy.uint8'"
                assert value.size == 8, \
                    "The 'slavecomerror' numpy.ndarray() must have a size of 8"
                self._slavecomerror = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 8 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 256 for val in value)), \
                "The 'slavecomerror' field must be a set or sequence with length 8 and each value of type 'int' and each unsigned integer in [0, 255]"
        self._slavecomerror = numpy.array(value, dtype=numpy.uint8)

    @builtins.property
    def cmdpointerror(self):
        """Message field 'cmdpointerror'."""
        return self._cmdpointerror

    @cmdpointerror.setter
    def cmdpointerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'cmdpointerror' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'cmdpointerror' field must be an unsigned integer in [0, 255]"
        self._cmdpointerror = value

    @builtins.property
    def ioerror(self):
        """Message field 'ioerror'."""
        return self._ioerror

    @ioerror.setter
    def ioerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ioerror' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'ioerror' field must be an unsigned integer in [0, 255]"
        self._ioerror = value

    @builtins.property
    def grippererro(self):
        """Message field 'grippererro'."""
        return self._grippererro

    @grippererro.setter
    def grippererro(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'grippererro' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'grippererro' field must be an unsigned integer in [0, 255]"
        self._grippererro = value

    @builtins.property
    def fileerror(self):
        """Message field 'fileerror'."""
        return self._fileerror

    @fileerror.setter
    def fileerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'fileerror' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'fileerror' field must be an unsigned integer in [0, 255]"
        self._fileerror = value

    @builtins.property
    def paraerror(self):
        """Message field 'paraerror'."""
        return self._paraerror

    @paraerror.setter
    def paraerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'paraerror' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'paraerror' field must be an unsigned integer in [0, 255]"
        self._paraerror = value

    @builtins.property
    def exaxis_out_slimit_error(self):
        """Message field 'exaxis_out_slimit_error'."""
        return self._exaxis_out_slimit_error

    @exaxis_out_slimit_error.setter
    def exaxis_out_slimit_error(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'exaxis_out_slimit_error' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'exaxis_out_slimit_error' field must be an unsigned integer in [0, 255]"
        self._exaxis_out_slimit_error = value

    @builtins.property
    def dr_com_err(self):
        """Message field 'dr_com_err'."""
        return self._dr_com_err

    @dr_com_err.setter
    def dr_com_err(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint8, \
                    "The 'dr_com_err' numpy.ndarray() must have the dtype of 'numpy.uint8'"
                assert value.size == 6, \
                    "The 'dr_com_err' numpy.ndarray() must have a size of 6"
                self._dr_com_err = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 6 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 256 for val in value)), \
                "The 'dr_com_err' field must be a set or sequence with length 6 and each value of type 'int' and each unsigned integer in [0, 255]"
        self._dr_com_err = numpy.array(value, dtype=numpy.uint8)

    @builtins.property
    def dr_err(self):
        """Message field 'dr_err'."""
        return self._dr_err

    @dr_err.setter
    def dr_err(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'dr_err' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'dr_err' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._dr_err = value

    @builtins.property
    def out_sflimit_err(self):
        """Message field 'out_sflimit_err'."""
        return self._out_sflimit_err

    @out_sflimit_err.setter
    def out_sflimit_err(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'out_sflimit_err' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'out_sflimit_err' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._out_sflimit_err = value

    @builtins.property
    def collision_err(self):
        """Message field 'collision_err'."""
        return self._collision_err

    @collision_err.setter
    def collision_err(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'collision_err' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'collision_err' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._collision_err = value

    @builtins.property
    def weld_readystate(self):
        """Message field 'weld_readystate'."""
        return self._weld_readystate

    @weld_readystate.setter
    def weld_readystate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'weld_readystate' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'weld_readystate' field must be an unsigned integer in [0, 255]"
        self._weld_readystate = value

    @builtins.property
    def alarm_check_emerg_stop_btn(self):
        """Message field 'alarm_check_emerg_stop_btn'."""
        return self._alarm_check_emerg_stop_btn

    @alarm_check_emerg_stop_btn.setter
    def alarm_check_emerg_stop_btn(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'alarm_check_emerg_stop_btn' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'alarm_check_emerg_stop_btn' field must be an unsigned integer in [0, 255]"
        self._alarm_check_emerg_stop_btn = value

    @builtins.property
    def ts_web_state_com_error(self):
        """Message field 'ts_web_state_com_error'."""
        return self._ts_web_state_com_error

    @ts_web_state_com_error.setter
    def ts_web_state_com_error(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ts_web_state_com_error' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'ts_web_state_com_error' field must be an unsigned integer in [0, 255]"
        self._ts_web_state_com_error = value

    @builtins.property
    def ts_tm_cmd_com_error(self):
        """Message field 'ts_tm_cmd_com_error'."""
        return self._ts_tm_cmd_com_error

    @ts_tm_cmd_com_error.setter
    def ts_tm_cmd_com_error(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ts_tm_cmd_com_error' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'ts_tm_cmd_com_error' field must be an unsigned integer in [0, 255]"
        self._ts_tm_cmd_com_error = value

    @builtins.property
    def ts_tm_state_com_error(self):
        """Message field 'ts_tm_state_com_error'."""
        return self._ts_tm_state_com_error

    @ts_tm_state_com_error.setter
    def ts_tm_state_com_error(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ts_tm_state_com_error' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'ts_tm_state_com_error' field must be an unsigned integer in [0, 255]"
        self._ts_tm_state_com_error = value

    @builtins.property
    def ctrlboxerror(self):
        """Message field 'ctrlboxerror'."""
        return self._ctrlboxerror

    @ctrlboxerror.setter
    def ctrlboxerror(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'ctrlboxerror' field must be of type 'int'"
            assert value >= 0 and value < 65536, \
                "The 'ctrlboxerror' field must be an unsigned integer in [0, 65535]"
        self._ctrlboxerror = value

    @builtins.property
    def safety_data_state(self):
        """Message field 'safety_data_state'."""
        return self._safety_data_state

    @safety_data_state.setter
    def safety_data_state(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'safety_data_state' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'safety_data_state' field must be an unsigned integer in [0, 255]"
        self._safety_data_state = value

    @builtins.property
    def forcesensorerrstate(self):
        """Message field 'forcesensorerrstate'."""
        return self._forcesensorerrstate

    @forcesensorerrstate.setter
    def forcesensorerrstate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'forcesensorerrstate' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'forcesensorerrstate' field must be an unsigned integer in [0, 255]"
        self._forcesensorerrstate = value

    @builtins.property
    def ctrlopenluaerrcode(self):
        """Message field 'ctrlopenluaerrcode'."""
        return self._ctrlopenluaerrcode

    @ctrlopenluaerrcode.setter
    def ctrlopenluaerrcode(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint8, \
                    "The 'ctrlopenluaerrcode' numpy.ndarray() must have the dtype of 'numpy.uint8'"
                assert value.size == 4, \
                    "The 'ctrlopenluaerrcode' numpy.ndarray() must have a size of 4"
                self._ctrlopenluaerrcode = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 4 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 256 for val in value)), \
                "The 'ctrlopenluaerrcode' field must be a set or sequence with length 4 and each value of type 'int' and each unsigned integer in [0, 255]"
        self._ctrlopenluaerrcode = numpy.array(value, dtype=numpy.uint8)

    @builtins.property
    def auxservoservoid(self):
        """Message field 'auxservoservoid'."""
        return self._auxservoservoid

    @auxservoservoid.setter
    def auxservoservoid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'auxservoservoid' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'auxservoservoid' field must be an unsigned integer in [0, 255]"
        self._auxservoservoid = value

    @builtins.property
    def auxservoerrcode(self):
        """Message field 'auxservoerrcode'."""
        return self._auxservoerrcode

    @auxservoerrcode.setter
    def auxservoerrcode(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'auxservoerrcode' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'auxservoerrcode' field must be an integer in [-2147483648, 2147483647]"
        self._auxservoerrcode = value

    @builtins.property
    def auxservostate(self):
        """Message field 'auxservostate'."""
        return self._auxservostate

    @auxservostate.setter
    def auxservostate(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'auxservostate' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'auxservostate' field must be an integer in [-2147483648, 2147483647]"
        self._auxservostate = value

    @builtins.property
    def auxservoactualpos(self):
        """Message field 'auxservoactualpos'."""
        return self._auxservoactualpos

    @auxservoactualpos.setter
    def auxservoactualpos(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'auxservoactualpos' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'auxservoactualpos' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._auxservoactualpos = value

    @builtins.property
    def auxservoctualspeed(self):
        """Message field 'auxservoctualspeed'."""
        return self._auxservoctualspeed

    @auxservoctualspeed.setter
    def auxservoctualspeed(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'auxservoctualspeed' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'auxservoctualspeed' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._auxservoctualspeed = value

    @builtins.property
    def auxservoactualtorque(self):
        """Message field 'auxservoactualtorque'."""
        return self._auxservoactualtorque

    @auxservoactualtorque.setter
    def auxservoactualtorque(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'auxservoactualtorque' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'auxservoactualtorque' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._auxservoactualtorque = value

    @builtins.property
    def extpioinput(self):
        """Message field 'extpioinput'."""
        return self._extpioinput

    @extpioinput.setter
    def extpioinput(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint16, \
                    "The 'extpioinput' numpy.ndarray() must have the dtype of 'numpy.uint16'"
                assert value.size == 8, \
                    "The 'extpioinput' numpy.ndarray() must have a size of 8"
                self._extpioinput = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 8 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 65536 for val in value)), \
                "The 'extpioinput' field must be a set or sequence with length 8 and each value of type 'int' and each unsigned integer in [0, 65535]"
        self._extpioinput = numpy.array(value, dtype=numpy.uint16)

    @builtins.property
    def extpiooutput(self):
        """Message field 'extpiooutput'."""
        return self._extpiooutput

    @extpiooutput.setter
    def extpiooutput(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint16, \
                    "The 'extpiooutput' numpy.ndarray() must have the dtype of 'numpy.uint16'"
                assert value.size == 8, \
                    "The 'extpiooutput' numpy.ndarray() must have a size of 8"
                self._extpiooutput = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 8 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 65536 for val in value)), \
                "The 'extpiooutput' field must be a set or sequence with length 8 and each value of type 'int' and each unsigned integer in [0, 65535]"
        self._extpiooutput = numpy.array(value, dtype=numpy.uint16)

    @builtins.property
    def extadcinput(self):
        """Message field 'extadcinput'."""
        return self._extadcinput

    @extadcinput.setter
    def extadcinput(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint16, \
                    "The 'extadcinput' numpy.ndarray() must have the dtype of 'numpy.uint16'"
                assert value.size == 4, \
                    "The 'extadcinput' numpy.ndarray() must have a size of 4"
                self._extadcinput = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 4 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 65536 for val in value)), \
                "The 'extadcinput' field must be a set or sequence with length 4 and each value of type 'int' and each unsigned integer in [0, 65535]"
        self._extadcinput = numpy.array(value, dtype=numpy.uint16)

    @builtins.property
    def extadcoutput(self):
        """Message field 'extadcoutput'."""
        return self._extadcoutput

    @extadcoutput.setter
    def extadcoutput(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.uint16, \
                    "The 'extadcoutput' numpy.ndarray() must have the dtype of 'numpy.uint16'"
                assert value.size == 4, \
                    "The 'extadcoutput' numpy.ndarray() must have a size of 4"
                self._extadcoutput = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 4 and
                 all(isinstance(v, int) for v in value) and
                 all(val >= 0 and val < 65536 for val in value)), \
                "The 'extadcoutput' field must be a set or sequence with length 4 and each value of type 'int' and each unsigned integer in [0, 65535]"
        self._extadcoutput = numpy.array(value, dtype=numpy.uint16)

    @builtins.property
    def reconnect_flag(self):
        """Message field 'reconnect_flag'."""
        return self._reconnect_flag

    @reconnect_flag.setter
    def reconnect_flag(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'reconnect_flag' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'reconnect_flag' field must be an unsigned integer in [0, 255]"
        self._reconnect_flag = value

    @builtins.property
    def exaxiscoordid(self):
        """Message field 'exaxiscoordid'."""
        return self._exaxiscoordid

    @exaxiscoordid.setter
    def exaxiscoordid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'exaxiscoordid' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'exaxiscoordid' field must be an unsigned integer in [0, 255]"
        self._exaxiscoordid = value

    @builtins.property
    def slave_status_1(self):
        """Message field 'slave_status_1'."""
        return self._slave_status_1

    @slave_status_1.setter
    def slave_status_1(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'slave_status_1' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'slave_status_1' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._slave_status_1 = value

    @builtins.property
    def slave_status_2(self):
        """Message field 'slave_status_2'."""
        return self._slave_status_2

    @slave_status_2.setter
    def slave_status_2(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'slave_status_2' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'slave_status_2' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._slave_status_2 = value

    @builtins.property
    def slave_domain_id(self):
        """Message field 'slave_domain_id'."""
        return self._slave_domain_id

    @slave_domain_id.setter
    def slave_domain_id(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'slave_domain_id' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'slave_domain_id' field must be an integer in [-2147483648, 2147483647]"
        self._slave_domain_id = value

    @builtins.property
    def program_run_state(self):
        """Message field 'program_run_state'."""
        return self._program_run_state

    @program_run_state.setter
    def program_run_state(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'program_run_state' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'program_run_state' field must be an unsigned integer in [0, 255]"
        self._program_run_state = value

    @builtins.property
    def speed_scale_manual(self):
        """Message field 'speed_scale_manual'."""
        return self._speed_scale_manual

    @speed_scale_manual.setter
    def speed_scale_manual(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'speed_scale_manual' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'speed_scale_manual' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._speed_scale_manual = value

    @builtins.property
    def speed_scale_auto(self):
        """Message field 'speed_scale_auto'."""
        return self._speed_scale_auto

    @speed_scale_auto.setter
    def speed_scale_auto(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'speed_scale_auto' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'speed_scale_auto' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._speed_scale_auto = value
