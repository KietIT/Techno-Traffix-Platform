"""
Video Detection Main Entry Point.

Usage:
    python main.py --video <path_to_video>
    python main.py --video <path_to_video> --show
    python main.py --config config/config.yaml --video <path_to_video>
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.inference_pipeline import InferencePipeline, PipelineConfig


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Video Detection System - Detect vehicles and accidents in traffic videos"
    )
    
    # Video source
    parser.add_argument(
        "--video", "-v",
        type=str,
        required=True,
        help="Path to video file or RTSP URL (use '0' for webcam)"
    )
    
    # Configuration
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to YAML configuration file"
    )
    
    # Model
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="yolov8l.pt",
        help="Path to YOLO model weights"
    )
    
    parser.add_argument(
        "--device", "-d",
        type=str,
        default="cuda",
        choices=["cuda", "cpu"],
        help="Device for inference"
    )
    
    # Detection thresholds
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="Detection confidence threshold"
    )
    
    # Display
    parser.add_argument(
        "--show", "-s",
        action="store_true",
        help="Show preview window"
    )
    
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to process"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("Video Detection System")
    logger.info("=" * 50)
    
    # Create config
    if args.config:
        config = PipelineConfig.from_yaml(args.config)
    else:
        config = PipelineConfig(
            model_path=args.model,
            device=args.device,
            conf_threshold=args.conf
        )
    
    logger.info(f"Model: {config.model_path}")
    logger.info(f"Device: {config.device}")
    logger.info(f"Confidence threshold: {config.conf_threshold}")
    
    # Create pipeline
    pipeline = InferencePipeline(config=config)
    
    # Run pipeline
    logger.info(f"Processing video: {args.video}")
    
    try:
        accidents = pipeline.run(
            video_source=args.video,
            show_preview=args.show,
            max_frames=args.max_frames
        )
        
        # Report results
        logger.info("=" * 50)
        logger.info("DETECTION SUMMARY")
        logger.info("=" * 50)
        
        if accidents:
            logger.info(f"Total accidents detected: {len(accidents)}")
            for event in accidents:
                logger.info(f"  - {event}")
        else:
            logger.info("No accidents detected")
            
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise


if __name__ == "__main__":
    main()
