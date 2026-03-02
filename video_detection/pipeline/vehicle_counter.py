"""
Vehicle Counter module.

Counts unique vehicles crossing a virtual horizontal line using two-layer deduplication:
1. Track ID registry  : same track_id is never counted twice per session.
2. Spatial dedup      : if a new track_id crosses at nearly the same x-position
                        within a short time window, it is treated as a re-ID of
                        the same physical vehicle and skipped.

Output: CountResult dataclass — JSON-serializable, suitable as DQN state input
for downstream traffic-light control.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from tracker.bytetrack_tracker import TrackedObject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CrossingEvent:
    """Records a single vehicle crossing the counting line."""
    track_id: int
    class_name: str
    x_position: float   # centroid x at crossing moment
    frame_id: int
    timestamp: float    # seconds from start


@dataclass
class CountResult:
    """
    Final counting result — JSON-serializable.

    Designed for DQN traffic-light control:
    - vehicle_counts  : per-class totals → DQN state vector
    - total_vehicles  : scalar density signal
    - accidents_detected: urgency / reward shaping flag
    - crossing_events : full per-vehicle log for analysis / training replay
    """
    video_source: str
    processed_at: str
    total_frames: int
    duration_seconds: float
    fps: float
    vehicle_counts: Dict[str, int]
    total_vehicles: int
    accidents_detected: int
    crossing_events: List[dict]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# VehicleCounter
# ---------------------------------------------------------------------------

class VehicleCounter:
    """
    Counts unique vehicles crossing a configurable virtual horizontal line.

    Usage (called each frame from InferencePipeline.process_frame):
        new_events = counter.update(tracked_objects, frame_id)

    At end of video:
        result = counter.build_result(video_source, total_frames,
                                      duration_seconds, accidents_detected)
        print(result.to_json())
    """

    def __init__(
        self,
        frame_height: int,
        line_position: float = 0.5,
        min_track_length: int = 3,
        dedup_distance: float = 80.0,
        dedup_time_window: float = 2.0,
        fps: float = 30.0,
    ):
        """
        Args:
            frame_height       : Frame height in pixels (used to compute line_y).
            line_position      : Fractional y-position of counting line [0=top, 1=bottom].
            min_track_length   : Minimum centroid history frames before a track
                                 is eligible (filters out ephemeral false detections).
            dedup_distance     : Max x-pixel delta to classify a crossing as a
                                 spatial duplicate of a recent crossing.
            dedup_time_window  : Time window in seconds used for spatial dedup.
            fps                : Video FPS (converts dedup_time_window → frames).
        """
        self.fps = fps
        self.line_y = int(frame_height * line_position)
        self.min_track_length = min_track_length
        self.dedup_distance = dedup_distance
        self.dedup_frames = max(1, int(dedup_time_window * fps))

        # Per-class cumulative counts
        self._counts: Dict[str, int] = {}

        # Layer 1: track IDs that have already been counted
        self._crossed_ids: Set[int] = set()

        # Layer 2: sliding window of recent crossings for spatial dedup
        self._crossing_registry: List[CrossingEvent] = []

        # Full event log for JSON output
        self._all_crossings: List[CrossingEvent] = []

        # Previous centroid per track_id for crossing detection
        self._prev_centroids: Dict[int, Tuple[float, float]] = {}

        logger.info(
            f"VehicleCounter initialized: line_y={self.line_y}px "
            f"({line_position * 100:.0f}% of {frame_height}px), "
            f"dedup_dist={dedup_distance}px, dedup_window={dedup_time_window}s"
        )

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        tracked_objects: List[TrackedObject],
        frame_id: int,
    ) -> List[CrossingEvent]:
        """
        Process one frame's tracked objects and detect new line crossings.

        Returns:
            List of CrossingEvent recorded in this frame (may be empty).
        """
        new_crossings: List[CrossingEvent] = []

        # Prune crossing registry to the sliding dedup window
        self._crossing_registry = [
            e for e in self._crossing_registry
            if frame_id - e.frame_id <= self.dedup_frames
        ]

        for obj in tracked_objects:
            track_id = obj.track_id
            cx, cy = obj.centroid

            # Skip tracks that are too short — likely noise / false positives
            if len(obj.centroid_history) < self.min_track_length:
                self._prev_centroids[track_id] = (cx, cy)
                continue

            prev = self._prev_centroids.get(track_id)
            self._prev_centroids[track_id] = (cx, cy)

            if prev is None:
                continue

            prev_cy = prev[1]

            # Detect crossing in either direction
            crossed = (
                (prev_cy < self.line_y <= cy) or
                (prev_cy > self.line_y >= cy)
            )
            if not crossed:
                continue

            event = CrossingEvent(
                track_id=track_id,
                class_name=obj.class_name,
                x_position=round(cx, 1),
                frame_id=frame_id,
                timestamp=round(frame_id / self.fps, 3),
            )

            if self._should_count(event):
                self._counts[obj.class_name] = (
                    self._counts.get(obj.class_name, 0) + 1
                )
                self._crossed_ids.add(track_id)
                self._crossing_registry.append(event)
                self._all_crossings.append(event)
                new_crossings.append(event)
                logger.debug(
                    f"Counted {obj.class_name} ID:{track_id} "
                    f"at frame {frame_id} x={cx:.0f} "
                    f"(total {obj.class_name}: {self._counts[obj.class_name]})"
                )

        return new_crossings

    # ------------------------------------------------------------------
    # Deduplication logic
    # ------------------------------------------------------------------

    def _should_count(self, event: CrossingEvent) -> bool:
        """
        Return True if this crossing event should increment the count.

        Layer 1 — track_id already counted → False.
        Layer 2 — same class crossed at nearby x within time window → False (re-ID).
        """
        if event.track_id in self._crossed_ids:
            return False

        for past in self._crossing_registry:
            if past.class_name != event.class_name:
                continue
            if abs(past.x_position - event.x_position) < self.dedup_distance:
                logger.debug(
                    f"Spatial dedup: skipping {event.class_name} ID:{event.track_id} "
                    f"(matches ID:{past.track_id}, "
                    f"Δx={abs(past.x_position - event.x_position):.0f}px, "
                    f"Δframes={event.frame_id - past.frame_id})"
                )
                return False

        return True

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def line_y_coord(self) -> int:
        """Y-coordinate of the counting line in pixels."""
        return self.line_y

    def get_counts(self) -> Dict[str, int]:
        """Return current per-class counts."""
        return dict(self._counts)

    def get_total(self) -> int:
        """Return total vehicles counted across all classes."""
        return sum(self._counts.values())

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

    def build_result(
        self,
        video_source: str,
        total_frames: int,
        duration_seconds: float,
        accidents_detected: int,
    ) -> CountResult:
        """
        Build the final CountResult for JSON export.

        Args:
            video_source       : Original video path / URL.
            total_frames       : Total frames processed.
            duration_seconds   : Elapsed video duration.
            accidents_detected : Number of accident events confirmed.

        Returns:
            CountResult — call .to_json() or .to_dict() to consume.
        """
        return CountResult(
            video_source=video_source,
            processed_at=datetime.now().isoformat(),
            total_frames=total_frames,
            duration_seconds=round(duration_seconds, 2),
            fps=round(self.fps, 2),
            vehicle_counts=self.get_counts(),
            total_vehicles=self.get_total(),
            accidents_detected=accidents_detected,
            crossing_events=[
                {
                    "track_id": e.track_id,
                    "class_name": e.class_name,
                    "x_position": e.x_position,
                    "frame_id": e.frame_id,
                    "timestamp": e.timestamp,
                }
                for e in self._all_crossings
            ],
        )

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all state (useful when re-running on a new video)."""
        self._counts.clear()
        self._crossed_ids.clear()
        self._crossing_registry.clear()
        self._all_crossings.clear()
        self._prev_centroids.clear()
        logger.info("VehicleCounter reset")
