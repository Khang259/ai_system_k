"""
ROI detection — GPU only.

Không có fallback CPU: detections luôn là CUDA tensor từ nms_ready. Sai kiểu
là lỗi lập trình (pipeline hỏng), phải nổ ngay thay vì âm thầm báo "không hàng".
"""
import torch

from config.settings import settings
from utils.overlap_utils import calculate_coverage_multi_rois
from utils.setup_log import setup_logger

logger = setup_logger("detection", "logs/detection/log")


def _require_cuda_tensor(detections) -> None:
    """Chốt kiểu đầu vào. Fallback CPU đã bỏ nên sai kiểu = pipeline hỏng."""
    if not isinstance(detections, torch.Tensor):
        logger.error(
            f"detections phải là torch.Tensor, nhận {type(detections).__name__}. "
            "Pipeline chỉ chạy GPU — kiểm tra nms_ready / camera_processor."
        )
        raise TypeError(
            f"has_object_in_rois_batch cần torch.Tensor, nhận {type(detections).__name__}"
        )

    if not detections.is_cuda:
        logger.error(
            "detections nằm trên CPU — nms_ready phải trả tensor CUDA. "
            "Không tự chuyển sang GPU vì sẽ giấu lỗi cấu hình."
        )
        raise TypeError("has_object_in_rois_batch cần tensor trên CUDA, nhận tensor CPU")


def has_object_in_rois_batch(detections, rois_list):
    """
    Batch check nhiều ROI cùng lúc — 1 lần sync GPU thay vì N lần.

    Args:
        detections: torch.Tensor (CUDA) shape (N, 6) [x1,y1,x2,y2,conf,cls]
        rois_list: list of dict [{"node_id": str, "roi": [x,y,w,h]}, ...]

    Returns:
        list of (has_object: bool, coverage: float, node_id: str)

    Raises:
        TypeError: detections không phải CUDA tensor.
    """
    if not rois_list:
        return []

    _require_cuda_tensor(detections)

    empty = [(False, 0.0, roi_dict.get("node_id")) for roi_dict in rois_list]
    if len(detections) == 0:
        return empty

    # Chỉ giữ xe (class 0) đủ confidence
    vehicle_mask = (detections[:, 5] == 0.0) & (
        detections[:, 4] > settings.THRESHOLD_DETECT
    )
    vehicle_detections = detections[vehicle_mask]
    if len(vehicle_detections) == 0:
        return empty

    roi_boxes = [roi_dict["roi"] for roi_dict in rois_list]
    coverage_matrix = calculate_coverage_multi_rois(
        vehicle_detections, roi_boxes, device="cuda"
    )

    # Max coverage cho từng ROI, rồi về CPU đúng 1 lần (single sync point)
    max_coverages, _ = torch.max(coverage_matrix, dim=1)
    max_coverages_cpu = max_coverages.cpu().numpy()

    threshold_coverage = settings.THRESHOLD_COVERAGE
    return [
        (
            float(max_coverages_cpu[i]) >= threshold_coverage,
            float(max_coverages_cpu[i]),
            roi_dict.get("node_id"),
        )
        for i, roi_dict in enumerate(rois_list)
    ]
