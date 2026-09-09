"""
Coverage ROI × detection — GPU only.

detection_boxes luôn là CUDA tensor từ nms_ready. Không tự convert list/numpy
sang tensor: làm vậy sẽ giấu lỗi cấu hình pipeline.
"""
import torch


def calculate_coverage_multi_rois(detection_boxes, rois_list, device='cuda'):
    """
    Coverage cho nhiều ROI cùng lúc, vectorize hoàn toàn trên GPU.

    Args:
        detection_boxes: torch.Tensor (CUDA) shape (N, 4) [x1,y1,x2,y2] hoặc (N, 6)
        rois_list: list of ROIs, mỗi cái [x, y, w, h]
        device: thiết bị tạo tensor trung gian

    Returns:
        coverage_matrix: torch.Tensor shape (M, N) — coverage[roi_idx, det_idx]

    Raises:
        TypeError: detection_boxes không phải torch.Tensor.
    """
    if not isinstance(detection_boxes, torch.Tensor):
        raise TypeError(
            f"calculate_coverage_multi_rois cần torch.Tensor, "
            f"nhận {type(detection_boxes).__name__}"
        )

    if len(detection_boxes) == 0 or len(rois_list) == 0:
        return torch.zeros((len(rois_list), 0), device=device)

    # YOLO boxes: (N,4)=xyxy hoặc (N,6)=xyxy+conf+cls — coverage chỉ cần 4 cột đầu
    det_boxes = (
        detection_boxes[:, :4]
        if detection_boxes.shape[1] > 4
        else detection_boxes
    )

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

    # Coverage: shape (M, N). +1e-6 tránh chia 0 khi ROI có diện tích 0
    roi_areas_exp = roi_areas.unsqueeze(1)  # (M, 1)
    return inter_area / (roi_areas_exp + 1e-6)
