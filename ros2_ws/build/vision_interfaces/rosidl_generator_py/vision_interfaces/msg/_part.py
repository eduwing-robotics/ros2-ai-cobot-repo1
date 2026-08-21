# generated from rosidl_generator_py/resource/_idl.py.em
# with input from vision_interfaces:msg/Part.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import math  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_Part(type):
    """Metaclass of message 'Part'."""

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
                'vision_interfaces.msg.Part')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__part
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__part
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__part
            cls._TYPE_SUPPORT = module.type_support_msg__msg__part
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__part

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class Part(metaclass=Metaclass_Part):
    """Message class 'Part'."""

    __slots__ = [
        '_name',
        '_class_id',
        '_score',
        '_x',
        '_y',
        '_width',
        '_height',
        '_angle_deg',
        '_angle_valid',
        '_depth_m',
        '_depth_valid',
        '_camera_x_m',
        '_camera_y_m',
        '_camera_z_m',
        '_position_valid',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'name': 'string',
        'class_id': 'int32',
        'score': 'float',
        'x': 'int32',
        'y': 'int32',
        'width': 'int32',
        'height': 'int32',
        'angle_deg': 'float',
        'angle_valid': 'boolean',
        'depth_m': 'float',
        'depth_valid': 'boolean',
        'camera_x_m': 'float',
        'camera_y_m': 'float',
        'camera_z_m': 'float',
        'position_valid': 'boolean',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('float'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
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
        self.name = kwargs.get('name', str())
        self.class_id = kwargs.get('class_id', int())
        self.score = kwargs.get('score', float())
        self.x = kwargs.get('x', int())
        self.y = kwargs.get('y', int())
        self.width = kwargs.get('width', int())
        self.height = kwargs.get('height', int())
        self.angle_deg = kwargs.get('angle_deg', float())
        self.angle_valid = kwargs.get('angle_valid', bool())
        self.depth_m = kwargs.get('depth_m', float())
        self.depth_valid = kwargs.get('depth_valid', bool())
        self.camera_x_m = kwargs.get('camera_x_m', float())
        self.camera_y_m = kwargs.get('camera_y_m', float())
        self.camera_z_m = kwargs.get('camera_z_m', float())
        self.position_valid = kwargs.get('position_valid', bool())

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
        if self.name != other.name:
            return False
        if self.class_id != other.class_id:
            return False
        if self.score != other.score:
            return False
        if self.x != other.x:
            return False
        if self.y != other.y:
            return False
        if self.width != other.width:
            return False
        if self.height != other.height:
            return False
        if self.angle_deg != other.angle_deg:
            return False
        if self.angle_valid != other.angle_valid:
            return False
        if self.depth_m != other.depth_m:
            return False
        if self.depth_valid != other.depth_valid:
            return False
        if self.camera_x_m != other.camera_x_m:
            return False
        if self.camera_y_m != other.camera_y_m:
            return False
        if self.camera_z_m != other.camera_z_m:
            return False
        if self.position_valid != other.position_valid:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def name(self):
        """Message field 'name'."""
        return self._name

    @name.setter
    def name(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'name' field must be of type 'str'"
        self._name = value

    @builtins.property
    def class_id(self):
        """Message field 'class_id'."""
        return self._class_id

    @class_id.setter
    def class_id(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'class_id' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'class_id' field must be an integer in [-2147483648, 2147483647]"
        self._class_id = value

    @builtins.property
    def score(self):
        """Message field 'score'."""
        return self._score

    @score.setter
    def score(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'score' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'score' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._score = value

    @builtins.property
    def x(self):
        """Message field 'x'."""
        return self._x

    @x.setter
    def x(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'x' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'x' field must be an integer in [-2147483648, 2147483647]"
        self._x = value

    @builtins.property
    def y(self):
        """Message field 'y'."""
        return self._y

    @y.setter
    def y(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'y' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'y' field must be an integer in [-2147483648, 2147483647]"
        self._y = value

    @builtins.property
    def width(self):
        """Message field 'width'."""
        return self._width

    @width.setter
    def width(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'width' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'width' field must be an integer in [-2147483648, 2147483647]"
        self._width = value

    @builtins.property
    def height(self):
        """Message field 'height'."""
        return self._height

    @height.setter
    def height(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'height' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'height' field must be an integer in [-2147483648, 2147483647]"
        self._height = value

    @builtins.property
    def angle_deg(self):
        """Message field 'angle_deg'."""
        return self._angle_deg

    @angle_deg.setter
    def angle_deg(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'angle_deg' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'angle_deg' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._angle_deg = value

    @builtins.property
    def angle_valid(self):
        """Message field 'angle_valid'."""
        return self._angle_valid

    @angle_valid.setter
    def angle_valid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'angle_valid' field must be of type 'bool'"
        self._angle_valid = value

    @builtins.property
    def depth_m(self):
        """Message field 'depth_m'."""
        return self._depth_m

    @depth_m.setter
    def depth_m(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'depth_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'depth_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._depth_m = value

    @builtins.property
    def depth_valid(self):
        """Message field 'depth_valid'."""
        return self._depth_valid

    @depth_valid.setter
    def depth_valid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'depth_valid' field must be of type 'bool'"
        self._depth_valid = value

    @builtins.property
    def camera_x_m(self):
        """Message field 'camera_x_m'."""
        return self._camera_x_m

    @camera_x_m.setter
    def camera_x_m(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'camera_x_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'camera_x_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._camera_x_m = value

    @builtins.property
    def camera_y_m(self):
        """Message field 'camera_y_m'."""
        return self._camera_y_m

    @camera_y_m.setter
    def camera_y_m(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'camera_y_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'camera_y_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._camera_y_m = value

    @builtins.property
    def camera_z_m(self):
        """Message field 'camera_z_m'."""
        return self._camera_z_m

    @camera_z_m.setter
    def camera_z_m(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'camera_z_m' field must be of type 'float'"
            assert not (value < -3.402823466e+38 or value > 3.402823466e+38) or math.isinf(value), \
                "The 'camera_z_m' field must be a float in [-3.402823466e+38, 3.402823466e+38]"
        self._camera_z_m = value

    @builtins.property
    def position_valid(self):
        """Message field 'position_valid'."""
        return self._position_valid

    @position_valid.setter
    def position_valid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'position_valid' field must be of type 'bool'"
        self._position_valid = value
