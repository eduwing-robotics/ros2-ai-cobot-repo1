#!/usr/bin/env python3
"""Shared ChArUco board configuration and OpenCV compatibility helpers."""

from pathlib import Path

import cv2
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "charuco_board.yaml"


def load_config():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    dictionary_id = getattr(cv2.aruco, config["dictionary"])
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    board = cv2.aruco.CharucoBoard_create(
        int(config["squares_x"]),
        int(config["squares_y"]),
        float(config["square_length_m"]),
        float(config["marker_length_m"]),
        dictionary,
    )
    return config, dictionary, board


def detector_parameters():
    if hasattr(cv2.aruco, "DetectorParameters_create"):
        return cv2.aruco.DetectorParameters_create()
    return cv2.aruco.DetectorParameters()


def detect_markers(gray, dictionary, parameters):
    if hasattr(cv2.aruco, "ArucoDetector"):
        return cv2.aruco.ArucoDetector(dictionary, parameters).detectMarkers(gray)
    return cv2.aruco.detectMarkers(gray, dictionary, parameters=parameters)


def detect_charuco(gray, dictionary, board, parameters, camera_matrix=None, distortion=None):
    marker_corners, marker_ids, rejected = detect_markers(gray, dictionary, parameters)
    if marker_ids is None or len(marker_ids) == 0:
        return marker_corners, marker_ids, None, None, rejected
    kwargs = {}
    if camera_matrix is not None:
        kwargs["cameraMatrix"] = camera_matrix
        kwargs["distCoeffs"] = distortion
    count, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        marker_corners, marker_ids, gray, board, **kwargs
    )
    if count is None or int(count) == 0:
        charuco_corners, charuco_ids = None, None
    return marker_corners, marker_ids, charuco_corners, charuco_ids, rejected
