# S22 USB high-quality camera

The only supported S22 camera path uses official scrcpy 4.1 camera streaming
over USB. The current measured stable high-quality profile uses the S22 rear
main camera at 1920x1080, 30 FPS with H.264 at 30 Mbps. Every fresh camera
frame wakes the control publisher immediately; it is not sampled by a second
30 Hz timer. The live control view is 960x540 JPEG 84 at a target 30 FPS;
the reduced packet size keeps stop status delivery responsive over DDS.

The subscriber-activated 1920x1080 JPEG 95 analysis topic runs in another
thread and is capped at 5 FPS, so opening it cannot queue old control frames.
Precise AOI does not use either overview topic: the managed optical capture
pauses scrcpy and saves a separate 4000x3000 Samsung Camera telephoto JPEG.

Install the project-local official release once:

```bash
~/KSMC/camera2_scrcpy/install_scrcpy.sh
```

Run the camera and conveyor overlay together:

```bash
~/KSMC/run_s22_conveyor_hq.sh
```

Topics and service:

```text
/camera2/image_stream/compressed           960x540 JPEG 84, ~30 FPS live view
/camera2/image_raw/compressed              1920x1080 JPEG 95, max 5 FPS analysis
/vision/conveyor/stop_image/compressed     stop-line overlay (recalibration pending)
/camera2/inspection_frame/compressed       one 1080p overview PNG on request
/camera2/capture_inspection_frame          std_srvs/srv/Trigger
```

All three compressed viewer topics (`/camera2/image_stream/compressed`,
`/camera2/image_raw/compressed`, and `/camera2/inspection_frame/compressed`)
offer the sensor-data `BEST_EFFORT`, `KEEP_LAST(1)`, `VOLATILE` QoS used by
rqt_image_view, the ROI node, and the ROS-TCP Endpoint. Keeping one newest
sample avoids stale JPEG replay and network backpressure. The uncompressed
`Image`/`CameraInfo` sensor paths use the same best-effort profile.

For `rqt_image_view`, select the base topics `/camera2/image_stream`,
`/camera3/image_raw`, or `/vision/conveyor/stop_image` and set the image
transport to `compressed` in the plugin. Do not pass the `/compressed` suffix
as the plugin's base topic: rqt then creates a `sensor_msgs/msg/Image`
subscription on a `sensor_msgs/msg/CompressedImage` topic, so the topic is
listed but no frame can be decoded. Direct ROS tools and Unity should continue
to use the full compressed names shown above. The GoPro compressed publisher
uses the same best-effort depth-one viewer profile.

When viewing from another computer, source the cell environment before
starting rqt so it joins the same ROS subnet:

```bash
source /opt/ros/jazzy/setup.bash
source ~/KSMC/scripts/ksmc_env.sh
export ROS_DOMAIN_ID=5
export ROS_LOCALHOST_ONLY=0
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
ros2 run rqt_image_view rqt_image_view
```

The remote viewer must then show an active `rqt_gui_cpp_node` subscription in
`ros2 topic info -v` for the selected compressed topic. If the topic is listed
but the subscription count stays zero, rqt is using the wrong base/transport or
is not in the same ROS domain; if a subscription is present but no frames
arrive, compare the DDS interface/firewall on that computer.

Capture one inspection frame while the PCB is stationary:

```bash
ros2 service call /camera2/capture_inspection_frame std_srvs/srv/Trigger '{}'
```

The PNG is saved under `~/KSMC/runtime/inspection`. This service preserves the
current overview frame but does not switch to the S22 telephoto lens.

During camera-position adjustment, use `/camera2/image_stream/compressed` for
the clean live view. Open the Full-HD analysis topic only while the belt is
stationary; it is deliberately limited to 5 FPS and is not the control display.
After the phone position and stop lines are recalibrated, the conveyor stop
detector must still be revalidated at the real belt speed.

The stop detector publishes trigger and ready status before drawing the optional
dashboard. A source frame older than the configured 0.15 seconds is ignored for
new stop/arrival evidence; that delay alone does not create a liveness fault.
The motion controller stops on explicit `ready=false`, a stop trigger, or its
finite motion timeout. A camera or viewer stall therefore cannot create a
false status fault, while a move with no visual trigger still ends at timeout.

The conveyor overview uses a 1.5x main-camera zoom. On this
SM-S901N, scrcpy `--camera-zoom=3.0` remains on the main physical camera and is
only a digital crop. Do not use it as an optical inspection image.

Capture an inspection photo with Samsung Camera. The default is 3.5x, which
keeps the whole PCB visible at the current inspection position:

```bash
~/KSMC/run_s22_optical_inspection.sh
```

Select another framing value explicitly when required:

```bash
S22_INSPECTION_ZOOM=3.0 ~/KSMC/run_s22_optical_inspection.sh
S22_INSPECTION_ZOOM=3.5 ~/KSMC/run_s22_optical_inspection.sh
S22_INSPECTION_ZOOM=4.7 ~/KSMC/run_s22_optical_inspection.sh
```

The 3.5x, 4.0x, and 4.7x modes first activate the true 3x telephoto lens and then
apply Samsung Camera's additional capture-time zoom. They do not crop the
saved image after capture, but only the 3x portion is optical.

When the managed HQ conveyor launcher is active, this command pauses only the
S22 overview stream, selects Samsung's true 3x telephoto camera, captures and
pulls the full-resolution JPEG, closes Samsung Camera, and restores the
overview automatically. The conveyor ROI node remains alive while frames are
temporarily paused. Images are stored in `~/KSMC/runtime/inspection`, and
`s22_telephoto_latest.jpg` points to the newest one.

The capture verifies the EXIF focal length. A valid S22 3x result is normally
4000x3000 with a 7.0 mm physical focal length and 69 mm full-frame equivalent.
The phone must remain unlocked, USB debugging must be authorized, and Samsung
Camera must retain its normal portrait control layout.

After each telephoto capture, the dark PCB body is detected, the fixture handle
is excluded, and the four board corners are perspective-rectified to a
1600x1266 lossless PNG using the physical 139x110 board ratio. The rectified
ROI is also rotated 180 degrees to match the upright rqt inspection view. The
newest files are available at:

```text
~/KSMC/runtime/inspection/s22_telephoto_upright_latest.png
~/KSMC/runtime/inspection/s22_inspection_roi_latest.png
~/KSMC/runtime/inspection/s22_inspection_roi_debug_latest.jpg
~/KSMC/runtime/inspection/s22_inspection_roi_latest.json
```

Reprocess the newest photo without taking another picture:

```bash
~/KSMC/run_s22_inspection_roi.sh
```

Set `S22_EXTRACT_INSPECTION_ROI=0` only when a telephoto photo is intentionally
captured without a PCB.

The phone JPEG is retained unchanged as optical evidence. The upright full
photo is a lossless PNG made after applying EXIF orientation and the required
180-degree operator-view correction. If any detected PCB corner touches the
photo boundary, the raw and upright photos are kept but the unsafe ROI is not
accepted as the newest inspection ROI.
