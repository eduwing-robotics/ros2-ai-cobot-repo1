# generated from rosidl_generator_py/resource/_idl.py.em
# with input from vision_interfaces:msg/Inspection.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

# Member 'expected'
# Member 'found'
import array  # noqa: E402, I100

import builtins  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_Inspection(type):
    """Metaclass of message 'Inspection'."""

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
                'vision_interfaces.msg.Inspection')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__inspection
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__inspection
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__inspection
            cls._TYPE_SUPPORT = module.type_support_msg__msg__inspection
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__inspection

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


class Inspection(metaclass=Metaclass_Inspection):
    """Message class 'Inspection'."""

    __slots__ = [
        '_header',
        '_camera',
        '_board_id',
        '_recipe_id',
        '_status',
        '_expected_total',
        '_found_total',
        '_names',
        '_expected',
        '_found',
        '_slot_ids',
        '_slot_status',
        '_errors',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'header': 'std_msgs/Header',
        'camera': 'string',
        'board_id': 'string',
        'recipe_id': 'string',
        'status': 'string',
        'expected_total': 'int32',
        'found_total': 'int32',
        'names': 'sequence<string>',
        'expected': 'sequence<int32>',
        'found': 'sequence<int32>',
        'slot_ids': 'sequence<string>',
        'slot_status': 'sequence<string>',
        'errors': 'sequence<string>',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['std_msgs', 'msg'], 'Header'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.BasicType('int32'),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.BasicType('int32')),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.BasicType('int32')),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.UnboundedString()),  # noqa: E501
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
        self.camera = kwargs.get('camera', str())
        self.board_id = kwargs.get('board_id', str())
        self.recipe_id = kwargs.get('recipe_id', str())
        self.status = kwargs.get('status', str())
        self.expected_total = kwargs.get('expected_total', int())
        self.found_total = kwargs.get('found_total', int())
        self.names = kwargs.get('names', [])
        self.expected = array.array('i', kwargs.get('expected', []))
        self.found = array.array('i', kwargs.get('found', []))
        self.slot_ids = kwargs.get('slot_ids', [])
        self.slot_status = kwargs.get('slot_status', [])
        self.errors = kwargs.get('errors', [])

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
        if self.camera != other.camera:
            return False
        if self.board_id != other.board_id:
            return False
        if self.recipe_id != other.recipe_id:
            return False
        if self.status != other.status:
            return False
        if self.expected_total != other.expected_total:
            return False
        if self.found_total != other.found_total:
            return False
        if self.names != other.names:
            return False
        if self.expected != other.expected:
            return False
        if self.found != other.found:
            return False
        if self.slot_ids != other.slot_ids:
            return False
        if self.slot_status != other.slot_status:
            return False
        if self.errors != other.errors:
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
    def camera(self):
        """Message field 'camera'."""
        return self._camera

    @camera.setter
    def camera(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'camera' field must be of type 'str'"
        self._camera = value

    @builtins.property
    def board_id(self):
        """Message field 'board_id'."""
        return self._board_id

    @board_id.setter
    def board_id(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'board_id' field must be of type 'str'"
        self._board_id = value

    @builtins.property
    def recipe_id(self):
        """Message field 'recipe_id'."""
        return self._recipe_id

    @recipe_id.setter
    def recipe_id(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'recipe_id' field must be of type 'str'"
        self._recipe_id = value

    @builtins.property
    def status(self):
        """Message field 'status'."""
        return self._status

    @status.setter
    def status(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'status' field must be of type 'str'"
        self._status = value

    @builtins.property
    def expected_total(self):
        """Message field 'expected_total'."""
        return self._expected_total

    @expected_total.setter
    def expected_total(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'expected_total' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'expected_total' field must be an integer in [-2147483648, 2147483647]"
        self._expected_total = value

    @builtins.property
    def found_total(self):
        """Message field 'found_total'."""
        return self._found_total

    @found_total.setter
    def found_total(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'found_total' field must be of type 'int'"
            assert value >= -2147483648 and value < 2147483648, \
                "The 'found_total' field must be an integer in [-2147483648, 2147483647]"
        self._found_total = value

    @builtins.property
    def names(self):
        """Message field 'names'."""
        return self._names

    @names.setter
    def names(self, value):
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
                "The 'names' field must be a set or sequence and each value of type 'str'"
        self._names = value

    @builtins.property
    def expected(self):
        """Message field 'expected'."""
        return self._expected

    @expected.setter
    def expected(self, value):
        if self._check_fields:
            if isinstance(value, array.array):
                assert value.typecode == 'i', \
                    "The 'expected' array.array() must have the type code of 'i'"
                self._expected = value
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
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'expected' field must be a set or sequence and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._expected = array.array('i', value)

    @builtins.property
    def found(self):
        """Message field 'found'."""
        return self._found

    @found.setter
    def found(self, value):
        if self._check_fields:
            if isinstance(value, array.array):
                assert value.typecode == 'i', \
                    "The 'found' array.array() must have the type code of 'i'"
                self._found = value
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
                 all(isinstance(v, int) for v in value) and
                 all(val >= -2147483648 and val < 2147483648 for val in value)), \
                "The 'found' field must be a set or sequence and each value of type 'int' and each integer in [-2147483648, 2147483647]"
        self._found = array.array('i', value)

    @builtins.property
    def slot_ids(self):
        """Message field 'slot_ids'."""
        return self._slot_ids

    @slot_ids.setter
    def slot_ids(self, value):
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
                "The 'slot_ids' field must be a set or sequence and each value of type 'str'"
        self._slot_ids = value

    @builtins.property
    def slot_status(self):
        """Message field 'slot_status'."""
        return self._slot_status

    @slot_status.setter
    def slot_status(self, value):
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
                "The 'slot_status' field must be a set or sequence and each value of type 'str'"
        self._slot_status = value

    @builtins.property
    def errors(self):
        """Message field 'errors'."""
        return self._errors

    @errors.setter
    def errors(self, value):
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
                "The 'errors' field must be a set or sequence and each value of type 'str'"
        self._errors = value
