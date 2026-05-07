from enum import Enum


class RunState(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RECORDING = "recording"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ClipStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class TriageStatus(str, Enum):
    UNTRIAGED = "untriaged"
    TRIAGED = "triaged"
