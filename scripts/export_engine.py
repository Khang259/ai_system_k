import pathlib
import platform

if platform.system() == 'Windows':
    pathlib.PosixPath = pathlib.WindowsPath

from ultralytics import YOLO

model = YOLO("models/model_test.pt")
model.export(format="engine", device=0, half=True, dynamic=True, batch=32, imgsz=[480, 640])