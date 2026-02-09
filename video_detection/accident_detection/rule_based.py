"""
Rule-Based Accident Detection module - 4-STAGE HIGH-PRECISION LOGIC.

Optimized for:
- Fixed traffic cameras
- Vietnam traffic (high motorcycle density)
- HIGH PRECISION (minimize false positives)

Detection Stages:
1. Proximity Detection - identify when vehicles are close
2. Collision Candidate - IOU + velocity analysis
3. Post-Collision Behavior - confirm by observing aftermath
4. Final Confirmation - multi-indicator voting

Provides:
- AccidentDetector: High-precision accident detection
- AccidentEvent: Container for detected accidents
"""

import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import math

from tracker.bytetrack_tracker import TrackedObject
from speed_estimation.speed_estimator import SpeedInfo
from utils.geometry import calculate_iou, calculate_distance


logger = logging.getLogger(__name__)


class AccidentType(Enum):
    """Types of detected accidents."""

    COLLISION = "collision"
    SIDESWIPE = "sideswipe"  # Glancing collision with trajectory change
    REAR_END = "rear_end"  # One vehicle hits another from behind


class AccidentConfidence(Enum):
    """Confidence levels for accident detection."""

    HIGH = "high"  # 4+ indicators confirmed
    MEDIUM = "medium"  # 3 indicators confirmed
    LOW = "low"  # 2 indicators (not reported by default)


@dataclass
class AccidentEvent:
    """Container for an accident event."""

    event_id: str
    event_type: AccidentType
    confidence: AccidentConfidence
    involved_track_ids: List[int]
    location: Tuple[float, float]
    timestamp: float
    frame_id: int
    confidence_score: float
    description: str
    bboxes: List[Tuple[int, int, int, int]] = field(default_factory=list)

    # Evidence details
    indicators: Dict[str, bool] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.event_type.value}][{self.confidence.value}] {self.description} at frame {self.frame_id}"


@dataclass
class VehicleState:
    """Track comprehensive state of a vehicle over time."""

    track_id: int

    # Motion history
    speed_history: deque = field(default_factory=lambda: deque(maxlen=60))
    heading_history: deque = field(default_factory=lambda: deque(maxlen=60))
    position_history: deque = field(default_factory=lambda: deque(maxlen=60))

    # Derived metrics
    was_moving: bool = False
    max_speed_seen: float = 0.0
    last_known_speed: float = 0.0
    last_known_heading: float = 0.0
    last_position: Optional[Tuple[float, float]] = None
    last_seen_frame: int = 0  # Track last frame this vehicle was seen

    # For collision analysis
    velocity_before_event: Optional[float] = None
    heading_before_event: Optional[float] = None

    def update(self, speed: float, heading: float, position: Tuple[float, float], frame_id: int = 0) -> None:
        """Update vehicle state with new measurements."""
        self.speed_history.append(speed)
        self.heading_history.append(heading)
        self.position_history.append(position)

        self.last_known_speed = speed
        self.last_known_heading = heading
        self.last_position = position
        self.last_seen_frame = frame_id

        if speed > self.max_speed_seen:
            self.max_speed_seen = speed

        if speed > 5.0:  # Moving threshold
            self.was_moving = True

    def get_average_speed(self, window: int = 10) -> float:
        """Get average speed over recent frames."""
        if not self.speed_history:
            return 0.0
        recent = list(self.speed_history)[-window:]
        return sum(recent) / len(recent)

    def get_speed_change(self, window: int = 5) -> float:
        """Get speed change over window (negative = deceleration)."""
        if len(self.speed_history) < window + 1:
            return 0.0

        old_speed = list(self.speed_history)[-(window + 1)]
        new_speed = list(self.speed_history)[-1]
        return new_speed - old_speed

    def get_heading_change(self, window: int = 3) -> float:
        """Get total heading change over window."""
        if len(self.heading_history) < window + 1:
            return 0.0

        recent = list(self.heading_history)[-(window + 1) :]
        total_change = 0.0
        for i in range(1, len(recent)):
            diff = recent[i] - recent[i - 1]
            # Normalize to [-180, 180]
            while diff > 180:
                diff -= 360
            while diff < -180:
                diff += 360
            total_change += abs(diff)

        return total_change


@dataclass
class ProximityEvent:
    """Tracks when two vehicles are in proximity."""

    track_id_1: int
    track_id_2: int
    start_frame: int
    max_iou: float = 0.0
    frames_in_contact: int = 0

    # Velocities at start of proximity
    speed_1_before: float = 0.0
    speed_2_before: float = 0.0
    heading_1_before: float = 0.0
    heading_2_before: float = 0.0


@dataclass
class CollisionCandidate:
    """A potential collision awaiting confirmation."""

    track_id_1: int
    track_id_2: int
    start_frame: int
    location: Tuple[float, float]
    bboxes: List[Tuple[int, int, int, int]]

    # Evidence collected
    max_iou: float = 0.0
    velocity_change_1: float = 0.0
    velocity_change_2: float = 0.0
    heading_change_1: float = 0.0
    heading_change_2: float = 0.0

    # Post-collision tracking
    post_collision_frames: int = 0
    vehicle_1_stopped: bool = False
    vehicle_2_stopped: bool = False
    vehicle_1_slowed: bool = False
    vehicle_2_slowed: bool = False
    vehicles_diverged: bool = False

    def get_indicator_count(self) -> int:
        """Count how many collision indicators are present."""
        indicators = [
            self.max_iou >= 0.1,  # Physical contact
            abs(self.velocity_change_1) > 0.3 or abs(self.velocity_change_2) > 0.3,  # Velocity change
            self.heading_change_1 > 15 or self.heading_change_2 > 15,  # Heading change
            self.vehicle_1_stopped
            or self.vehicle_2_stopped
            or self.vehicle_1_slowed
            or self.vehicle_2_slowed,  # Post-collision behavior
            self.vehicles_diverged,  # Trajectory divergence
        ]
        return sum(indicators)

    def get_indicators_dict(self) -> Dict[str, bool]:
        """Get dictionary of indicator states."""
        return {
            "iou_contact": self.max_iou >= 0.1,
            "velocity_change": abs(self.velocity_change_1) > 0.3 or abs(self.velocity_change_2) > 0.3,
            "heading_change": self.heading_change_1 > 15 or self.heading_change_2 > 15,
            "post_stop_slow": (
                self.vehicle_1_stopped or self.vehicle_2_stopped or self.vehicle_1_slowed or self.vehicle_2_slowed
            ),
            "trajectory_diverged": self.vehicles_diverged,
        }


class AccidentDetector:
    """
    4-Stage High-Precision Accident Detector.

    Optimized for fixed traffic cameras and Vietnam traffic conditions.
    Prioritizes PRECISION over recall to minimize false positives.

    Stages:
    1. Proximity Detection: Identify when vehicles are close
    2. Collision Candidate: Analyze IOU + velocity for potential collisions
    3. Post-Collision Analysis: Observe behavior after collision
    4. Final Confirmation: Multi-indicator voting
    """

    def __init__(
        self,
        # Stage 1: Proximity
        proximity_iou_threshold: float = 0.05,
        proximity_distance_threshold: float = 100.0,
        proximity_min_frames: int = 2,
        # Stage 2: Collision Candidate
        collision_iou_threshold: float = 0.15,
        collision_min_frames: int = 5,
        min_speed_for_collision: float = 5.0,
        velocity_change_threshold: float = 0.4,
        heading_change_threshold: float = 20.0,
        require_both_affected: bool = True,
        # Stage 3: Post-Collision Analysis
        post_collision_window: int = 90,
        stop_speed_threshold: float = 2.0,
        slow_speed_threshold: float = 5.0,
        min_stop_duration: int = 30,
        divergence_threshold: float = 50.0,
        # Stage 4: Confirmation
        min_indicators_for_accident: int = 3,
        high_confidence_indicators: int = 4,
        # Trajectory Anomaly (sideswipe detection)
        enable_trajectory_detection: bool = True,
        trajectory_heading_threshold: float = 35.0,
        trajectory_min_speed: float = 8.0,
        trajectory_proximity: float = 120.0,
        sync_heading_tolerance: float = 25.0,
        # False positive filters
        filter_parallel_movement: bool = True,
        parallel_heading_tolerance: float = 15.0,
        parallel_speed_tolerance: float = 0.25,
        # General
        fps: float = 30.0,
    ):
        """Initialize the 4-stage accident detector."""
        # Stage 1 params
        self.proximity_iou_threshold = proximity_iou_threshold
        self.proximity_distance_threshold = proximity_distance_threshold
        self.proximity_min_frames = proximity_min_frames

        # Stage 2 params
        self.collision_iou_threshold = collision_iou_threshold
        self.collision_min_frames = collision_min_frames
        self.min_speed_for_collision = min_speed_for_collision
        self.velocity_change_threshold = velocity_change_threshold
        self.heading_change_threshold = heading_change_threshold
        self.require_both_affected = require_both_affected

        # Stage 3 params
        self.post_collision_window = post_collision_window
        self.stop_speed_threshold = stop_speed_threshold
        self.slow_speed_threshold = slow_speed_threshold
        self.min_stop_duration = min_stop_duration
        self.divergence_threshold = divergence_threshold

        # Stage 4 params
        self.min_indicators_for_accident = min_indicators_for_accident
        self.high_confidence_indicators = high_confidence_indicators

        # Trajectory params
        self.enable_trajectory_detection = enable_trajectory_detection
        self.trajectory_heading_threshold = trajectory_heading_threshold
        self.trajectory_min_speed = trajectory_min_speed
        self.trajectory_proximity = trajectory_proximity
        self.sync_heading_tolerance = sync_heading_tolerance

        # Filter params
        self.filter_parallel_movement = filter_parallel_movement
        self.parallel_heading_tolerance = parallel_heading_tolerance
        self.parallel_speed_tolerance = parallel_speed_tolerance

        self.fps = fps

        # State tracking
        self._vehicle_states: Dict[int, VehicleState] = {}
        self._proximity_events: Dict[Tuple[int, int], ProximityEvent] = {}
        self._collision_candidates: Dict[Tuple[int, int], CollisionCandidate] = {}
        self._confirmed_accidents: Set[str] = set()
        self._event_counter = 0

        logger.info("AccidentDetector initialized (4-STAGE HIGH-PRECISION)")
        logger.info(f"  Min indicators for accident: {min_indicators_for_accident}")
        logger.info(f"  Post-collision analysis window: {post_collision_window} frames")

    def _get_pair_key(self, id1: int, id2: int) -> Tuple[int, int]:
        """Get ordered pair key."""
        return (min(id1, id2), max(id1, id2))

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"ACC_{self._event_counter:06d}"

    def _get_vehicle_state(self, track_id: int) -> VehicleState:
        """Get or create vehicle state."""
        if track_id not in self._vehicle_states:
            self._vehicle_states[track_id] = VehicleState(track_id=track_id)
        return self._vehicle_states[track_id]

    def _is_parallel_movement(
        self,
        state1: VehicleState,
        state2: VehicleState,
        speed_info1: Optional[SpeedInfo],
        speed_info2: Optional[SpeedInfo],
    ) -> bool:
        """Check if two vehicles are moving parallel (same direction, similar speed)."""
        if not self.filter_parallel_movement:
            return False

        if speed_info1 is None or speed_info2 is None:
            return False

        # Check heading difference
        heading_diff = abs(speed_info1.current_heading - speed_info2.current_heading)
        if heading_diff > 180:
            heading_diff = 360 - heading_diff

        if heading_diff > self.parallel_heading_tolerance:
            return False

        # Check speed similarity
        max_speed = max(speed_info1.current_speed, speed_info2.current_speed)
        if max_speed > 0:
            speed_diff_ratio = abs(speed_info1.current_speed - speed_info2.current_speed) / max_speed
            if speed_diff_ratio > self.parallel_speed_tolerance:
                return False

        return True

    # ========== STAGE 1: Proximity Detection ==========

    def _detect_proximity(
        self, tracked_objects: List[TrackedObject], speed_infos: Dict[int, SpeedInfo], frame_id: int
    ) -> None:
        """Stage 1: Detect proximity events between vehicles."""
        n = len(tracked_objects)
        active_pairs = set()

        for i in range(n):
            for j in range(i + 1, n):
                obj1 = tracked_objects[i]
                obj2 = tracked_objects[j]
                pair_key = self._get_pair_key(obj1.track_id, obj2.track_id)

                # Calculate proximity metrics
                iou = calculate_iou(obj1.bbox, obj2.bbox)
                distance = calculate_distance(obj1.centroid, obj2.centroid)

                in_proximity = iou >= self.proximity_iou_threshold or distance <= self.proximity_distance_threshold

                if in_proximity:
                    active_pairs.add(pair_key)

                    if pair_key not in self._proximity_events:
                        # New proximity event
                        state1 = self._get_vehicle_state(obj1.track_id)
                        state2 = self._get_vehicle_state(obj2.track_id)
                        speed_info1 = speed_infos.get(obj1.track_id)
                        speed_info2 = speed_infos.get(obj2.track_id)

                        self._proximity_events[pair_key] = ProximityEvent(
                            track_id_1=obj1.track_id,
                            track_id_2=obj2.track_id,
                            start_frame=frame_id,
                            max_iou=iou,
                            frames_in_contact=1,
                            speed_1_before=speed_info1.current_speed if speed_info1 else 0,
                            speed_2_before=speed_info2.current_speed if speed_info2 else 0,
                            heading_1_before=speed_info1.current_heading if speed_info1 else 0,
                            heading_2_before=speed_info2.current_heading if speed_info2 else 0,
                        )
                    else:
                        # Update existing proximity event
                        event = self._proximity_events[pair_key]
                        event.frames_in_contact += 1
                        if iou > event.max_iou:
                            event.max_iou = iou

        # Clean up old proximity events
        stale = [k for k in self._proximity_events if k not in active_pairs]
        for k in stale:
            del self._proximity_events[k]

    # ========== STAGE 2: Collision Candidate Detection ==========

    def _detect_collision_candidates(
        self, tracked_objects: List[TrackedObject], speed_infos: Dict[int, SpeedInfo], frame_id: int
    ) -> None:
        """Stage 2: Identify collision candidates from proximity events."""
        objects_by_id = {obj.track_id: obj for obj in tracked_objects}

        for pair_key, prox_event in list(self._proximity_events.items()):
            # Skip if not enough frames in proximity
            if prox_event.frames_in_contact < self.proximity_min_frames:
                continue

            # Skip if already a collision candidate
            if pair_key in self._collision_candidates:
                continue

            # Check if this is a collision candidate
            obj1 = objects_by_id.get(prox_event.track_id_1)
            obj2 = objects_by_id.get(prox_event.track_id_2)

            if obj1 is None or obj2 is None:
                continue

            state1 = self._get_vehicle_state(obj1.track_id)
            state2 = self._get_vehicle_state(obj2.track_id)
            speed_info1 = speed_infos.get(obj1.track_id)
            speed_info2 = speed_infos.get(obj2.track_id)

            # Filter: Skip parallel movement (vehicles just driving together)
            if self._is_parallel_movement(state1, state2, speed_info1, speed_info2):
                continue

            # Check collision criteria
            iou_contact = prox_event.max_iou >= self.collision_iou_threshold

            # Both were moving before contact
            both_moving = (
                state1.was_moving
                and state2.was_moving
                and prox_event.speed_1_before >= self.min_speed_for_collision
                and prox_event.speed_2_before >= self.min_speed_for_collision
            )

            # At least one showing impact signs
            current_speed_1 = speed_info1.current_speed if speed_info1 else 0
            current_speed_2 = speed_info2.current_speed if speed_info2 else 0

            vel_change_1 = 0
            vel_change_2 = 0
            if prox_event.speed_1_before > 0:
                vel_change_1 = (prox_event.speed_1_before - current_speed_1) / prox_event.speed_1_before
            if prox_event.speed_2_before > 0:
                vel_change_2 = (prox_event.speed_2_before - current_speed_2) / prox_event.speed_2_before

            heading_change_1 = state1.get_heading_change(window=5)
            heading_change_2 = state2.get_heading_change(window=5)

            # Collision candidate criteria
            has_iou = iou_contact
            has_vel_change = (
                vel_change_1 > self.velocity_change_threshold or vel_change_2 > self.velocity_change_threshold
            )
            has_heading_change = (
                heading_change_1 > self.heading_change_threshold or heading_change_2 > self.heading_change_threshold
            )

            # Need at least 2 indicators to be a candidate
            indicator_count = sum([has_iou, has_vel_change, has_heading_change, both_moving])

            if indicator_count >= 2:
                # Create collision candidate
                cx = (obj1.centroid[0] + obj2.centroid[0]) / 2
                cy = (obj1.centroid[1] + obj2.centroid[1]) / 2

                self._collision_candidates[pair_key] = CollisionCandidate(
                    track_id_1=obj1.track_id,
                    track_id_2=obj2.track_id,
                    start_frame=prox_event.start_frame,
                    location=(cx, cy),
                    bboxes=[obj1.bbox, obj2.bbox],
                    max_iou=prox_event.max_iou,
                    velocity_change_1=vel_change_1,
                    velocity_change_2=vel_change_2,
                    heading_change_1=heading_change_1,
                    heading_change_2=heading_change_2,
                )

                logger.debug(f"Collision candidate: {pair_key}, indicators={indicator_count}")

    # ========== STAGE 3: Post-Collision Behavior Analysis ==========

    def _analyze_post_collision(
        self, tracked_objects: List[TrackedObject], speed_infos: Dict[int, SpeedInfo], frame_id: int
    ) -> None:
        """Stage 3: Analyze post-collision behavior of candidates."""
        objects_by_id = {obj.track_id: obj for obj in tracked_objects}

        for pair_key, candidate in list(self._collision_candidates.items()):
            frames_since = frame_id - candidate.start_frame

            # Only analyze within post-collision window
            if frames_since > self.post_collision_window:
                continue

            candidate.post_collision_frames = frames_since

            obj1 = objects_by_id.get(candidate.track_id_1)
            obj2 = objects_by_id.get(candidate.track_id_2)

            if obj1 is None and obj2 is None:
                continue

            # Analyze vehicle 1
            if obj1 is not None:
                speed_info1 = speed_infos.get(obj1.track_id)
                if speed_info1:
                    if speed_info1.current_speed <= self.stop_speed_threshold:
                        candidate.vehicle_1_stopped = True
                    elif speed_info1.current_speed <= self.slow_speed_threshold:
                        candidate.vehicle_1_slowed = True

            # Analyze vehicle 2
            if obj2 is not None:
                speed_info2 = speed_infos.get(obj2.track_id)
                if speed_info2:
                    if speed_info2.current_speed <= self.stop_speed_threshold:
                        candidate.vehicle_2_stopped = True
                    elif speed_info2.current_speed <= self.slow_speed_threshold:
                        candidate.vehicle_2_slowed = True

            # Check trajectory divergence
            if obj1 is not None and obj2 is not None:
                current_distance = calculate_distance(obj1.centroid, obj2.centroid)
                if current_distance > self.divergence_threshold:
                    candidate.vehicles_diverged = True

    # ========== STAGE 4: Final Confirmation ==========

    def _confirm_accidents(self, frame_id: int) -> List[AccidentEvent]:
        """Stage 4: Confirm accidents based on multi-indicator voting."""
        confirmed_events = []

        for pair_key, candidate in list(self._collision_candidates.items()):
            # Wait for enough post-collision analysis
            if candidate.post_collision_frames < self.min_stop_duration:
                continue

            indicator_count = candidate.get_indicator_count()

            # Check if meets minimum indicators
            if indicator_count < self.min_indicators_for_accident:
                # Not enough evidence - remove candidate after analysis window
                if candidate.post_collision_frames >= self.post_collision_window:
                    del self._collision_candidates[pair_key]
                continue

            # Generate event key to avoid duplicates
            event_key = f"collision_{pair_key[0]}_{pair_key[1]}"

            if event_key in self._confirmed_accidents:
                continue

            # Determine confidence level
            if indicator_count >= self.high_confidence_indicators:
                confidence = AccidentConfidence.HIGH
            else:
                confidence = AccidentConfidence.MEDIUM

            # Create accident event
            event = AccidentEvent(
                event_id=self._generate_event_id(),
                event_type=AccidentType.COLLISION,
                confidence=confidence,
                involved_track_ids=[candidate.track_id_1, candidate.track_id_2],
                location=candidate.location,
                timestamp=candidate.start_frame / self.fps,
                frame_id=candidate.start_frame,
                confidence_score=indicator_count / 5.0,
                description=(
                    f"Collision between ID:{candidate.track_id_1} and ID:{candidate.track_id_2}, "
                    f"{indicator_count}/5 indicators, IOU={candidate.max_iou:.2f}"
                ),
                bboxes=candidate.bboxes,
                indicators=candidate.get_indicators_dict(),
            )

            confirmed_events.append(event)
            self._confirmed_accidents.add(event_key)

            logger.warning(f"ACCIDENT CONFIRMED: {event}")

            # Remove from candidates
            del self._collision_candidates[pair_key]

        return confirmed_events

    # ========== Trajectory Anomaly Detection (Sideswipe) ==========

    def _detect_trajectory_anomaly(
        self, tracked_objects: List[TrackedObject], speed_infos: Dict[int, SpeedInfo], frame_id: int
    ) -> List[AccidentEvent]:
        """Detect sideswipe/glancing collisions via trajectory anomaly."""
        if not self.enable_trajectory_detection:
            return []

        events = []

        for obj in tracked_objects:
            speed_info = speed_infos.get(obj.track_id)
            if speed_info is None:
                continue

            state = self._get_vehicle_state(obj.track_id)

            # Skip if not moving fast enough
            if speed_info.current_speed < self.trajectory_min_speed:
                continue

            # Check for sudden heading change
            heading_change = abs(speed_info.heading_change)

            # Filter out noise (180° changes are usually tracking errors)
            if heading_change > 150 or heading_change < 15:
                continue

            # Need significant heading change
            if heading_change < self.trajectory_heading_threshold:
                continue

            # Find nearby vehicles
            nearby_vehicles = []
            for other in tracked_objects:
                if other.track_id == obj.track_id:
                    continue

                dist = calculate_distance(obj.centroid, other.centroid)
                if dist <= self.trajectory_proximity:
                    nearby_vehicles.append((other, dist))

            if not nearby_vehicles:
                continue

            # Check if this is synchronous turning (both vehicles turning together = curve)
            closest_obj, closest_dist = min(nearby_vehicles, key=lambda x: x[1])
            other_speed_info = speed_infos.get(closest_obj.track_id)

            if other_speed_info:
                other_heading_change = abs(other_speed_info.heading_change)

                # If both turning similar amounts in same direction, it's a curve
                same_direction = (speed_info.heading_change * other_speed_info.heading_change) > 0
                similar_magnitude = abs(heading_change - other_heading_change) < self.sync_heading_tolerance

                if same_direction and similar_magnitude:
                    continue  # This is synchronized turning, not a collision

            # Check for physical contact
            iou = calculate_iou(obj.bbox, closest_obj.bbox)

            # For trajectory anomaly, require either IOU or very close proximity
            if iou < 0.05 and closest_dist > 80:
                continue

            # Generate event
            pair_key = self._get_pair_key(obj.track_id, closest_obj.track_id)
            event_key = f"sideswipe_{pair_key[0]}_{pair_key[1]}"

            if event_key in self._confirmed_accidents:
                continue

            cx = (obj.centroid[0] + closest_obj.centroid[0]) / 2
            cy = (obj.centroid[1] + closest_obj.centroid[1]) / 2

            event = AccidentEvent(
                event_id=self._generate_event_id(),
                event_type=AccidentType.SIDESWIPE,
                confidence=AccidentConfidence.MEDIUM,
                involved_track_ids=[obj.track_id, closest_obj.track_id],
                location=(cx, cy),
                timestamp=frame_id / self.fps,
                frame_id=frame_id,
                confidence_score=0.7,
                description=(
                    f"Sideswipe: ID:{obj.track_id} deflected {heading_change:.1f}° near ID:{closest_obj.track_id}"
                ),
                bboxes=[obj.bbox, closest_obj.bbox],
                indicators={"heading_change": True, "proximity": True, "iou_contact": iou > 0},
            )

            events.append(event)
            self._confirmed_accidents.add(event_key)
            logger.warning(f"SIDESWIPE DETECTED: {event}")

        return events

    # ========== Main Detection Method ==========

    def detect(
        self,
        tracked_objects: List[TrackedObject],
        speed_infos: Dict[int, SpeedInfo],
        frame_id: int,
        current_time: Optional[float] = None,
    ) -> List[AccidentEvent]:
        """
        Run 4-stage accident detection.

        Args:
            tracked_objects: List of tracked vehicles
            speed_infos: Speed info for each track
            frame_id: Current frame number
            current_time: Current timestamp (optional)

        Returns:
            List of confirmed accident events
        """
        if current_time is None:
            current_time = frame_id / self.fps

        # Update all vehicle states
        for obj in tracked_objects:
            speed_info = speed_infos.get(obj.track_id)
            if speed_info:
                state = self._get_vehicle_state(obj.track_id)
                state.update(
                    speed=speed_info.current_speed,
                    heading=speed_info.current_heading,
                    position=obj.centroid,
                    frame_id=frame_id,
                )

        # Run detection stages
        all_events = []

        # Stage 1: Proximity detection
        self._detect_proximity(tracked_objects, speed_infos, frame_id)

        # Stage 2: Collision candidate detection
        self._detect_collision_candidates(tracked_objects, speed_infos, frame_id)

        # Stage 3: Post-collision behavior analysis
        self._analyze_post_collision(tracked_objects, speed_infos, frame_id)

        # Stage 4: Final confirmation
        all_events.extend(self._confirm_accidents(frame_id))

        # Additional: Trajectory anomaly detection
        all_events.extend(self._detect_trajectory_anomaly(tracked_objects, speed_infos, frame_id))

        # Cleanup old vehicle states (not seen for 60+ frames)
        active_ids = {obj.track_id for obj in tracked_objects}
        stale_ids = [tid for tid in self._vehicle_states if tid not in active_ids]
        for tid in stale_ids:
            state = self._vehicle_states[tid]
            frames_since_seen = frame_id - state.last_seen_frame
            if frames_since_seen > 60:
                del self._vehicle_states[tid]

        return all_events

    def reset(self) -> None:
        """Reset detector state."""
        self._vehicle_states.clear()
        self._proximity_events.clear()
        self._collision_candidates.clear()
        self._confirmed_accidents.clear()
        self._event_counter = 0
        logger.info("AccidentDetector reset")

    def update_fps(self, fps: float) -> None:
        """Update FPS for time calculations."""
        self.fps = fps

    def get_pending_candidates(self) -> int:
        """Get number of collision candidates being analyzed."""
        return len(self._collision_candidates)

    def get_stats(self) -> Dict[str, int]:
        """Get detection statistics."""
        return {
            "active_vehicle_states": len(self._vehicle_states),
            "active_proximity_events": len(self._proximity_events),
            "pending_candidates": len(self._collision_candidates),
            "confirmed_accidents": len(self._confirmed_accidents),
        }
