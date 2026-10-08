"""Inference giả cho sandbox — không model/GPU, chỉ giữ cờ pause như InferenceEngine."""
from __future__ import annotations

import threading


class SandboxInference:
    def __init__(self, initial_paused: bool = True) -> None:
        # InferenceAdapter.is_paused đọc thẳng `_paused` → giữ đúng tên field.
        self._paused = threading.Event()
        if initial_paused:
            self._paused.set()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def is_model_loaded(self) -> bool:
        return True

    def wait_model_ready(self, timeout: float) -> bool:
        return True

    def load_error(self):
        return None
