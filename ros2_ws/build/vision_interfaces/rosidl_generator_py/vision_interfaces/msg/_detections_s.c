// generated from rosidl_generator_py/resource/_idl_support.c.em
// with input from vision_interfaces:msg/Detections.idl
// generated code does not contain a copyright notice
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <stdbool.h>
#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-function"
#endif
#include "numpy/ndarrayobject.h"
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif
#include "rosidl_runtime_c/visibility_control.h"
#include "vision_interfaces/msg/detail/detections__struct.h"
#include "vision_interfaces/msg/detail/detections__functions.h"

#include "rosidl_runtime_c/string.h"
#include "rosidl_runtime_c/string_functions.h"

#include "rosidl_runtime_c/primitives_sequence.h"
#include "rosidl_runtime_c/primitives_sequence_functions.h"

// Nested array functions includes
#include "vision_interfaces/msg/detail/part__functions.h"
// end nested array functions include
ROSIDL_GENERATOR_C_IMPORT
bool std_msgs__msg__header__convert_from_py(PyObject * _pymsg, void * _ros_message);
ROSIDL_GENERATOR_C_IMPORT
PyObject * std_msgs__msg__header__convert_to_py(void * raw_ros_message);
bool vision_interfaces__msg__part__convert_from_py(PyObject * _pymsg, void * _ros_message);
PyObject * vision_interfaces__msg__part__convert_to_py(void * raw_ros_message);

ROSIDL_GENERATOR_C_EXPORT
bool vision_interfaces__msg__detections__convert_from_py(PyObject * _pymsg, void * _ros_message)
{
  // check that the passed message is of the expected Python class
  {
    char full_classname_dest[45];
    {
      char * class_name = NULL;
      char * module_name = NULL;
      {
        PyObject * class_attr = PyObject_GetAttrString(_pymsg, "__class__");
        if (class_attr) {
          PyObject * name_attr = PyObject_GetAttrString(class_attr, "__name__");
          if (name_attr) {
            class_name = (char *)PyUnicode_1BYTE_DATA(name_attr);
            Py_DECREF(name_attr);
          }
          PyObject * module_attr = PyObject_GetAttrString(class_attr, "__module__");
          if (module_attr) {
            module_name = (char *)PyUnicode_1BYTE_DATA(module_attr);
            Py_DECREF(module_attr);
          }
          Py_DECREF(class_attr);
        }
      }
      if (!class_name || !module_name) {
        return false;
      }
      snprintf(full_classname_dest, sizeof(full_classname_dest), "%s.%s", module_name, class_name);
    }
    assert(strncmp("vision_interfaces.msg._detections.Detections", full_classname_dest, 44) == 0);
  }
  vision_interfaces__msg__Detections * ros_message = _ros_message;
  {  // header
    PyObject * field = PyObject_GetAttrString(_pymsg, "header");
    if (!field) {
      return false;
    }
    if (!std_msgs__msg__header__convert_from_py(field, &ros_message->header)) {
      Py_DECREF(field);
      return false;
    }
    Py_DECREF(field);
  }
  {  // camera
    PyObject * field = PyObject_GetAttrString(_pymsg, "camera");
    if (!field) {
      return false;
    }
    assert(PyUnicode_Check(field));
    PyObject * encoded_field = PyUnicode_AsUTF8String(field);
    if (!encoded_field) {
      Py_DECREF(field);
      return false;
    }
    rosidl_runtime_c__String__assign(&ros_message->camera, PyBytes_AS_STRING(encoded_field));
    Py_DECREF(encoded_field);
    Py_DECREF(field);
  }
  {  // image_width
    PyObject * field = PyObject_GetAttrString(_pymsg, "image_width");
    if (!field) {
      return false;
    }
    assert(PyLong_Check(field));
    ros_message->image_width = PyLong_AsUnsignedLong(field);
    Py_DECREF(field);
  }
  {  // image_height
    PyObject * field = PyObject_GetAttrString(_pymsg, "image_height");
    if (!field) {
      return false;
    }
    assert(PyLong_Check(field));
    ros_message->image_height = PyLong_AsUnsignedLong(field);
    Py_DECREF(field);
  }
  {  // parts
    PyObject * field = PyObject_GetAttrString(_pymsg, "parts");
    if (!field) {
      return false;
    }
    PyObject * seq_field = PySequence_Fast(field, "expected a sequence in 'parts'");
    if (!seq_field) {
      Py_DECREF(field);
      return false;
    }
    Py_ssize_t size = PySequence_Size(field);
    if (-1 == size) {
      Py_DECREF(seq_field);
      Py_DECREF(field);
      return false;
    }
    if (!vision_interfaces__msg__Part__Sequence__init(&(ros_message->parts), size)) {
      PyErr_SetString(PyExc_RuntimeError, "unable to create vision_interfaces__msg__Part__Sequence ros_message");
      Py_DECREF(seq_field);
      Py_DECREF(field);
      return false;
    }
    vision_interfaces__msg__Part * dest = ros_message->parts.data;
    for (Py_ssize_t i = 0; i < size; ++i) {
      if (!vision_interfaces__msg__part__convert_from_py(PySequence_Fast_GET_ITEM(seq_field, i), &dest[i])) {
        Py_DECREF(seq_field);
        Py_DECREF(field);
        return false;
      }
    }
    Py_DECREF(seq_field);
    Py_DECREF(field);
  }

  return true;
}

ROSIDL_GENERATOR_C_EXPORT
PyObject * vision_interfaces__msg__detections__convert_to_py(void * raw_ros_message)
{
  /* NOTE(esteve): Call constructor of Detections */
  PyObject * _pymessage = NULL;
  {
    PyObject * pymessage_module = PyImport_ImportModule("vision_interfaces.msg._detections");
    assert(pymessage_module);
    PyObject * pymessage_class = PyObject_GetAttrString(pymessage_module, "Detections");
    assert(pymessage_class);
    Py_DECREF(pymessage_module);
    _pymessage = PyObject_CallObject(pymessage_class, NULL);
    Py_DECREF(pymessage_class);
    if (!_pymessage) {
      return NULL;
    }
  }
  vision_interfaces__msg__Detections * ros_message = (vision_interfaces__msg__Detections *)raw_ros_message;
  {  // header
    PyObject * field = NULL;
    field = std_msgs__msg__header__convert_to_py(&ros_message->header);
    if (!field) {
      return NULL;
    }
    {
      int rc = PyObject_SetAttrString(_pymessage, "header", field);
      Py_DECREF(field);
      if (rc) {
        return NULL;
      }
    }
  }
  {  // camera
    PyObject * field = NULL;
    field = PyUnicode_DecodeUTF8(
      ros_message->camera.data,
      strlen(ros_message->camera.data),
      "replace");
    if (!field) {
      return NULL;
    }
    {
      int rc = PyObject_SetAttrString(_pymessage, "camera", field);
      Py_DECREF(field);
      if (rc) {
        return NULL;
      }
    }
  }
  {  // image_width
    PyObject * field = NULL;
    field = PyLong_FromUnsignedLong(ros_message->image_width);
    {
      int rc = PyObject_SetAttrString(_pymessage, "image_width", field);
      Py_DECREF(field);
      if (rc) {
        return NULL;
      }
    }
  }
  {  // image_height
    PyObject * field = NULL;
    field = PyLong_FromUnsignedLong(ros_message->image_height);
    {
      int rc = PyObject_SetAttrString(_pymessage, "image_height", field);
      Py_DECREF(field);
      if (rc) {
        return NULL;
      }
    }
  }
  {  // parts
    PyObject * field = NULL;
    size_t size = ros_message->parts.size;
    field = PyList_New(size);
    if (!field) {
      return NULL;
    }
    vision_interfaces__msg__Part * item;
    for (size_t i = 0; i < size; ++i) {
      item = &(ros_message->parts.data[i]);
      PyObject * pyitem = vision_interfaces__msg__part__convert_to_py(item);
      if (!pyitem) {
        Py_DECREF(field);
        return NULL;
      }
      int rc = PyList_SetItem(field, i, pyitem);
      (void)rc;
      assert(rc == 0);
    }
    assert(PySequence_Check(field));
    {
      int rc = PyObject_SetAttrString(_pymessage, "parts", field);
      Py_DECREF(field);
      if (rc) {
        return NULL;
      }
    }
  }

  // ownership of _pymessage is transferred to the caller
  return _pymessage;
}
