"""
Video Reader module for handling video/RTSP input.

Provides:
- VideoReader: Class for reading video files or RTSP streams
- Frame sampling and FPS control
"""

import cv2
import logging
from typing import Optional, Tuple, Generator
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """Container for frame information."""
    frame: any  # numpy array
    frame_id: int
    timestamp: float  # in seconds
    fps: float


class VideoReader:
    """
    Video reader class supporting files and RTSP streams.
    
    Features:
    - Read from video file or RTSP/HTTP stream
    - Optional frame resizing
    - Frame skipping for FPS control
    - Generator-based iteration
    """
    
    def __init__(
        self,
        source: str,
        resize_width: Optional[int] = None,
        resize_height: Optional[int] = None,
        target_fps: Optional[float] = None
    ):
        """
        Initialize VideoReader.
        
        Args:
            source: Path to video file or RTSP/HTTP URL
            resize_width: Target width for resizing (None = no resize)
            resize_height: Target height for resizing (None = no resize)
            target_fps: Target FPS for frame sampling (None = use source FPS)
        """
        self.source = source
        self.resize_width = resize_width
        self.resize_height = resize_height
        self.target_fps = target_fps
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._source_fps = 0.0
        self._total_frames = 0
        self._width = 0
        self._height = 0
        
    def open(self) -> bool:
        """
        Open video source.
        
        Returns:
            True if opened successfully, False otherwise
        """
        try:
            # Try to parse as integer (webcam index)
            source = int(self.source)
        except ValueError:
            source = self.source
            
        self._cap = cv2.VideoCapture(source)
        
        if not self._cap.isOpened():
            logger.error(f"Failed to open video source: {self.source}")
            return False
        
        # Get video properties
        self._source_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"Opened video: {self.source}")
        logger.info(f"  Resolution: {self._width}x{self._height}")
        logger.info(f"  FPS: {self._source_fps:.2f}")
        logger.info(f"  Total frames: {self._total_frames}")
        
        return True
    
    def close(self) -> None:
        """Release video capture resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Video source closed")
    
    def read_frame(self) -> Optional[FrameInfo]:
        """
        Read a single frame.
        
        Returns:
            FrameInfo if successful, None if end of video or error
        """
        if self._cap is None or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret:
            return None
        
        # Resize if needed
        if self.resize_width and self.resize_height:
            frame = cv2.resize(frame, (self.resize_width, self.resize_height))
        
        # Calculate timestamp
        timestamp = self._frame_count / self._source_fps if self._source_fps > 0 else 0
        
        frame_info = FrameInfo(
            frame=frame,
            frame_id=self._frame_count,
            timestamp=timestamp,
            fps=self._source_fps
        )
        
        self._frame_count += 1
        return frame_info
    
    def frames(self) -> Generator[FrameInfo, None, None]:
        """
        Generator that yields frames from the video.
        
        Handles frame skipping if target_fps is set.
        
        Yields:
            FrameInfo for each frame
        """
        if self._cap is None:
            if not self.open():
                return
        
        # Calculate frame skip interval if target FPS is set
        skip_interval = 1
        if self.target_fps and self._source_fps > 0:
            skip_interval = max(1, int(self._source_fps / self.target_fps))
        
        frame_counter = 0
        while True:
            frame_info = self.read_frame()
            if frame_info is None:
                break
            
            # Skip frames if needed
            if frame_counter % skip_interval == 0:
                yield frame_info
            
            frame_counter += 1
        
        self.close()
    
    @property
    def fps(self) -> float:
        """Get source FPS."""
        return self._source_fps
    
    @property
    def frame_count(self) -> int:
        """Get current frame count."""
        return self._frame_count
    
    @property
    def total_frames(self) -> int:
        """Get total frames in video (0 for streams)."""
        return self._total_frames
    
    @property
    def resolution(self) -> Tuple[int, int]:
        """Get video resolution (width, height)."""
        return (self._width, self._height)
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
