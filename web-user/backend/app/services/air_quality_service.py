# Air Quality Service
# Fetches real-time AQI data from Open-Meteo Air Quality API
# Completely free, no API key needed: https://open-meteo.com/

import time
import requests
import logging
from typing import List, Dict, Any, Optional

from app.core.config import WAQI_CACHE_TTL

logger = logging.getLogger(__name__)

# Open-Meteo Air Quality API
OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CURRENT_PARAMS = "us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,uv_index"


class AirQualityService:
    """Service for fetching real-time AQI data from Open-Meteo (free, no key)."""

    HEALTH_LEVELS = [
        {"max": 50, "key": "good", "label": "Tốt", "color": "#10b981",
         "advice": "Chất lượng không khí tốt. Thích hợp cho mọi hoạt động ngoài trời."},
        {"max": 100, "key": "moderate", "label": "Trung bình", "color": "#f59e0b",
         "advice": "Chấp nhận được. Người nhạy cảm nên hạn chế hoạt động ngoài trời kéo dài."},
        {"max": 150, "key": "unhealthy_sensitive", "label": "Không tốt cho nhóm nhạy cảm", "color": "#f97316",
         "advice": "Trẻ em, người già, người có bệnh hô hấp nên hạn chế ra ngoài."},
        {"max": 200, "key": "unhealthy", "label": "Không tốt", "color": "#ef4444",
         "advice": "Mọi người nên hạn chế hoạt động ngoài trời. Đeo khẩu trang khi ra ngoài."},
        {"max": 300, "key": "very_unhealthy", "label": "Rất không tốt", "color": "#7c3aed",
         "advice": "Cảnh báo sức khỏe! Hạn chế tối đa ra ngoài. Đóng cửa sổ."},
        {"max": 999, "key": "hazardous", "label": "Nguy hiểm", "color": "#991b1b",
         "advice": "NGUY HIỂM! Ở trong nhà. Sử dụng máy lọc không khí nếu có."},
    ]

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = WAQI_CACHE_TTL
        print("🌬️ Air quality service initialized (Open-Meteo, free, no API key)")

    def _get_health_info(self, aqi: int) -> Dict[str, str]:
        for level in self.HEALTH_LEVELS:
            if aqi <= level["max"]:
                return {"label": level["label"], "color": level["color"], "advice": level["advice"]}
        return self.HEALTH_LEVELS[-1]

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache:
            return False
        return (time.time() - self._cache[key]["_ts"]) < self._cache_ttl

    def _fetch_point(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """Fetch AQI data for a single coordinate from Open-Meteo."""
        try:
            resp = requests.get(OPEN_METEO_URL, params={
                "latitude": lat,
                "longitude": lng,
                "current": CURRENT_PARAMS,
                "timezone": "auto",
            }, timeout=10)

            if resp.status_code != 200:
                return None

            data = resp.json()
            current = data.get("current")
            if not current:
                return None

            aqi = current.get("us_aqi")
            if aqi is None:
                return None

            health = self._get_health_info(aqi)

            return {
                "lat": data.get("latitude", lat),
                "lng": data.get("longitude", lng),
                "aqi": aqi,
                "status": health["label"],
                "color": health["color"],
                "advice": health["advice"],
                "pollutants": {
                    "PM2.5": current.get("pm2_5"),
                    "PM10": current.get("pm10"),
                    "O₃": current.get("ozone"),
                    "NO₂": current.get("nitrogen_dioxide"),
                    "SO₂": current.get("sulphur_dioxide"),
                    "CO": current.get("carbon_monoxide"),
                },
                "uv_index": current.get("uv_index"),
                "time": current.get("time", ""),
                "elevation": data.get("elevation"),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Open-Meteo request failed for ({lat},{lng}): {e}")
            return None

    def get_aqi_grid(self, lat: float, lng: float, radius_km: float = 5,
                     grid_size: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch AQI at a grid of points around (lat, lng) for spatial visualization.
        grid_size=3 produces a 3x3 grid = 9 points.
        """
        cache_key = f"grid_{round(lat, 2)}_{round(lng, 2)}_{radius_km}_{grid_size}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]

        # ~0.009 degrees per km
        offset = radius_km * 0.009
        step = (2 * offset) / (grid_size - 1) if grid_size > 1 else 0

        points = []
        for row in range(grid_size):
            for col in range(grid_size):
                p_lat = (lat - offset) + row * step
                p_lng = (lng - offset) + col * step
                result = self._fetch_point(p_lat, p_lng)
                if result:
                    points.append(result)

        self._cache[cache_key] = {"data": points, "_ts": time.time()}
        logger.info(f"AQI grid: {len(points)} points fetched around ({lat}, {lng})")
        return points

    def get_aqi_data(self, lat: float, lng: float, radius_km: float = 5) -> Dict[str, Any]:
        """
        Main method called by the API endpoint.
        Returns the center point detail + surrounding grid points.
        """
        cache_key = f"full_{round(lat, 3)}_{round(lng, 3)}_{radius_km}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Center point with full detail
        center = self._fetch_point(lat, lng)

        # Grid of surrounding points
        grid = self.get_aqi_grid(lat, lng, radius_km, grid_size=3)

        result = {
            "center": center,
            "stations": grid,
            "health_levels": [
                {"range": "0-50", "label": "Tốt", "color": "#10b981"},
                {"range": "51-100", "label": "Trung bình", "color": "#f59e0b"},
                {"range": "101-150", "label": "Không tốt (nhạy cảm)", "color": "#f97316"},
                {"range": "151-200", "label": "Không tốt", "color": "#ef4444"},
                {"range": "201-300", "label": "Rất không tốt", "color": "#7c3aed"},
                {"range": "301+", "label": "Nguy hiểm", "color": "#991b1b"},
            ],
            "_ts": time.time(),
        }

        self._cache[cache_key] = result
        return result


# Singleton
air_quality_service = AirQualityService()
