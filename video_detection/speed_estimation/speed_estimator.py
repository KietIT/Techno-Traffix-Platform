"""
Speed Estimator module - ENHANCED with Heading/Direction and Acceleration.

Provides:
- SpeedEstimator: Calculates object speed, heading, AND acceleration for trajectory analysis
- Supports smoothing to reduce noise from tracking jitter
"""

import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
import math

from tracker.bytetrack_tracker import TrackedObject


logger = logging.getLogger(__name__)


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-180, 180] degrees."""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def angle_difference(angle1: float, angle2: float) -> float:
    """Calculate the smallest difference between two angles (in degrees)."""
    diff = angle1 - angle2
    return normalize_angle(diff)


def moving_average(values: List[float], window: int = 3) -> float:
    """Calculate moving average of recent values."""
    if not values:
        return 0.0
    recent = values[-window:]
    return sum(recent) / len(recent)


@dataclass
class SpeedInfo:
    """Container for speed, heading, and acceleration information."""

    track_id: int
    current_speed: float  # pixels per frame
    average_speed: float  # pixels per frame (over history)
    speed_kmh: float  # approximate km/h (if calibrated)
    is_moving: bool
    speed_change: float  # delta from previous speed

    # Heading/Direction information
    current_heading: float  # angle in degrees (-180 to 180), 0 = right, 90 = down
    heading_change: float  # change in heading since last frame (degrees)
    heading_history: List[float] = field(default_factory=list)  # recent headings

    # NEW: Acceleration information (for collision detection)
    acceleration: float = 0.0  # pixels per frame^2 (positive = speeding up, negative = braking)
    smoothed_speed: float = 0.0  # noise-reduced speed
    smoothed_heading: float = 0.0  # noise-reduced heading


class SpeedEstimator:
    """
    Estimates speed, heading, AND acceleration of tracked objects.

    Enhanced to support trajectory anomaly detection:
    - Calculates heading (direction angle) from velocity vector
    - Tracks heading history for sudden direction change detection
    - Calculates acceleration for collision impact detection
    - Applies smoothing to reduce tracking noise
    """

    def __init__(
        self,
        fps: float = 30.0,
        pixels_per_meter: float = 50.0,
        min_history: int = 2,  # Reduced for faster warmup
        stationary_threshold: float = 2.0,
        heading_history_length: int = 20,  # Increased for better analysis
        acceleration_window: int = 5,  # Frames for acceleration calculation
        smooth_window: int = 3,  # Moving average window for noise reduction
    ):
        """
        Initialize SpeedEstimator.

        Args:
            fps: Video frames per second
            pixels_per_meter: Calibration factor for real-world conversion
            min_history: Minimum frames of history needed for calculation
            stationary_threshold: Speed below which object is considered stationary
            heading_history_length: Number of frames to keep heading history
            acceleration_window: Frames to use for acceleration calculation
            smooth_window: Window size for moving average smoothing
        """
        self.fps = fps
        self.pixels_per_meter = pixels_per_meter
        self.min_history = min_history
        self.stationary_threshold = stationary_threshold
        self.heading_history_length = heading_history_length
        self.acceleration_window = acceleration_window
        self.smooth_window = smooth_window

        # Store previous data for change detection
        self._previous_speeds: Dict[int, float] = {}
        self._previous_headings: Dict[int, float] = {}
        self._heading_histories: Dict[int, List[float]] = {}
        self._speed_histories: Dict[int, List[float]] = {}  # NEW: for acceleration

        logger.info(
            f"SpeedEstimator initialized: fps={fps}, heading_history={heading_history_length}, "
            f"accel_window={acceleration_window}, smooth_window={smooth_window}"
        )

    def _calculate_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def _calculate_heading(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        Calculate heading (direction angle) from p1 to p2.

        Returns angle in degrees:
        - 0 = moving right (+x)
        - 90 = moving down (+y)
        - 180/-180 = moving left (-x)
        - -90 = moving up (-y)
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        # atan2 returns radians from -pi to pi
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    def estimate_speed(self, tracked_object: TrackedObject) -> Optional[SpeedInfo]:
        """
        Estimate speed, heading, AND acceleration for a single tracked object.

        Args:
            tracked_object: TrackedObject with centroid history

        Returns:
            SpeedInfo if enough history, None otherwise
        """
        history = tracked_object.centroid_history
        frame_history = tracked_object.frame_history
        track_id = tracked_object.track_id

        # Need minimum history for calculation
        if len(history) < self.min_history:
            return None

        # === SPEED CALCULATION ===
        current_distance = self._calculate_distance(history[-1], history[-2])
        frame_diff = frame_history[-1] - frame_history[-2]
        frame_diff = max(1, frame_diff)
        current_speed = current_distance / frame_diff

        # Average speed over history
        total_distance = 0.0
        for i in range(1, len(history)):
            total_distance += self._calculate_distance(history[i], history[i - 1])

        total_frames = frame_history[-1] - frame_history[0]
        total_frames = max(1, total_frames)
        average_speed = total_distance / total_frames

        # Convert to km/h
        speed_kmh = (average_speed * self.fps / self.pixels_per_meter) * 3.6

        # Determine if moving
        is_moving = current_speed >= self.stationary_threshold

        # Speed change
        previous_speed = self._previous_speeds.get(track_id, current_speed)
        speed_change = current_speed - previous_speed
        self._previous_speeds[track_id] = current_speed

        # === SPEED HISTORY FOR ACCELERATION ===
        if track_id not in self._speed_histories:
            self._speed_histories[track_id] = []
        self._speed_histories[track_id].append(current_speed)

        # Trim speed history
        if len(self._speed_histories[track_id]) > self.heading_history_length:
            self._speed_histories[track_id] = self._speed_histories[track_id][-self.heading_history_length :]

        # === ACCELERATION CALCULATION (NEW) ===
        acceleration = 0.0
        speed_hist = self._speed_histories[track_id]
        if len(speed_hist) >= self.acceleration_window:
            # Calculate acceleration as speed change over window
            old_speed = speed_hist[-self.acceleration_window]
            new_speed = speed_hist[-1]
            acceleration = (new_speed - old_speed) / self.acceleration_window

        # === SMOOTHED SPEED (noise reduction) ===
        smoothed_speed = moving_average(speed_hist, self.smooth_window)

        # === HEADING CALCULATION ===
        # Only calculate heading if moving (avoid noise when stationary)
        if current_speed >= self.stationary_threshold:
            current_heading = self._calculate_heading(history[-2], history[-1])
        else:
            # Keep previous heading when stationary
            current_heading = self._previous_headings.get(track_id, 0.0)

        # Calculate heading change
        previous_heading = self._previous_headings.get(track_id, current_heading)
        heading_change = angle_difference(current_heading, previous_heading)
        self._previous_headings[track_id] = current_heading

        # Update heading history
        if track_id not in self._heading_histories:
            self._heading_histories[track_id] = []
        self._heading_histories[track_id].append(current_heading)

        # Trim history
        if len(self._heading_histories[track_id]) > self.heading_history_length:
            self._heading_histories[track_id] = self._heading_histories[track_id][-self.heading_history_length :]

        # === SMOOTHED HEADING (noise reduction) ===
        smoothed_heading = moving_average(self._heading_histories[track_id], self.smooth_window)

        return SpeedInfo(
            track_id=track_id,
            current_speed=current_speed,
            average_speed=average_speed,
            speed_kmh=speed_kmh,
            is_moving=is_moving,
            speed_change=speed_change,
            current_heading=current_heading,
            heading_change=heading_change,
            heading_history=self._heading_histories[track_id].copy(),
            acceleration=acceleration,
            smoothed_speed=smoothed_speed,
            smoothed_heading=smoothed_heading,
        )

    def estimate_speeds(self, tracked_objects: List[TrackedObject]) -> Dict[int, SpeedInfo]:
        """
        Estimate speeds and headings for multiple tracked objects.

        Args:
            tracked_objects: List of TrackedObject

        Returns:
            Dict mapping track_id to SpeedInfo
        """
        speeds = {}
        for obj in tracked_objects:
            speed_info = self.estimate_speed(obj)
            if speed_info is not None:
                speeds[obj.track_id] = speed_info

        return speeds

    def get_max_heading_change(self, track_id: int, window: int = 5) -> float:
        """
        Get maximum heading change over a window of frames.

        Useful for detecting sudden direction changes.

        Args:
            track_id: Track ID to check
            window: Number of frames to analyze

        Returns:
            Maximum absolute heading change in degrees
        """
        if track_id not in self._heading_histories:
            return 0.0

        history = self._heading_histories[track_id]
        if len(history) < 2:
            return 0.0

        # Get recent window
        recent = history[-min(window, len(history)) :]

        max_change = 0.0
        for i in range(1, len(recent)):
            change = abs(angle_difference(recent[i], recent[i - 1]))
            if change > max_change:
                max_change = change

        return max_change

    def get_total_heading_change(self, track_id: int, window: int = 5) -> float:
        """
        Get total accumulated heading change over a window.

        Useful for detecting sustained turning or spinning.

        Args:
            track_id: Track ID to check
            window: Number of frames to analyze

        Returns:
            Total heading change in degrees (can be positive or negative)
        """
        if track_id not in self._heading_histories:
            return 0.0

        history = self._heading_histories[track_id]
        if len(history) < 2:
            return 0.0

        recent = history[-min(window, len(history)) :]

        total_change = 0.0
        for i in range(1, len(recent)):
            total_change += angle_difference(recent[i], recent[i - 1])

        return total_change

    def update_fps(self, fps: float) -> None:
        """Update FPS for km/h conversion."""
        self.fps = fps
        logger.debug(f"FPS updated to {fps}")

    def cleanup_stale_tracks(self, active_track_ids: set) -> None:
        """Remove data for tracks no longer active."""
        stale_ids = [tid for tid in self._previous_speeds if tid not in active_track_ids]
        for tid in stale_ids:
            if tid in self._previous_speeds:
                del self._previous_speeds[tid]
            if tid in self._previous_headings:
                del self._previous_headings[tid]
            if tid in self._heading_histories:
                del self._heading_histories[tid]
            if tid in self._speed_histories:
                del self._speed_histories[tid]

    def get_acceleration(self, track_id: int) -> float:
        """Get current acceleration for a track."""
        if track_id not in self._speed_histories:
            return 0.0

        speed_hist = self._speed_histories[track_id]
        if len(speed_hist) < self.acceleration_window:
            return 0.0

        old_speed = speed_hist[-self.acceleration_window]
        new_speed = speed_hist[-1]
        return (new_speed - old_speed) / self.acceleration_window

    def get_speed_history(self, track_id: int) -> List[float]:
        """Get speed history for a track."""
        return self._speed_histories.get(track_id, []).copy()

    def is_decelerating(self, track_id: int, threshold: float = -0.5) -> bool:
        """Check if a vehicle is decelerating significantly."""
        return self.get_acceleration(track_id) < threshold

    def is_accelerating(self, track_id: int, threshold: float = 0.5) -> bool:
        """Check if a vehicle is accelerating significantly."""
        return self.get_acceleration(track_id) > threshold
