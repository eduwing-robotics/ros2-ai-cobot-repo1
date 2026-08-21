# generated from rosidl_generator_py/resource/_idl.py.em
# with input from vision_interfaces:msg/VisionStatus.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_VisionStatus(type):
    """Metaclass of message 'VisionStatus'."""

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
            module = import_type_support('vision_interfaces')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'vision_interfaces.msg.VisionStatus')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__vision_status
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__vision_status
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__vision_status
            cls._TYPE_SUPPORT = module.type_support_msg__msg__vision_status
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__vision_status

            from std_msgs.msg import Header
            if Header.__class__._TYPE_SUPPORT is None:
                Header.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class VisionStatus(metaclass=Metaclass_VisionStatus):
    """Message class 'VisionStatus'."""

    __slots__ = [
        '_header',
        '_ready',
        '_model_loaded',
        '_cameras',
        '_active_cameras',
        '_missing_cameras',
        '_inference_count',
        '_message',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'header': 'std_msgs/Header',
        'ready': 'boolean',
        'model_loaded': 'boolean',
        'cameras': 'sequence<string>',
        'active_cameras': 'sequence<string>',
        'missing_cameras': 'sequence<string>',
        'inference_count': 'uint64',
        'message': 'string',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['std_msgs', 'msg'], 'Header'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.BasicType('uint64'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
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
        from std_msgs.msg import Header
        self.header = kwargs.get('header', Header())
        self.ready = kwargs.get('ready', bool())
        self.model_loaded = kwargs.get('model_loaded', bool())
        self.cameras = kwargs.get('cameras', [])
        self.active_cameras = kwargs.get('active_cameras', [])
        self.missing_cameras = kwargs.get('missing_cameras', [])
        self.inference_count = kwargs.get('inference_count', int())
        self.message = kwargs.get('message', str())

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
        if self.header != other.header:
            return False
        if self.ready != other.ready:
            return False
        if self.model_loaded != other.model_loaded:
            return False
        if self.cameras != other.cameras:
            return False
        if self.active_cameras != other.active_cameras:
            return False
        if self.missing_cameras != other.missing_cameras:
            return False
        if self.inference_count != other.inference_count:
            return False
        if self.message != other.message:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def header(self):
        """Message field 'header'."""
        return self._header

    @header.setter
    def header(self, value):
        if self._check_fields:
            from std_msgs.msg import Header
            assert \
                isinstance(value, Header), \
                "The 'header' field must be a sub message of type 'Header'"
        self._header = value

    @builtins.property
    def ready(self):
        """Message field 'ready'."""
        return self._ready

    @ready.setter
    def ready(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'ready' field must be of type 'bool'"
        self._ready = value

    @builtins.property
    def model_loaded(self):
        """Message field 'model_loaded'."""
        return self._model_loaded

    @model_loaded.setter
    def model_loaded(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'model_loaded' field must be of type 'bool'"
        self._model_loaded = value

    @builtins.property
    def cameras(self):
        """Message field 'cameras'."""
        return self._cameras

    @cameras.setter
    def cameras(self, value):
        if self._check_fields:
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
                 all(isinstance(v, str) for v in value) and
                 True), \
                "The 'cameras' field must be a set or sequence and each value of type 'str'"
        self._cameras = value

    @builtins.property
    def active_cameras(self):
        """Message field 'active_cameras'."""
        return self._active_cameras

    @active_cameras.setter
    def active_cameras(self, value):
        if self._check_fields:
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
                 all(isinstance(v, str) for v in value) and
                 True), \
                "The 'active_cameras' field must be a set or sequence and each value of type 'str'"
        self._active_cameras = value

    @builtins.property
    def missing_cameras(self):
        """Message field 'missing_cameras'."""
        return self._missing_cameras

    @missing_cameras.setter
    def missing_cameras(self, value):
        if self._check_fields:
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
                 all(isinstance(v, str) for v in value) and
                 True), \
                "The 'missing_cameras' field must be a set or sequence and each value of type 'str'"
        self._missing_cameras = value

    @builtins.property
    def inference_count(self):
        """Message field 'inference_count'."""
        return self._inference_count

    @inference_count.setter
    def inference_count(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'inference_count' field must be of type 'int'"
            assert value >= 0 and value < 18446744073709551616, \
                "The 'inference_count' field must be an unsigned integer in [0, 18446744073709551615]"
        self._inference_count = value

    @builtins.property
    def message(self):
        """Message field 'message'."""
        return self._message

    @message.setter
    def message(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'message' field must be of type 'str'"
        self._message = value
