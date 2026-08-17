# File: yolo_visualizer.py
#TODO: this file can be delete cause it uses for testing only
#TODO: remove this file to another folder for testing purpose
from ultralytics import YOLO
from utils.setup_log import setup_logger
import numpy as np
import torch
import pathlib
import platform
if platform.system() == 'Windows':
    pathlib.PosixPath = pathlib.WindowsPath

logger = setup_logger("yolo_visualizer", "logs/yolo_visualizer/log")


#TODO: check this function is still available for GPU inference in batch processing
def predict_and_visualize(model, frame, return_tensor=True):
    """
    YOLO inference với option giữ tensor trên GPU.
    
    Args:
        model: YOLO model
        frame: numpy array (H, W, 3)
        return_tensor: True = return GPU tensor, False = return numpy array
    
    Returns:
        detections: torch.Tensor (GPU) hoặc numpy array tùy return_tensor
        annotated_frame: numpy array với bbox vẽ sẵn
    """
    try:
        results = model(frame, 
                        conf=0.3, 
                        max_det=15,
                        device='cuda',
                        verbose=False)
        
        if return_tensor:
            detections = results[0].boxes.data
        else:
            logger.warning("This device is not supported for GPU inference")
            
        #annotated_frame = results[0].plot()
        #return detections, annotated_frame
        return detections
        
    except Exception as e:
        logger.error(f"Error in YOLO prediction: {e}")
        return torch.empty((0, 6), device='cuda'), frame

def predict_batch(model, frames_batch):
    """
    Batch inference cho nhiều frames.
    
    Args:
        model: YOLO model
        frames_batch: List[np.ndarray] - list of frames
    
    Returns:
        List[Tuple[torch.Tensor, np.ndarray]] - list of (detections, annotated_frame)
    """
    try:
        results = model(frames_batch, 
                        conf=0.3, 
                        max_det=15,
                        device='cuda',
                        verbose=False)
        
        output = []
        for result in results:
            detections = result.boxes.data
            #annotated_frame = result.plot()
            #output.append((detections, annotated_frame))
            output.append((detections))
        
        return output
        
    except Exception as e:
        logger.error(f"Error in batch YOLO prediction: {e}")
        empty_results = []
        for frame in frames_batch:
            empty_results.append((torch.empty((0, 6), device='cuda'), frame))
        return empty_results