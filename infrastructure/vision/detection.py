from config.settings import settings
from utils.setup_log import setup_logger
from utils.overlap_utils import calculate_coverage_batch
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
