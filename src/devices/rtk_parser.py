from __future__ import annotations

from typing import Dict, Optional

GPCHC_FIELDS = [
    "header",
    "gps_week",
    "gps_time",
    "heading",
    "pitch",
    "roll",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "acc_x",
    "acc_y",
    "acc_z",
    "latitude",
    "longitude",
    "altitude",
    "ve",
    "vn",
    "vu",
    "vehicle_speed",
    "nsv1",
    "nsv2",
    "status",
    "age",
    "warning",
]


class GpchcParser:
    @staticmethod
    def parse(line: str) -> Optional[Dict[str, object]]:
        raw = line.strip()
        if not raw.startswith("$GPCHC"):
            return None

        parts = raw.split(",")
        if len(parts) < 24:
            return None

        warning = parts[23].split("*")[0]
        values = parts[:23] + [warning]
        try:
            return {
                "header": values[0],
                "gps_week": int(values[1]),
                "gps_time": float(values[2]),
                "heading": float(values[3]),
                "pitch": float(values[4]),
                "roll": float(values[5]),
                "gyro_x": float(values[6]),
                "gyro_y": float(values[7]),
                "gyro_z": float(values[8]),
                "acc_x": float(values[9]),
                "acc_y": float(values[10]),
                "acc_z": float(values[11]),
                "latitude": float(values[12]),
                "longitude": float(values[13]),
                "altitude": float(values[14]),
                "ve": float(values[15]),
                "vn": float(values[16]),
                "vu": float(values[17]),
                "vehicle_speed": float(values[18]),
                "nsv1": int(values[19]),
                "nsv2": int(values[20]),
                "status": int(values[21]),
                "age": int(values[22]),
                "warning": int(values[23]),
            }
        except ValueError:
            return None
