# Traffic Data Service
# Handles OSRM routing, traffic simulation, and zone-based caching

import json
import math
import time
import random
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional


class TrafficService:
    """Service for generating traffic simulation data using OSRM with zone-based caching."""

    FALLBACK_NAMES = [
        "Đường Dân Sinh", "Đường Nội Thị", "Đường Liên Xã", "Đường Giao Thông"
    ]

    def __init__(self):
        self._zones = []
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_zones()

    def _load_zones(self):
        """Load zone definitions from traffic_zones.json."""
        zones_path = Path(__file__).parent.parent / "data" / "traffic_zones.json"
        try:
            with open(zones_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._zones = data.get("zones", [])
            print(f"📍 Loaded {len(self._zones)} traffic zones")
        except Exception as e:
            print(f"⚠️ Failed to load traffic zones: {e}")
            self._zones = []

    def get_all_zones(self) -> List[Dict[str, Any]]:
        """Return all zone configs (without keywords, for API response)."""
        return [
            {
                "id": z["id"],
                "name": z["name"],
                "province": z["province"],
                "center": z["center"],
                "radius_km": z["radius_km"],
            }
            for z in self._zones
        ]

    def get_zone_by_id(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a zone by its id."""
        for z in self._zones:
            if z["id"] == zone_id:
                return z
        return None

    def _match_zone(self, text: str) -> Optional[Dict[str, Any]]:
        """Find a zone whose keywords appear in the given text."""
        text_lower = text.lower()
        for z in self._zones:
            for kw in z.get("keywords", []):
                if kw in text_lower:
                    return z
        # Default to first zone if no keyword match
        return self._zones[0] if self._zones else None

    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate Haversine distance in kilometers."""
        R_earth = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R_earth * c

    def _generate_routes(self, lat: float, lng: float, radius_km: float = 3.0,
                         target_routes: int = 8) -> List[Dict[str, Any]]:
        """
        Generate traffic simulation routes with OSRM routing.
        Returns real road geometries with street names.
        """
        print(f"🗺️ Generating traffic data for ({lat}, {lng}), radius={radius_km}km")

        traffic_data = []
        # Convert radius_km to approximate degree spread (~0.009 per km at this latitude)
        R = radius_km * 0.009
        max_attempts = 25
        attempts = 0
        fallback_counter = 0

        while len(traffic_data) < target_routes and attempts < max_attempts:
            attempts += 1

            start_lat = lat + (random.random() - 0.5) * R
            start_lng = lng + (random.random() - 0.5) * R
            end_lat = start_lat + (random.random() - 0.5) * 0.015
            end_lng = start_lng + (random.random() - 0.5) * 0.015

            try:
                url = (f"http://router.project-osrm.org/route/v1/driving/"
                       f"{start_lng},{start_lat};{end_lng},{end_lat}"
                       f"?overview=full&geometries=geojson&steps=true")

                response = requests.get(url, timeout=5)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('code') == 'Ok' and data.get('routes'):
                        route = data['routes'][0]
                        street_name = None

                        if route.get('legs') and route['legs'][0].get('summary'):
                            street_name = route['legs'][0]['summary']

                        if not street_name and route.get('legs') and route['legs'][0].get('steps'):
                            for step in route['legs'][0]['steps']:
                                if (step.get('name') and step['name'].strip() and
                                    step['name'].lower() != 'unnamed road'):
                                    street_name = step['name']
                                    break

                        if not street_name or 'unnamed' in street_name.lower():
                            continue

                        coordinates = [[coord[1], coord[0]]
                                       for coord in route['geometry']['coordinates']]

                        severity = 'severe' if random.random() > 0.5 else 'moderate'

                        traffic_data.append({
                            'name': street_name,
                            'coordinates': coordinates,
                            'severity': severity,
                            'distance': route.get('distance', 0),
                            'duration': route.get('duration', 0),
                            'isFallback': False
                        })

                        print(f"✅ Route {len(traffic_data)}/{target_routes}: {street_name} ({severity})")

            except Exception as e:
                fallback_counter += 1
                fallback_name = f"{random.choice(self.FALLBACK_NAMES)} {chr(65 + fallback_counter % 26)}"
                coordinates = [[start_lat, start_lng], [end_lat, end_lng]]
                severity = 'severe' if random.random() > 0.5 else 'moderate'
                distance = self.calculate_distance(start_lat, start_lng, end_lat, end_lng) * 1000

                traffic_data.append({
                    'name': fallback_name,
                    'coordinates': coordinates,
                    'severity': severity,
                    'distance': distance,
                    'duration': round(distance / 8.33),
                    'isFallback': True
                })

                print(f"⚠️ Fallback route {len(traffic_data)}/{target_routes}: {fallback_name}")

            time.sleep(0.15)

        print(f"✅ Generated {len(traffic_data)} traffic routes")
        return traffic_data

    def get_traffic_data(self, zone_id: Optional[str] = None,
                         lat: Optional[float] = None, lng: Optional[float] = None,
                         radius_km: Optional[float] = None,
                         target_routes: int = 8) -> Dict[str, Any]:
        """
        Get traffic data for a zone or a dynamic geolocation.

        Priority:
        1. zone_id → use predefined zone config
        2. lat/lng provided → dynamic geolocation mode (user's GPS position)
        3. Neither → fall back to first predefined zone

        Returns { zone: {...}, routes: [...] }.
        """
        # --- Mode 1: predefined zone ---
        zone = None
        if zone_id:
            zone = self.get_zone_by_id(zone_id)

        # --- Mode 2: dynamic geolocation (lat/lng provided explicitly) ---
        if not zone and lat is not None and lng is not None:
            r_km = radius_km or 10.0
            # Round to 3 decimals (~110m) for a stable cache key
            cache_key = f"geo_{round(lat,3)}_{round(lng,3)}_{r_km}"

            if cache_key in self._cache:
                print(f"📦 Returning cached geolocation data for '{cache_key}'")
                return self._cache[cache_key]

            routes = self._generate_routes(lat, lng, radius_km=r_km, target_routes=target_routes)

            zone_info = {
                "id": cache_key,
                "name": "Vị trí hiện tại của bạn",
                "center": {"lat": lat, "lng": lng},
                "radius_km": r_km,
            }

            result = {"zone": zone_info, "routes": routes}
            self._cache[cache_key] = result
            return result

        # --- Mode 3: fall back to first predefined zone ---
        if not zone and self._zones:
            zone = self._zones[0]

        if zone:
            z_id = zone["id"]
            center_lat = zone["center"]["lat"]
            center_lng = zone["center"]["lng"]
            z_radius = zone["radius_km"]
        else:
            z_id = "__default__"
            center_lat = 12.6976
            center_lng = 108.0674
            z_radius = 3.0

        if z_id in self._cache:
            print(f"📦 Returning cached traffic data for zone '{z_id}'")
            return self._cache[z_id]

        routes = self._generate_routes(center_lat, center_lng, radius_km=z_radius, target_routes=target_routes)

        zone_info = {
            "id": zone["id"] if zone else "__default__",
            "name": zone["name"] if zone else "Khu vực mặc định",
            "center": {"lat": center_lat, "lng": center_lng},
            "radius_km": z_radius,
        }

        result = {"zone": zone_info, "routes": routes}
        self._cache[z_id] = result
        return result

    def get_traffic_summary(self, message: str) -> Optional[str]:
        """
        Build a Vietnamese text summary of current congestion for the chatbot.
        Scans message for zone keywords, looks up (or generates) cached data,
        and formats a human-readable summary.
        """
        zone = self._match_zone(message)
        if not zone:
            return None

        z_id = zone["id"]

        # Use cached data or generate
        if z_id not in self._cache:
            self.get_traffic_data(zone_id=z_id)

        cached = self._cache.get(z_id)
        if not cached or not cached.get("routes"):
            return None

        routes = cached["routes"]
        zone_name = cached["zone"]["name"]

        severe = [r for r in routes if r["severity"] == "severe"]
        moderate = [r for r in routes if r["severity"] == "moderate"]

        lines = [f"📍 Tình hình giao thông tại **{zone_name}**:\n"]

        if severe:
            lines.append(f"🔴 **Tắc nghiêm trọng** ({len(severe)} tuyến):")
            for r in severe:
                dist_km = r.get("distance", 0) / 1000
                lines.append(f"  - {r['name']} ({dist_km:.1f} km)")

        if moderate:
            lines.append(f"🟡 **Đông xe** ({len(moderate)} tuyến):")
            for r in moderate:
                dist_km = r.get("distance", 0) / 1000
                lines.append(f"  - {r['name']} ({dist_km:.1f} km)")

        lines.append(f"\nTổng cộng: {len(routes)} tuyến đường đang có tình trạng ùn tắc/đông xe.")
        lines.append("*(Dữ liệu mô phỏng từ hệ thống giám sát giao thông)*")

        return "\n".join(lines)

    def get_traffic_summary_by_location(
        self, lat: float, lng: float, radius_km: float = 10
    ) -> Optional[str]:
        """
        Build a Vietnamese text summary of congestion around a GPS position.
        Uses the same cache as get_traffic_data (geolocation mode).
        """
        data = self.get_traffic_data(lat=lat, lng=lng, radius_km=radius_km)
        routes = data.get("routes", [])
        if not routes:
            return None

        zone_name = data.get("zone", {}).get("name", "Vị trí hiện tại")

        severe = [r for r in routes if r["severity"] == "severe"]
        moderate = [r for r in routes if r["severity"] == "moderate"]

        lines = [f"📍 Tình hình giao thông tại **{zone_name}** (bán kính {radius_km} km):\n"]

        if severe:
            lines.append(f"🔴 **Tắc nghiêm trọng** ({len(severe)} tuyến):")
            for r in severe:
                dist_km = r.get("distance", 0) / 1000
                lines.append(f"  - {r['name']} ({dist_km:.1f} km)")

        if moderate:
            lines.append(f"🟡 **Đông xe** ({len(moderate)} tuyến):")
            for r in moderate:
                dist_km = r.get("distance", 0) / 1000
                lines.append(f"  - {r['name']} ({dist_km:.1f} km)")

        lines.append(f"\nTổng cộng: {len(routes)} tuyến đường đang có tình trạng ùn tắc/đông xe.")
        lines.append("*(Dữ liệu mô phỏng từ hệ thống giám sát giao thông)*")

        return "\n".join(lines)

    def get_all_zones_summary(self) -> Optional[str]:
        """
        Build a combined Vietnamese text summary of congestion for ALL predefined zones.
        Always returns data regardless of user message or location.
        """
        if not self._zones:
            return None

        all_sections = []

        for zone in self._zones:
            z_id = zone["id"]
            data = self.get_traffic_data(zone_id=z_id)
            routes = data.get("routes", [])
            if not routes:
                continue

            zone_name = zone["name"]
            radius_km = zone.get("radius_km", 3)

            severe = [r for r in routes if r["severity"] == "severe"]
            moderate = [r for r in routes if r["severity"] == "moderate"]

            lines = [f"📍 **{zone_name}** ({zone.get('province', '')}, bán kính {radius_km} km):"]

            if severe:
                lines.append(f"  🔴 Tắc nghiêm trọng ({len(severe)} tuyến):")
                for r in severe:
                    dist_km = r.get("distance", 0) / 1000
                    lines.append(f"    - {r['name']} ({dist_km:.1f} km)")

            if moderate:
                lines.append(f"  🟡 Đông xe ({len(moderate)} tuyến):")
                for r in moderate:
                    dist_km = r.get("distance", 0) / 1000
                    lines.append(f"    - {r['name']} ({dist_km:.1f} km)")

            lines.append(f"  Tổng: {len(routes)} tuyến ùn tắc/đông xe.")
            all_sections.append("\n".join(lines))

        if not all_sections:
            return None

        return "\n\n".join(all_sections)

    def get_combined_traffic_summary(
        self, lat: Optional[float] = None, lng: Optional[float] = None,
        message: str = "", radius_km: float = 10
    ) -> Optional[str]:
        """
        Build a combined summary that includes BOTH:
        1. GPS location routes (if lat/lng provided)
        2. All predefined fixed zone routes (always)

        Used by the chatbot to have full awareness of all traffic data.
        """
        parts = []

        # GPS location summary
        if lat is not None and lng is not None:
            gps_summary = self.get_traffic_summary_by_location(lat, lng, radius_km)
            if gps_summary:
                parts.append("🛰️ **DỮ LIỆU GIAO THÔNG TẠI VỊ TRÍ GPS CỦA BẠN:**\n" + gps_summary)

        # All fixed zone summaries
        zones_summary = self.get_all_zones_summary()
        if zones_summary:
            parts.append("🗺️ **DỮ LIỆU GIAO THÔNG TẠI CÁC KHU VỰC CỐ ĐỊNH:**\n" + zones_summary)

        if not parts:
            return None

        result = "\n\n---\n\n".join(parts)
        return result


# Singleton instance
traffic_service = TrafficService()
