#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};


#[link(name = "vision_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Part() -> *const std::ffi::c_void;
}

#[link(name = "vision_interfaces__rosidl_generator_c")]
extern "C" {
    fn vision_interfaces__msg__Part__init(msg: *mut Part) -> bool;
    fn vision_interfaces__msg__Part__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<Part>, size: usize) -> bool;
    fn vision_interfaces__msg__Part__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<Part>);
    fn vision_interfaces__msg__Part__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<Part>, out_seq: *mut rosidl_runtime_rs::Sequence<Part>) -> bool;
}

// Corresponds to vision_interfaces__msg__Part
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Part {

    // This member is not documented.
    #[allow(missing_docs)]
    pub name: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub class_id: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub score: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub x: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub y: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub width: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub height: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub angle_deg: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub angle_valid: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub depth_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub depth_valid: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera_x_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera_y_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera_z_m: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position_valid: bool,

}



impl Default for Part {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !vision_interfaces__msg__Part__init(&mut msg as *mut _) {
        panic!("Call to vision_interfaces__msg__Part__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for Part {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Part__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Part__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Part__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for Part {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for Part where Self: Sized {
  const TYPE_NAME: &'static str = "vision_interfaces/msg/Part";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Part() }
  }
}


#[link(name = "vision_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Detections() -> *const std::ffi::c_void;
}

#[link(name = "vision_interfaces__rosidl_generator_c")]
extern "C" {
    fn vision_interfaces__msg__Detections__init(msg: *mut Detections) -> bool;
    fn vision_interfaces__msg__Detections__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<Detections>, size: usize) -> bool;
    fn vision_interfaces__msg__Detections__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<Detections>);
    fn vision_interfaces__msg__Detections__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<Detections>, out_seq: *mut rosidl_runtime_rs::Sequence<Detections>) -> bool;
}

// Corresponds to vision_interfaces__msg__Detections
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Detections {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::rmw::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub image_width: u32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub image_height: u32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub parts: rosidl_runtime_rs::Sequence<super::super::msg::rmw::Part>,

}



impl Default for Detections {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !vision_interfaces__msg__Detections__init(&mut msg as *mut _) {
        panic!("Call to vision_interfaces__msg__Detections__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for Detections {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Detections__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Detections__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Detections__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for Detections {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for Detections where Self: Sized {
  const TYPE_NAME: &'static str = "vision_interfaces/msg/Detections";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Detections() }
  }
}


#[link(name = "vision_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Inspection() -> *const std::ffi::c_void;
}

#[link(name = "vision_interfaces__rosidl_generator_c")]
extern "C" {
    fn vision_interfaces__msg__Inspection__init(msg: *mut Inspection) -> bool;
    fn vision_interfaces__msg__Inspection__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<Inspection>, size: usize) -> bool;
    fn vision_interfaces__msg__Inspection__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<Inspection>);
    fn vision_interfaces__msg__Inspection__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<Inspection>, out_seq: *mut rosidl_runtime_rs::Sequence<Inspection>) -> bool;
}

// Corresponds to vision_interfaces__msg__Inspection
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Inspection {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::rmw::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub board_id: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub recipe_id: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub status: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub expected_total: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub found_total: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub names: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub expected: rosidl_runtime_rs::Sequence<i32>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub found: rosidl_runtime_rs::Sequence<i32>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub slot_ids: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub slot_status: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub errors: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,

}



impl Default for Inspection {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !vision_interfaces__msg__Inspection__init(&mut msg as *mut _) {
        panic!("Call to vision_interfaces__msg__Inspection__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for Inspection {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Inspection__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Inspection__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__Inspection__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for Inspection {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for Inspection where Self: Sized {
  const TYPE_NAME: &'static str = "vision_interfaces/msg/Inspection";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__Inspection() }
  }
}


#[link(name = "vision_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__VisionStatus() -> *const std::ffi::c_void;
}

#[link(name = "vision_interfaces__rosidl_generator_c")]
extern "C" {
    fn vision_interfaces__msg__VisionStatus__init(msg: *mut VisionStatus) -> bool;
    fn vision_interfaces__msg__VisionStatus__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<VisionStatus>, size: usize) -> bool;
    fn vision_interfaces__msg__VisionStatus__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<VisionStatus>);
    fn vision_interfaces__msg__VisionStatus__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<VisionStatus>, out_seq: *mut rosidl_runtime_rs::Sequence<VisionStatus>) -> bool;
}

// Corresponds to vision_interfaces__msg__VisionStatus
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct VisionStatus {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::rmw::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub ready: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub model_loaded: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub cameras: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub active_cameras: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub missing_cameras: rosidl_runtime_rs::Sequence<rosidl_runtime_rs::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub inference_count: u64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: rosidl_runtime_rs::String,

}



impl Default for VisionStatus {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !vision_interfaces__msg__VisionStatus__init(&mut msg as *mut _) {
        panic!("Call to vision_interfaces__msg__VisionStatus__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for VisionStatus {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__VisionStatus__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__VisionStatus__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { vision_interfaces__msg__VisionStatus__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for VisionStatus {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for VisionStatus where Self: Sized {
  const TYPE_NAME: &'static str = "vision_interfaces/msg/VisionStatus";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__vision_interfaces__msg__VisionStatus() }
  }
}


