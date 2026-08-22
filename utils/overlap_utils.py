import numpy as np
import torch

def calculate_coverage_batch(detection_boxes, roi_box, device='cuda'):
    """
    GPU-accelerated vectorized coverage calculation.
    
    Args:
        detection_boxes: torch.Tensor shape (N, 4) [x1, y1, x2, y2] or (N, 6) [x1,y1,x2,y2,conf,cls]
        roi_box: list/tuple [x, y, w, h]
        device: 'cuda' or 'cpu'
    
    Returns:
        coverage: torch.Tensor shape (N,) - coverage ratio for each detection
    """
    if len(detection_boxes) == 0:
        return torch.tensor([], device=device)
    
    if not isinstance(detection_boxes, torch.Tensor):
        detection_boxes = torch.tensor(detection_boxes, device=device)
    else:
        detection_boxes = detection_boxes.to(device)
    
    if detection_boxes.shape[1] > 4: #TODO: check the meaning of 4
        det_boxes = detection_boxes[:, :4]
    else:
        det_boxes = detection_boxes
    
    roi_x, roi_y, roi_w, roi_h = roi_box
    roi_xyxy = torch.tensor([roi_x, roi_y, roi_x + roi_w, roi_y + roi_h], #Format: [x1, y1, x2, y2]
                            device=device, dtype=det_boxes.dtype)
    
    inter_x1 = torch.maximum(det_boxes[:, 0], roi_xyxy[0])
    inter_y1 = torch.maximum(det_boxes[:, 1], roi_xyxy[1])
    inter_x2 = torch.minimum(det_boxes[:, 2], roi_xyxy[2])
    inter_y2 = torch.minimum(det_boxes[:, 3], roi_xyxy[3])
    
    inter_area = torch.clamp(inter_x2 - inter_x1, min=0) * \
                 torch.clamp(inter_y2 - inter_y1, min=0)
    
    roi_area = roi_w * roi_h
    
    if roi_area == 0:
        return torch.zeros(len(det_boxes), device=device)
    
    coverage = inter_area / roi_area
    
    return coverage


def calculate_coverage_multi_rois(detection_boxes, rois_list, device='cuda'):
    """
    GPU-accelerated batch coverage calculation for multiple ROIs.
    
    Args:
        detection_boxes: torch.Tensor shape (N, 4) [x1, y1, x2, y2] or (N, 6)
        rois_list: list of ROIs, each [x, y, w, h]
        device: 'cuda' or 'cpu'
    
    Returns:
        coverage_matrix: torch.Tensor shape (M, N) - coverage[roi_idx, det_idx]
                        M = number of ROIs, N = number of detections
    """
    if len(detection_boxes) == 0 or len(rois_list) == 0:
        return torch.zeros((len(rois_list), 0), device=device)
    
    if not isinstance(detection_boxes, torch.Tensor):
        detection_boxes = torch.tensor(detection_boxes, device=device)
    else:
        detection_boxes = detection_boxes.to(device)
    
    if detection_boxes.shape[1] > 4:
        det_boxes = detection_boxes[:, :4]
    else:
        det_boxes = detection_boxes
    
    # Convert all ROIs to xyxy format: shape (M, 4)
    rois_xyxy = []
    roi_areas = []
    for roi in rois_list:
        roi_x, roi_y, roi_w, roi_h = roi
        rois_xyxy.append([roi_x, roi_y, roi_x + roi_w, roi_y + roi_h])
        roi_areas.append(roi_w * roi_h)
    
    rois_xyxy = torch.tensor(rois_xyxy, device=device, dtype=det_boxes.dtype)  # (M, 4)
    roi_areas = torch.tensor(roi_areas, device=device, dtype=det_boxes.dtype)  # (M,)
    
    # Expand for broadcasting: det_boxes (1, N, 4), rois_xyxy (M, 1, 4)
    det_boxes_exp = det_boxes.unsqueeze(0)  # (1, N, 4)
    rois_exp = rois_xyxy.unsqueeze(1)       # (M, 1, 4)
    
    # Calculate intersection for all ROI-detection pairs
    inter_x1 = torch.maximum(det_boxes_exp[:, :, 0], rois_exp[:, :, 0])  # (M, N)
    inter_y1 = torch.maximum(det_boxes_exp[:, :, 1], rois_exp[:, :, 1])
    inter_x2 = torch.minimum(det_boxes_exp[:, :, 2], rois_exp[:, :, 2])
    inter_y2 = torch.minimum(det_boxes_exp[:, :, 3], rois_exp[:, :, 3])
    
    inter_area = torch.clamp(inter_x2 - inter_x1, min=0) * \
                 torch.clamp(inter_y2 - inter_y1, min=0)  # (M, N)
    
    # Calculate coverage: shape (M, N)
    roi_areas_exp = roi_areas.unsqueeze(1)  # (M, 1)
    coverage_matrix = inter_area / (roi_areas_exp + 1e-6)  # Avoid division by zero
    
    return coverage_matrix