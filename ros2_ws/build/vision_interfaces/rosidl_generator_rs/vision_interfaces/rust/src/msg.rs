#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



// Corresponds to vision_interfaces__msg__Part

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Part {

    // This member is not documented.
    #[allow(missing_docs)]
    pub name: std::string::String,


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
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::Part::default())
  }
}

impl rosidl_runtime_rs::Message for Part {
  type RmwMsg = super::msg::rmw::Part;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        name: msg.name.as_str().into(),
        class_id: msg.class_id,
        score: msg.score,
        x: msg.x,
        y: msg.y,
        width: msg.width,
        height: msg.height,
        angle_deg: msg.angle_deg,
        angle_valid: msg.angle_valid,
        depth_m: msg.depth_m,
        depth_valid: msg.depth_valid,
        camera_x_m: msg.camera_x_m,
        camera_y_m: msg.camera_y_m,
        camera_z_m: msg.camera_z_m,
        position_valid: msg.position_valid,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        name: msg.name.as_str().into(),
      class_id: msg.class_id,
      score: msg.score,
      x: msg.x,
      y: msg.y,
      width: msg.width,
      height: msg.height,
      angle_deg: msg.angle_deg,
      angle_valid: msg.angle_valid,
      depth_m: msg.depth_m,
      depth_valid: msg.depth_valid,
      camera_x_m: msg.camera_x_m,
      camera_y_m: msg.camera_y_m,
      camera_z_m: msg.camera_z_m,
      position_valid: msg.position_valid,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      name: msg.name.to_string(),
      class_id: msg.class_id,
      score: msg.score,
      x: msg.x,
      y: msg.y,
      width: msg.width,
      height: msg.height,
      angle_deg: msg.angle_deg,
      angle_valid: msg.angle_valid,
      depth_m: msg.depth_m,
      depth_valid: msg.depth_valid,
      camera_x_m: msg.camera_x_m,
      camera_y_m: msg.camera_y_m,
      camera_z_m: msg.camera_z_m,
      position_valid: msg.position_valid,
    }
  }
}


// Corresponds to vision_interfaces__msg__Detections

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Detections {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub image_width: u32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub image_height: u32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub parts: Vec<super::msg::Part>,

}



impl Default for Detections {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::Detections::default())
  }
}

impl rosidl_runtime_rs::Message for Detections {
  type RmwMsg = super::msg::rmw::Detections;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        camera: msg.camera.as_str().into(),
        image_width: msg.image_width,
        image_height: msg.image_height,
        parts: msg.parts
          .into_iter()
          .map(|elem| super::msg::Part::into_rmw_message(std::borrow::Cow::Owned(elem)).into_owned())
          .collect(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
        camera: msg.camera.as_str().into(),
      image_width: msg.image_width,
      image_height: msg.image_height,
        parts: msg.parts
          .iter()
          .map(|elem| super::msg::Part::into_rmw_message(std::borrow::Cow::Borrowed(elem)).into_owned())
          .collect(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      camera: msg.camera.to_string(),
      image_width: msg.image_width,
      image_height: msg.image_height,
      parts: msg.parts
          .into_iter()
          .map(super::msg::Part::from_rmw_message)
          .collect(),
    }
  }
}


// Corresponds to vision_interfaces__msg__Inspection

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Inspection {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub camera: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub board_id: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub recipe_id: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub status: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub expected_total: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub found_total: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub names: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub expected: Vec<i32>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub found: Vec<i32>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub slot_ids: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub slot_status: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub errors: Vec<std::string::String>,

}



impl Default for Inspection {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::Inspection::default())
  }
}

impl rosidl_runtime_rs::Message for Inspection {
  type RmwMsg = super::msg::rmw::Inspection;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        camera: msg.camera.as_str().into(),
        board_id: msg.board_id.as_str().into(),
        recipe_id: msg.recipe_id.as_str().into(),
        status: msg.status.as_str().into(),
        expected_total: msg.expected_total,
        found_total: msg.found_total,
        names: msg.names
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        expected: msg.expected.into(),
        found: msg.found.into(),
        slot_ids: msg.slot_ids
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        slot_status: msg.slot_status
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        errors: msg.errors
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
        camera: msg.camera.as_str().into(),
        board_id: msg.board_id.as_str().into(),
        recipe_id: msg.recipe_id.as_str().into(),
        status: msg.status.as_str().into(),
      expected_total: msg.expected_total,
      found_total: msg.found_total,
        names: msg.names
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        expected: msg.expected.as_slice().into(),
        found: msg.found.as_slice().into(),
        slot_ids: msg.slot_ids
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        slot_status: msg.slot_status
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        errors: msg.errors
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      camera: msg.camera.to_string(),
      board_id: msg.board_id.to_string(),
      recipe_id: msg.recipe_id.to_string(),
      status: msg.status.to_string(),
      expected_total: msg.expected_total,
      found_total: msg.found_total,
      names: msg.names
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      expected: msg.expected
          .into_iter()
          .collect(),
      found: msg.found
          .into_iter()
          .collect(),
      slot_ids: msg.slot_ids
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      slot_status: msg.slot_status
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      errors: msg.errors
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
    }
  }
}


// Corresponds to vision_interfaces__msg__VisionStatus

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct VisionStatus {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub ready: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub model_loaded: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub cameras: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub active_cameras: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub missing_cameras: Vec<std::string::String>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub inference_count: u64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: std::string::String,

}



impl Default for VisionStatus {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::VisionStatus::default())
  }
}

impl rosidl_runtime_rs::Message for VisionStatus {
  type RmwMsg = super::msg::rmw::VisionStatus;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        ready: msg.ready,
        model_loaded: msg.model_loaded,
        cameras: msg.cameras
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        active_cameras: msg.active_cameras
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        missing_cameras: msg.missing_cameras
          .into_iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        inference_count: msg.inference_count,
        message: msg.message.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
      ready: msg.ready,
      model_loaded: msg.model_loaded,
        cameras: msg.cameras
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        active_cameras: msg.active_cameras
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
        missing_cameras: msg.missing_cameras
          .iter()
          .map(|elem| elem.as_str().into())
          .collect(),
      inference_count: msg.inference_count,
        message: msg.message.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      ready: msg.ready,
      model_loaded: msg.model_loaded,
      cameras: msg.cameras
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      active_cameras: msg.active_cameras
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      missing_cameras: msg.missing_cameras
          .into_iter()
          .map(|elem| elem.to_string())
          .collect(),
      inference_count: msg.inference_count,
      message: msg.message.to_string(),
    }
  }
}


