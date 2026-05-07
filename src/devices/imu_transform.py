from __future__ import annotations


def axis_to_angle_key(axis_name: str) -> str:
    mapping = {
        "X": "angle_x_deg",
        "Y": "angle_y_deg",
        "Z": "angle_z_deg",
        "angle_x": "angle_x_deg",
        "angle_y": "angle_y_deg",
        "angle_z": "angle_z_deg",
        "angle_x_deg": "angle_x_deg",
        "angle_y_deg": "angle_y_deg",
        "angle_z_deg": "angle_z_deg",
    }
    return mapping.get(axis_name, "angle_z_deg")


def compute_steering_angle(raw_angle_deg: float, zero_offset_deg: float, inverted: bool = False) -> float:
    sign = -1.0 if inverted else 1.0
    return (raw_angle_deg - zero_offset_deg) * sign
