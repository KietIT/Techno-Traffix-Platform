"""
Geometry utility functions for video detection.

Provides:
- IOU (Intersection over Union) calculation
- Euclidean distance calculation
- Bounding box operations
"""

from typing import Tuple, List
import numpy as np


def calculate_iou(box1: Tuple[int, int, int, int], 
                  box2: Tuple[int, int, int, int]) -> float:
    """
    Calculate Intersection over Union (IOU) between two bounding boxes.
    
    Args:
        box1: First bounding box (x1, y1, x2, y2)
        box2: Second bounding box (x1, y1, x2, y2)
        
    Returns:
        IOU value between 0 and 1
    """
    # Extract coordinates
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Calculate intersection coordinates
    x1_inter = max(x1_1, x1_2)
    y1_inter = max(y1_1, y1_2)
    x2_inter = min(x2_1, x2_2)
    y2_inter = min(y2_1, y2_2)
    
    # Calculate intersection area
    inter_width = max(0, x2_inter - x1_inter)
    inter_height = max(0, y2_inter - y1_inter)
    intersection_area = inter_width * inter_height
    
    # Calculate union area
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = area1 + area2 - intersection_area
    
    # Avoid division by zero
    if union_area == 0:
        return 0.0
    
    return intersection_area / union_area


def calculate_distance(point1: Tuple[float, float], 
                       point2: Tuple[float, float]) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        point1: First point (x, y)
        point2: Second point (x, y)
        
    Returns:
        Euclidean distance
    """
    return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)


def get_centroid(box: Tuple[int, int, int, int]) -> Tuple[float, float]:
    """
    Calculate centroid of a bounding box.
    
    Args:
        box: Bounding box (x1, y1, x2, y2)
        
    Returns:
        Centroid coordinates (cx, cy)
    """
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def get_box_area(box: Tuple[int, int, int, int]) -> float:
    """
    Calculate area of a bounding box.
    
    Args:
        box: Bounding box (x1, y1, x2, y2)
        
    Returns:
        Area of the box
    """
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def boxes_overlap(box1: Tuple[int, int, int, int], 
                  box2: Tuple[int, int, int, int]) -> bool:
    """
    Check if two bounding boxes overlap.
    
    Args:
        box1: First bounding box (x1, y1, x2, y2)
        box2: Second bounding box (x1, y1, x2, y2)
        
    Returns:
        True if boxes overlap, False otherwise
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Check if boxes don't overlap
    if x2_1 < x1_2 or x2_2 < x1_1:
        return False
    if y2_1 < y1_2 or y2_2 < y1_1:
        return False
    
    return True
