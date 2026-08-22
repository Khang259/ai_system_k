from config.settings import settings
from utils.setup_log import setup_logger
from utils.overlap_utils import calculate_coverage_batch, calculate_coverage_multi_rois
import torch

logger = setup_logger("detection", "logs/detection/log")


def has_object_in_roi(detections, roi, node_id=None, use_gpu=True):
    """
    Kiểm tra xem có object trong ROI hay không.

    Args:
        detections: torch.Tensor (GPU) hoặc numpy array - shape (N, 6) [x1,y1,x2,y2,conf,cls]
        roi: list [x, y, w, h]
        node_id: optional node identifier
        use_gpu: True = dùng GPU tensor ops, False = fallback numpy

    Returns:
        has_object: bool
        coverage_value: float
    """
    try:
        threshold_coverage = settings.THRESHOLD_COVERAGE
        threshold_detect = settings.THRESHOLD_DETECT
        roi_box = roi

        has_object = False
        coverage_value = 0.0

        if use_gpu and isinstance(detections, torch.Tensor):
            if len(detections) == 0:
                return False, 0.0

            vehicle_mask = (detections[:, 5] == 0.0) & (detections[:, 4] > threshold_detect)
            vehicle_detections = detections[vehicle_mask]

            if len(vehicle_detections) == 0:
                return False, 0.0

            coverage_values = calculate_coverage_batch(vehicle_detections, roi_box, device="cuda")

            max_coverage, max_idx = torch.max(coverage_values, dim=0)

            if max_coverage >= threshold_coverage:
                has_object = True
                coverage_value = max_coverage.item()
        else:
            for det in detections:
                det_x, det_y, det_x1, det_y1, conf, cls = det
                if cls == 0.0 and conf > threshold_detect:
                    det_box = [det_x, det_y, det_x1, det_y1]
                    if is_roi_covered_enough(det_box, roi_box, threshold_coverage):
                        coverage_value = calculate_coverage(det_box, roi_box)
                        has_object = True
                        break

        return has_object, coverage_value
    except Exception as e:
        logger.error(f"Error in detection: {e}")
        return False, 0.0


def has_object_in_rois_batch(detections, rois_list, use_gpu=True):
    """
    Batch check nhiều ROI cùng lúc (1 lần sync GPU thay vì N lần).
    
    Args:
        detections: torch.Tensor (GPU) shape (N, 6) [x1,y1,x2,y2,conf,cls]
        rois_list: list of dict [{"node_id": str, "roi": [x,y,w,h]}, ...]
        use_gpu: True = dùng GPU tensor ops
    
    Returns:
        results: list of (has_object: bool, coverage: float, node_id: str)
    """
    try:
        threshold_coverage = settings.THRESHOLD_COVERAGE
        threshold_detect = settings.THRESHOLD_DETECT
        
        if not rois_list:
            return []
        
        results = []
        
        if use_gpu and isinstance(detections, torch.Tensor):
            if len(detections) == 0:
                return [(False, 0.0, roi_dict.get("node_id")) for roi_dict in rois_list]
            
            # Filter vehicle detections (class 0, conf > threshold)
            vehicle_mask = (detections[:, 5] == 0.0) & (detections[:, 4] > threshold_detect)
            vehicle_detections = detections[vehicle_mask]
            
            if len(vehicle_detections) == 0:
                return [(False, 0.0, roi_dict.get("node_id")) for roi_dict in rois_list]
            
            # Extract ROI boxes
            roi_boxes = [roi_dict["roi"] for roi_dict in rois_list]
            
            # Batch calculate coverage: (M_rois, N_detections)
            coverage_matrix = calculate_coverage_multi_rois(
                vehicle_detections, roi_boxes, device="cuda"
            )
            
            # Find max coverage for each ROI (along detection axis)
            max_coverages, max_indices = torch.max(coverage_matrix, dim=1)  # (M_rois,)
            
            # Convert to CPU once (single sync point!)
            max_coverages_cpu = max_coverages.cpu().numpy()
            
            # Build results
            for i, roi_dict in enumerate(rois_list):
                max_cov = float(max_coverages_cpu[i])
                has_obj = max_cov >= threshold_coverage
                node_id = roi_dict.get("node_id")
                results.append((has_obj, max_cov, node_id))
        
        else:
            # Fallback: CPU numpy (giữ nguyên logic cũ, loop từng ROI)
            for roi_dict in rois_list:
                roi = roi_dict["roi"]
                node_id = roi_dict.get("node_id")
                has_obj, cov = has_object_in_roi(detections, roi, node_id, use_gpu=False)
                results.append((has_obj, cov, node_id))
        
        return results
        
    except Exception as e:
        logger.error(f"Error in batch detection: {e}")
        # Return safe defaults
        return [(False, 0.0, roi_dict.get("node_id")) for roi_dict in rois_list]
