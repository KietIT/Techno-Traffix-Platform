"""
Techno TraffiX - Central Command Dashboard
Integrated with CustomTkinter, YOLOv8, Double DQN, and MQTT.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import argparse

# --- THƯ VIỆN AI & BACKEND ---
import cv2
import numpy as np
import torch
import paho.mqtt.client as mqtt
from config import *
from agent import DoubleDQNagent
from ultralytics import YOLO

_VD_DIR = Path(__file__).resolve().parent.parent / "video_detection"
sys.path.insert(0, str(_VD_DIR))
from detector.yolo_detector import YOLODetector  

_DEFAULT_ACCIDENT_MODEL = str(_VD_DIR / "accident_classification_yolov8l.pt")
_DEFAULT_AMBULANCE_MODEL = str(_VD_DIR / "vehicle_detection_yolov8l_ambulance.pt")

# --- CẤU HÌNH MQTT ---
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
WATER_TOPIC_DATA = "KHKT_DQN/water"
WATER_TOPIC_CMD = "KHKT_DQN/water/control"

# ── Color Palette ──────────────────────────────────────────────
COLORS = {
    "bg_dark": "#1a1a2e", "bg_header": "#16213e", "bg_card": "#ffffff",
    "bg_card_dark": "#f8f9fa", "bg_upload": "#e8ecf1", "primary": "#2196F3",
    "primary_dark": "#1976D2", "accent": "#00bcd4", "danger": "#e74c3c",
    "danger_dark": "#c0392b", "success": "#27ae60", "success_dark": "#1e8449",
    "warning": "#f39c12", "orange": "#e67e22", "text_dark": "#2c3e50",
    "text_light": "#ffffff", "text_muted": "#7f8c8d", "border": "#dfe6e9",
    "badge_live": "#e74c3c", "node_green": "#27ae60", "mode_auto": "#16213e",
}

INTERSECTIONS = {
    "Ngã tư 1 (Lê Hồng Phong)": {
        "short": "Ngã tư 1 (LHP)", 
        "cameras": ["Cam 1 - Hướng Bắc", "Cam 2 - Hướng Nam", "Cam 3 - Hướng Đông", "Cam 4 - Hướng Tây"],
        "topic": "KHKT_DQN/traffic_control"  
    },
    "Ngã tư 2 (Nguyễn Trãi)": {
        "short": "Ngã tư 2 (NT)", 
        "cameras": ["Cam 1 - Hướng Bắc", "Cam 2 - Hướng Nam", "Cam 3 - Hướng Đông", "Cam 4 - Hướng Tây"],
        "topic": "KHKT_DQN/traffic_control_node2"  
    },
    "Ngã tư 3 (Lê Lợi)": {
        "short": "Ngã tư 3 (LL)", 
        "cameras": ["Cam 1 - Hướng Bắc", "Cam 2 - Hướng Nam", "Cam 3 - Hướng Đông", "Cam 4 - Hướng Tây"],
        "topic": "KHKT_DQN/water"  
    },
}

# --- LÕI TÍNH TOÁN DQN ---
class TrafficDataConnector:
    def __init__(self):
        self.current_group = 0  
        self.time_active = 0    

    def update_light_state(self, action_taken, block_time):
        if action_taken == self.current_group: self.time_active += block_time
        else:
            self.current_group = action_taken
            self.time_active = block_time 

    def _calculate_weighted_queue(self, vehicle_counts): 
        weight_map = {"motorcycle": 0.3, "car": 1.1, "bus": 2.5, "truck": 3.0}
        return sum(count * weight_map.get(v_class.lower(), 1.0) for v_class, count in vehicle_counts.items())

    def process_traffic_data(self, data):
        directions = data.get("directions", {})
        counts_n = directions.get("north", {}).get("vehicle_counts", {})
        counts_s = directions.get("south", {}).get("vehicle_counts", {})
        counts_e = directions.get("east", {}).get("vehicle_counts", {})
        counts_w = directions.get("west", {}).get("vehicle_counts", {})

        q_n = np.clip(self._calculate_weighted_queue(counts_n) / MAX_CAPACITY, 0.0, 1.5)
        q_s = np.clip(self._calculate_weighted_queue(counts_s) / MAX_CAPACITY, 0.0, 1.5)
        q_e = np.clip(self._calculate_weighted_queue(counts_e) / MAX_CAPACITY, 0.0, 1.5)
        q_w = np.clip(self._calculate_weighted_queue(counts_w) / MAX_CAPACITY, 0.0, 1.5)

        phase_one_hot = np.zeros(4, dtype=np.float32)
        if self.current_group == 0: phase_one_hot[0] = 1.0 
        else: phase_one_hot[2] = 1.0

        time_duration = min(self.time_active / BLOCK_TIME, 2.0)

        amb_n = directions.get("north", {}).get("has_ambulance", False)
        amb_s = directions.get("south", {}).get("has_ambulance", False)
        amb_e = directions.get("east", {}).get("has_ambulance", False)
        amb_w = directions.get("west", {}).get("has_ambulance", False)

        prio_ns = 1.0 if (amb_n or amb_s) else 0.0
        prio_ew = 1.0 if (amb_e or amb_w) else 0.0

        state = np.array([q_n, q_s, q_e, q_w, phase_one_hot[0], phase_one_hot[1], phase_one_hot[2], phase_one_hot[3], time_duration, prio_ns, prio_ew], dtype=np.float32)

        override_action = None
        if prio_ns == 1.0: override_action = 0 
        elif prio_ew == 1.0: override_action = 1 
        elif self.time_active < MIN_GREEN_TIME: override_action = self.current_group 
        elif self.time_active >= MAX_GREEN_TIME: override_action = 1 if self.current_group == 0 else 0 

        return state, override_action

# --- GIAO DIỆN CHÍNH ---
class SmartFixDashboard:
    def __init__(self, root, img_paths, topic):
        self.root = root
        self.current_intersection = list(INTERSECTIONS.keys())[0]

        for name, data in INTERSECTIONS.items():
            if data["topic"] == topic:
                self.current_intersection = name
                break
        self.topic = INTERSECTIONS[self.current_intersection]["topic"]
        
        node_name = self.topic.split("/")[-1].upper()
        self.root.title(f"Techno TraffiX - Central Command ({node_name})")
        self.root.configure(bg=COLORS["bg_dark"])

        # ── State UI ──
        self.image_refs = [None, None, None, None]  
        self.photo_refs = [None, None, None, None]  
        self.image_paths = img_paths.copy() if img_paths else [None, None, None, None]
        self.uploaded_count = sum(1 for p in self.image_paths if p is not None)
        self.current_intersection = list(INTERSECTIONS.keys())[0]
        
        # ── State Backend & Traffic Light ──
        self.operation_mode = tk.StringVar(value="auto") # manual, auto, ai
        self.manual_action = 0 # 0: Dọc, 1: Ngang, 2: Dừng tất cả
        self.is_processing = False
        self.ai_thread = None
        self.stop_thread = False

        self.current_action = 0 # Mặc định khởi động Xanh Bắc-Nam
        self.target_action = 0
        self.is_transitioning = False
        self.transition_start = 0
        self.countdown = 30
        self.has_accident = False
        self.has_ambulance = False
        self.last_tick = time.time()
        self.blink_state = False

        self.stats = {
            "fps": 0.0, "total_cars": 0,
            "emergency": False, "accident": False,
        }

        # ── Window sizing ──
        self.root.state("zoomed")  
        self.root.minsize(1200, 700)

        # ── Build UI ──
        self._setup_styles()
        self._build_header()
        self._build_main_content()

        if self.uploaded_count == 4:
            for i in range(4):
                if os.path.exists(self.image_paths[i]):
                    try:
                        self.image_refs[i] = Image.open(self.image_paths[i])
                        self.root.after(100, lambda idx=i: self._display_image_on_canvas(idx))
                        self.root.after(100, lambda idx=i: self.badge_labels[idx].grid())
                        self.root.after(100, lambda idx=i: self.node_labels[idx].place(x=8, y=8))
                        self.root.after(100, lambda idx=i: self.mode_labels[idx].place(x=8, rely=1.0, y=-30))
                    except: pass
            
            self.upload_progress_label.config(text="Sẵn sàng phân tích!", fg=COLORS["success"])
            self.start_btn.config(state="normal", bg=COLORS["success"], cursor="hand2")

        # ── Cập nhật trạng thái Ngã tư lần đầu ──
        self._toggle_intersection_features()

        # ── MQTT ──
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"[{node_name}] MQTT Connected to {MQTT_BROKER}")
        except:
            print(f"[{node_name}] MQTT Connection Failed!")

        self.update_clock() # Bật vòng lặp UI
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ══════════════════════════════════════════════════════════════
    #  STYLES & UI BUILDERS
    # ══════════════════════════════════════════════════════════════
    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Header.TFrame", background=COLORS["bg_header"])
        self.style.configure("Header.TLabel", background=COLORS["bg_header"], foreground=COLORS["text_light"], font=("Segoe UI", 14, "bold"))
        self.style.configure("Card.TFrame", background=COLORS["bg_card"])
        self.style.configure("Card.TLabel", background=COLORS["bg_card"], foreground=COLORS["text_dark"])
        self.style.configure("CardTitle.TLabel", background=COLORS["bg_card"], foreground=COLORS["text_dark"], font=("Segoe UI", 11, "bold"))
        self.style.configure("StatValue.TLabel", background=COLORS["bg_card"], foreground=COLORS["text_dark"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["bg_card"], foreground=COLORS["text_muted"], font=("Segoe UI", 9))
        self.style.configure("Custom.TCombobox", fieldbackground=COLORS["bg_card"], background=COLORS["primary"])

    def _build_header(self):
        header = ttk.Frame(self.root, style="Header.TFrame", height=48)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        title_frame = ttk.Frame(header, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(title_frame, text="\u2630", font=("Segoe UI", 16), bg=COLORS["bg_header"], fg=COLORS["text_light"]).pack(side=tk.LEFT, padx=(0, 10))
        
        node_name = self.topic.split("/")[-1].upper()
        self.header_label = ttk.Label(title_frame, text=f"Techno Traffix - Central Command | {node_name}", style="Header.TLabel")
        self.header_label.pack(side=tk.LEFT)
        
        tk.Label(header, text="\u2699", font=("Segoe UI", 18), bg=COLORS["bg_header"], fg=COLORS["accent"], cursor="hand2").pack(side=tk.RIGHT, padx=16)

    def _build_main_content(self):
        main = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        main.columnconfigure(0, weight=7)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)
        self._build_left_panel(main)
        self._build_right_panel(main)

    def _build_left_panel(self, parent):
        self.left_frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.left_frame.columnconfigure(0, weight=1)
        self.left_frame.columnconfigure(1, weight=1)
        self.left_frame.rowconfigure(0, weight=1)
        self.left_frame.rowconfigure(1, weight=1)

        self.camera_frames, self.camera_canvases = [], []
        self.camera_labels, self.badge_labels = [], []
        self.node_labels, self.mode_labels = [], []

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        cam_names = INTERSECTIONS[self.current_intersection]["cameras"]

        for idx, (r, c) in enumerate(positions):
            frame = tk.Frame(self.left_frame, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
            frame.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)

            top_bar = tk.Frame(frame, bg=COLORS["bg_card"], height=28)
            top_bar.grid(row=0, column=0, sticky="ew")
            top_bar.columnconfigure(0, weight=1)
            top_bar.grid_propagate(False)

            cam_label = tk.Label(top_bar, text=f"  {cam_names[idx]}", font=("Segoe UI", 9), bg=COLORS["bg_card"], fg=COLORS["text_dark"], anchor="w")
            cam_label.grid(row=0, column=0, sticky="w", padx=4, pady=2)
            self.camera_labels.append(cam_label)

            badge = tk.Label(top_bar, text=" LIVE ", font=("Segoe UI", 7, "bold"), bg=COLORS["badge_live"], fg=COLORS["text_light"])
            badge.grid(row=0, column=1, sticky="e", padx=6, pady=4)
            badge.grid_remove() 
            self.badge_labels.append(badge)

            canvas = tk.Canvas(frame, bg=COLORS["bg_upload"], highlightthickness=0, cursor="hand2")
            canvas.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
            canvas.bind("<Button-1>", lambda e, i=idx: self.upload_image(i))
            canvas.bind("<Configure>", lambda e, i=idx: self._draw_placeholder(i))
            self.camera_canvases.append(canvas)

            node_lbl = tk.Label(canvas, text=f"NODE {idx + 1}: YOLOV8", font=("Consolas", 9, "bold"), bg=COLORS["node_green"], fg=COLORS["text_light"], padx=6, pady=1)
            self.node_labels.append(node_lbl)

            mode_lbl = tk.Label(canvas, text="Mode: AUTO", font=("Consolas", 8), bg=COLORS["mode_auto"], fg=COLORS["text_light"], padx=6, pady=1)
            self.mode_labels.append(mode_lbl)
            self.camera_frames.append(frame)

    def _draw_placeholder(self, idx):
        canvas = self.camera_canvases[idx]
        canvas.delete("placeholder")

        if self.image_refs[idx] is not None:
            self._display_image_on_canvas(idx)
            return

        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 10 or h < 10: return

        pad = 20
        canvas.create_rectangle(pad, pad, w - pad, h - pad, outline=COLORS["text_muted"], dash=(6, 4), width=2, tags="placeholder")
        canvas.create_text(w // 2, h // 2 - 15, text="\U0001F4F7", font=("Segoe UI", 28), fill=COLORS["text_muted"], tags="placeholder")
        canvas.create_text(w // 2, h // 2 + 20, text="Nhấn để tải ảnh / video", font=("Segoe UI", 10), fill=COLORS["text_muted"], tags="placeholder")
        canvas.create_text(w // 2, h // 2 + 42, text=INTERSECTIONS[self.current_intersection]["cameras"][idx], font=("Segoe UI", 9), fill=COLORS["primary"], tags="placeholder")

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=COLORS["bg_dark"])
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)
        right.rowconfigure(3, weight=0)
        right.rowconfigure(4, weight=0)

        self._build_control_area(right)
        self._build_statistics(right)
        self._build_start_button(right)
        self._build_traffic_light_control(right)
        self._build_operation_mode(right)

    def _make_card(self, parent, row):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        card.grid(row=row, column=0, sticky="nsew", pady=3)
        return card

    def _build_control_area(self, parent):
        card = self._make_card(parent, row=0)
        title_frame = tk.Frame(card, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(title_frame, text="\u2699", font=("Segoe UI", 13), bg=COLORS["bg_card"], fg=COLORS["primary"]).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="  Khu vực điều khiển", style="CardTitle.TLabel").pack(side=tk.LEFT)

        combo_frame = tk.Frame(card, bg=COLORS["bg_card"])
        combo_frame.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(combo_frame, text="\U0001F4CD", font=("Segoe UI", 12), bg=COLORS["bg_card"], fg=COLORS["danger"]).pack(side=tk.LEFT, padx=(0, 4))

        self.intersection_var = tk.StringVar(value=self.current_intersection)
        self.combo = ttk.Combobox(combo_frame, textvariable=self.intersection_var, values=list(INTERSECTIONS.keys()), state="readonly", font=("Segoe UI", 10))
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo.bind("<<ComboboxSelected>>", self.reset_dashboard)
        ttk.Label(card, text="(Nhấn vào video hoặc chọn menu để đổi quyền điều khiển)", style="Muted.TLabel").pack(padx=16, pady=(0, 10))

    def _build_statistics(self, parent):
        card = self._make_card(parent, row=1)
        title_frame = tk.Frame(card, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(title_frame, text="\U0001F4CA", font=("Segoe UI", 12), bg=COLORS["bg_card"], fg=COLORS["primary"]).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="  Thống kê", style="CardTitle.TLabel").pack(side=tk.LEFT)
        
        self.stats_intersection_label = ttk.Label(title_frame, text=INTERSECTIONS[self.current_intersection]["short"], style="StatValue.TLabel", foreground=COLORS["primary"])
        self.stats_intersection_label.pack(side=tk.RIGHT)
        ttk.Separator(card, orient="horizontal").pack(fill=tk.X, padx=12, pady=2)

        stats_body = tk.Frame(card, bg=COLORS["bg_card"])
        stats_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # --- GIAO DIỆN NƯỚC MỚI THEO Ý BẠN CHUẨN OLED ---
        water_container = tk.Frame(stats_body, bg=COLORS["bg_card"])
        water_container.pack(fill=tk.X, pady=4)

        tk.Label(water_container, text="\U0001F4A7 CẢM BIẾN MỰC NƯỚC (mm)", font=("Segoe UI", 9, "bold"), bg=COLORS["bg_card"], fg=COLORS["primary"]).pack(anchor="w", pady=(0, 4))

        data_frame = tk.Frame(water_container, bg="#2d3436", padx=8, pady=8)
        data_frame.pack(fill=tk.X)
        data_frame.columnconfigure(1, weight=1)
        data_frame.columnconfigure(2, weight=1)

        # Header 
        tk.Label(data_frame, text="", bg="#2d3436", width=5).grid(row=0, column=0)
        tk.Label(data_frame, text="Left", font=("Consolas", 10, "bold"), bg="#2d3436", fg="#dfe6e9").grid(row=0, column=1)
        tk.Label(data_frame, text="Right", font=("Consolas", 10, "bold"), bg="#2d3436", fg="#dfe6e9").grid(row=0, column=2)

        # Hàng AVG
        tk.Label(data_frame, text="AVG", font=("Consolas", 10, "bold"), bg="#2d3436", fg="#00bcd4").grid(row=1, column=0, sticky="w", pady=4)
        self.lbl_avg_l = tk.Label(data_frame, text="--", font=("Consolas", 16, "bold"), bg="#2d3436", fg="white")
        self.lbl_avg_l.grid(row=1, column=1)
        self.lbl_avg_r = tk.Label(data_frame, text="--", font=("Consolas", 16, "bold"), bg="#2d3436", fg="white")
        self.lbl_avg_r.grid(row=1, column=2)

        # Hàng D
        tk.Label(data_frame, text="D", font=("Consolas", 10, "bold"), bg="#2d3436", fg="#e74c3c").grid(row=2, column=0, sticky="w", pady=4)
        self.lbl_max_l = tk.Label(data_frame, text="--", font=("Consolas", 16, "bold"), bg="#2d3436", fg="white")
        self.lbl_max_l.grid(row=2, column=1)
        self.lbl_max_r = tk.Label(data_frame, text="--", font=("Consolas", 16, "bold"), bg="#2d3436", fg="white")
        self.lbl_max_r.grid(row=2, column=2)

        # Nút điều khiển nước
        water_btn_frame = tk.Frame(water_container, bg=COLORS["bg_card"])
        water_btn_frame.pack(fill=tk.X, pady=(6, 0))
        
        self.btn_calib = tk.Button(water_btn_frame, text="Calib (r)", font=("Segoe UI", 8, "bold"), bg=COLORS["warning"], fg="white", relief="flat", cursor="hand2", command=lambda: self.mqtt_client.publish(WATER_TOPIC_CMD, "r"))
        self.btn_calib.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.btn_set = tk.Button(water_btn_frame, text="Set 100 (f)", font=("Segoe UI", 8, "bold"), bg=COLORS["success"], fg="white", relief="flat", cursor="hand2", command=lambda: self.mqtt_client.publish(WATER_TOPIC_CMD, "f"))
        self.btn_set.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)

        self.btn_pause = tk.Button(water_btn_frame, text="Pause (p)", font=("Segoe UI", 8, "bold"), bg=COLORS["danger"], fg="white", relief="flat", cursor="hand2", command=lambda: self.mqtt_client.publish(WATER_TOPIC_CMD, "p"))
        self.btn_pause.pack(side=tk.LEFT, padx=(4, 0), expand=True, fill=tk.X)
        # -------------------------------------------------------------------

        ttk.Separator(stats_body, orient="horizontal").pack(fill=tk.X, pady=10)

        fps_row = tk.Frame(stats_body, bg=COLORS["bg_card"])
        fps_row.pack(fill=tk.X, pady=2)
        tk.Label(fps_row, text="FPS:", font=("Segoe UI", 10, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"]).pack(side=tk.LEFT)
        self.fps_label = tk.Label(fps_row, text="0.0", font=("Segoe UI", 10, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"])
        self.fps_label.pack(side=tk.LEFT, padx=4)
        tk.Label(fps_row, text="Tổng xe:", font=("Segoe UI", 10, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"]).pack(side=tk.RIGHT, padx=(0, 0))
        self.total_cars_label = tk.Label(fps_row, text="0", font=("Segoe UI", 12, "bold"), bg=COLORS["bg_card"], fg=COLORS["primary"])
        self.total_cars_label.pack(side=tk.RIGHT, padx=(0, 4))

        ttk.Separator(stats_body, orient="horizontal").pack(fill=tk.X, pady=10)

        alert_frame = tk.Frame(stats_body, bg=COLORS["bg_card"])
        alert_frame.pack(fill=tk.X, pady=(2, 8))
        self.emergency_badge = tk.Label(alert_frame, text="  \U0001F6A8 Cấp cứu: KHÔNG  ", font=("Segoe UI", 8, "bold"), bg=COLORS["success"], fg=COLORS["text_light"], padx=4, pady=2)
        self.emergency_badge.pack(side=tk.LEFT, padx=(0, 6))
        self.accident_badge = tk.Label(alert_frame, text="  \u26A0 Tai nạn: KHÔNG  ", font=("Segoe UI", 8, "bold"), bg=COLORS["text_muted"], fg=COLORS["text_light"], padx=4, pady=2)
        self.accident_badge.pack(side=tk.LEFT)

    def _update_water_ui(self, avg_l, avg_r, max_l, max_r):
        """Hàm update thông số nước trên UI (Chỉ chạy khi ở Ngã tư Lê Lợi)"""
        if hasattr(self, 'lbl_avg_l') and self.current_intersection == "Ngã tư 3 (Lê Lợi)":
            self.lbl_avg_l.config(text=str(avg_l))
            self.lbl_avg_r.config(text=str(avg_r))
            self.lbl_max_l.config(text=str(max_l))
            self.lbl_max_r.config(text=str(max_r))

    def _build_start_button(self, parent):
        card = self._make_card(parent, row=2)
        btn_frame = tk.Frame(card, bg=COLORS["bg_card"])
        btn_frame.pack(fill=tk.X, padx=12, pady=10)

        self.start_btn = tk.Button(btn_frame, text="\u25B6  BẮT ĐẦU PHÂN TÍCH", font=("Segoe UI", 11, "bold"), bg=COLORS["text_muted"], fg=COLORS["text_light"], activebackground=COLORS["success_dark"], activeforeground=COLORS["text_light"], relief="flat", padx=20, pady=8, state="disabled", cursor="arrow", command=self.start_processing)
        self.start_btn.pack(fill=tk.X)

        self.upload_progress_label = tk.Label(btn_frame, text="Tải lên 0/4 hình ảnh để bắt đầu", font=("Segoe UI", 8), bg=COLORS["bg_card"], fg=COLORS["text_muted"])
        self.upload_progress_label.pack(pady=(4, 0))

    def _build_traffic_light_control(self, parent):
        card = self._make_card(parent, row=3)
        title_frame = tk.Frame(card, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(title_frame, text="\U0001F6A6", font=("Segoe UI", 12), bg=COLORS["bg_card"]).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="  Bảng điều khiển đèn", style="CardTitle.TLabel").pack(side=tk.LEFT)

        light_container = tk.Frame(card, bg=COLORS["bg_card"])
        # light_container.pack(fill=tk.X, padx=12, pady=10)
        light_container.columnconfigure(0, weight=1)
        light_container.columnconfigure(1, weight=1)

        ns_frame = tk.Frame(light_container, bg=COLORS["bg_card"])
        ns_frame.grid(row=0, column=0)
        tk.Label(ns_frame, text="BẮC - NAM", font=("Segoe UI", 10, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"]).pack()
        
        self.canvas_ns = tk.Canvas(ns_frame, width=36, height=90, bg="#333333", highlightthickness=2, highlightbackground="#111111")
        self.canvas_ns.pack(pady=5)
        self.draw_traffic_light_base(self.canvas_ns)
        
        self.lbl_time_ns = tk.Label(ns_frame, text="30s", font=("Segoe UI", 16, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"])
        self.lbl_time_ns.pack()

        ew_frame = tk.Frame(light_container, bg=COLORS["bg_card"])
        ew_frame.grid(row=0, column=1)
        tk.Label(ew_frame, text="ĐÔNG - TÂY", font=("Segoe UI", 10, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"]).pack()
        
        self.canvas_ew = tk.Canvas(ew_frame, width=36, height=90, bg="#333333", highlightthickness=2, highlightbackground="#111111")
        self.canvas_ew.pack(pady=5)
        self.draw_traffic_light_base(self.canvas_ew)
        
        self.lbl_time_ew = tk.Label(ew_frame, text="30s", font=("Segoe UI", 16, "bold"), bg=COLORS["bg_card"], fg=COLORS["text_dark"])
        self.lbl_time_ew.pack()

        btn_frame = tk.Frame(card, bg=COLORS["bg_card"])
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 10))
        btn_frame.columnconfigure(0, weight=1); btn_frame.columnconfigure(1, weight=1); btn_frame.columnconfigure(2, weight=1)

        self.btn_stop_all = tk.Button(btn_frame, text="\u23F9 DỪNG TẤT CẢ", font=("Segoe UI", 9, "bold"), bg=COLORS["danger"], fg=COLORS["text_light"], activebackground=COLORS["danger_dark"], activeforeground=COLORS["text_light"], relief="flat", pady=6, cursor="hand2", command=lambda: self._set_traffic_light("stop_all"))
        self.btn_stop_all.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.btn_horizontal = tk.Button(btn_frame, text="\U0001F7E2 Ưu tiên Ngang", font=("Segoe UI", 9, "bold"), bg=COLORS["primary"], fg=COLORS["text_light"], activebackground=COLORS["primary_dark"], activeforeground=COLORS["text_light"], relief="flat", pady=6, cursor="hand2", command=lambda: self._set_traffic_light("horizontal"))
        self.btn_horizontal.grid(row=0, column=1, sticky="ew", padx=3)

        self.btn_vertical = tk.Button(btn_frame, text="\U0001F7E2 Ưu tiên Dọc", font=("Segoe UI", 9, "bold"), bg=COLORS["success"], fg=COLORS["text_light"], activebackground=COLORS["success_dark"], activeforeground=COLORS["text_light"], relief="flat", pady=6, cursor="hand2", command=lambda: self._set_traffic_light("vertical"))
        self.btn_vertical.grid(row=0, column=2, sticky="ew", padx=(3, 0))

    def draw_traffic_light_base(self, canvas):
        canvas.create_oval(6, 6, 30, 30, fill="#555555", outline="#111111", tags="red")
        canvas.create_oval(6, 34, 30, 58, fill="#555555", outline="#111111", tags="yellow")
        canvas.create_oval(6, 62, 30, 86, fill="#555555", outline="#111111", tags="green")

    def set_light(self, canvas, state):
        canvas.itemconfig("red", fill="#555555")
        canvas.itemconfig("yellow", fill="#555555")
        canvas.itemconfig("green", fill="#555555")

        if state == "red":
            canvas.itemconfig("red", fill="#FF3B30")
        elif state == "yellow":
            canvas.itemconfig("yellow", fill="#FFCC00")
        elif state == "green":
            canvas.itemconfig("green", fill="#34C759")

    def _build_operation_mode(self, parent):
        card = self._make_card(parent, row=4)
        title_frame = tk.Frame(card, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(title_frame, text="\u2699", font=("Segoe UI", 12), bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="  Chế độ hoạt động", style="CardTitle.TLabel").pack(side=tk.LEFT)

        mode_frame = tk.Frame(card, bg=COLORS["bg_card"])
        mode_frame.pack(fill=tk.X, padx=12, pady=(0, 10))
        mode_frame.columnconfigure(0, weight=1); mode_frame.columnconfigure(1, weight=1); mode_frame.columnconfigure(2, weight=1)

        self.mode_buttons = {}
        modes = [("Manual", 0), ("Auto", 1), ("AI", 2)]

        for mode_name, col in modes:
            btn = tk.Button(mode_frame, text=mode_name, font=("Segoe UI", 10, "bold"), relief="flat", pady=6, cursor="hand2", command=lambda m=mode_name: self._set_mode(m))
            btn.grid(row=0, column=col, sticky="ew", padx=1)
            self.mode_buttons[mode_name] = btn

        self._set_mode("Auto")

    def _toggle_intersection_features(self):
        """Hàm dùng để chuyển đổi trạng thái Khóa/Mở Nước và Đèn theo đúng tên Ngã Tư"""
        is_le_loi = (self.current_intersection == "Ngã tư 3 (Lê Lợi)")
        
        # 1. Quản lý trạng thái chức năng Nước
        water_state = "normal" if is_le_loi else "disabled"
        self.btn_calib.config(state=water_state)
        self.btn_set.config(state=water_state)
        self.btn_pause.config(state=water_state)
        
        if not is_le_loi and hasattr(self, 'lbl_avg_l'):
            self.lbl_avg_l.config(text="--")
            self.lbl_avg_r.config(text="--")
            self.lbl_max_l.config(text="--")
            self.lbl_max_r.config(text="--")

        # 2. Quản lý trạng thái chức năng Đèn (Ngược lại với Nước)
        traffic_state = "disabled" if is_le_loi else "normal"
        self.btn_stop_all.config(state=traffic_state)
        self.btn_horizontal.config(state=traffic_state)
        self.btn_vertical.config(state=traffic_state)
        for btn in self.mode_buttons.values():
            btn.config(state=traffic_state)
            
        self.render_ui()

    # ══════════════════════════════════════════════════════════════
    #  LOGIC MQTT VÀ GIAO DIỆN ĐÈN
    # ══════════════════════════════════════════════════════════════
    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.mqtt_client.subscribe(self.topic)
        self.mqtt_client.subscribe(WATER_TOPIC_DATA) 

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            
            # --- 1. NẾU LÀ DATA TỪ CẢM BIẾN NƯỚC ---
            if msg.topic == WATER_TOPIC_DATA:
                avg_l = payload.get('avg_L', 'ERR')
                avg_r = payload.get('avg_R', 'ERR')
                max_l = payload.get('max_L', 'ERR')
                max_r = payload.get('max_R', 'ERR')
                
                self.root.after(0, lambda: self._update_water_ui(avg_l, avg_r, max_l, max_r))
                return 

            # --- 2. NẾU LÀ DATA ĐIỀU KHIỂN GIAO THÔNG ---
            action = payload.get("action", 0)
            self.has_ambulance = payload.get("has_ambulance", False)
            self.has_accident = payload.get("has_accident", False)
            mode = payload.get("mode", "auto")

            if mode != self.operation_mode.get():
                self.operation_mode.set(mode)
            
            if mode == "auto":
                if self.current_action == -1 or self.current_action == 2: 
                    self.current_action = 0
                    self.target_action = 0
                    self.countdown = 30
                    self.is_transitioning = False

            elif mode == "manual":
                if action != self.current_action and not self.is_transitioning:
                    self.target_action = action
                    self.is_transitioning = True
                    self.countdown = 2 # Bất đồng bộ 

            elif mode == "ai":
                if self.current_action == -1:
                    self.current_action = action
                    self.target_action = action
                    self.countdown = 10
                    self.is_transitioning = False
                elif action != self.current_action and not self.is_transitioning:
                    self.target_action = action
                    self.is_transitioning = True
                    self.transition_start = time.time()
                    self.countdown = 3
                elif action == self.current_action:
                    self.countdown = 10

            self.last_tick = time.time()
        except Exception as e:
            pass

    def update_clock(self):
        current_time = time.time()

        if current_time - self.last_tick >= 1.0:
            self.last_tick = current_time
            self.blink_state = not self.blink_state

            if self.countdown > 0:
                self.countdown -= 1

            mode = self.operation_mode.get()

            if mode == "auto":
                if self.countdown == 0:
                    if self.is_transitioning:
                        self.is_transitioning = False
                        self.current_action = self.target_action
                        self.countdown = 30
                    else:
                        self.is_transitioning = True
                        self.target_action = 1 if self.current_action == 0 else 0
                        self.countdown = 3

            elif mode == "manual" and self.is_transitioning and self.countdown == 0:
                self.is_transitioning = False
                self.current_action = self.target_action
                self.countdown = 0

        # AI mode: end transition by wall-clock (immune to last_tick resets)
        mode = self.operation_mode.get()
        if mode == "ai" and self.is_transitioning:
            if current_time - self.transition_start >= 3.0:
                self.is_transitioning = False
                self.current_action = self.target_action
                self.countdown = 7

        self.render_ui()
        self.root.after(100, self.update_clock)

    def render_ui(self):
        # 0. KHÓA ĐÈN NẾU LÀ NGÃ TƯ LÊ LỢI (Theo yêu cầu)
        if self.current_intersection == "Ngã tư 3 (Lê Lợi)":
            self.set_light(self.canvas_ns, "off")
            self.set_light(self.canvas_ew, "off")
            self.lbl_time_ns.config(text="--s", fg="black")
            self.lbl_time_ew.config(text="--s", fg="black")
            return

        mode = self.operation_mode.get()
        
        if self.has_accident and not self.has_ambulance:
            state = "yellow" if self.blink_state else "off"
            self.set_light(self.canvas_ns, state)
            self.set_light(self.canvas_ew, state)
            self.lbl_time_ns.config(text="--s", fg="black") 
            self.lbl_time_ew.config(text="--s", fg="black")
            return

        if self.is_transitioning:
            if self.current_action == 0: 
                self.set_light(self.canvas_ns, "yellow")
                self.set_light(self.canvas_ew, "red")
            else: 
                self.set_light(self.canvas_ns, "red")
                self.set_light(self.canvas_ew, "yellow")
        else:
            if self.current_action == 0: 
                self.set_light(self.canvas_ns, "green")
                self.set_light(self.canvas_ew, "red")
            elif self.current_action == 1: 
                self.set_light(self.canvas_ns, "red")
                self.set_light(self.canvas_ew, "green")
            elif self.current_action == 2: 
                self.set_light(self.canvas_ns, "red")
                self.set_light(self.canvas_ew, "red")
            else:
                self.set_light(self.canvas_ns, "off")
                self.set_light(self.canvas_ew, "off")
                
        if self.has_ambulance:
            self.lbl_time_ns.config(text="SOS", fg="#FF3B30")
            self.lbl_time_ew.config(text="SOS", fg="#FF3B30")
        else:
            if mode == "manual" and not self.is_transitioning:
                self.lbl_time_ns.config(text="--s", fg="black")
                self.lbl_time_ew.config(text="--s", fg="black")
            else:
                red_time = self.countdown + 3 if not self.is_transitioning else self.countdown
                
                if self.is_transitioning:
                    self.lbl_time_ns.config(text=f"{self.countdown}s", fg="black")
                    self.lbl_time_ew.config(text=f"{self.countdown}s", fg="black")
                else:
                    if self.current_action == 0:
                        self.lbl_time_ns.config(text=f"{self.countdown}s", fg="black")
                        self.lbl_time_ew.config(text=f"{red_time}s", fg="black")
                    elif self.current_action == 1:
                        self.lbl_time_ns.config(text=f"{red_time}s", fg="black")
                        self.lbl_time_ew.config(text=f"{self.countdown}s", fg="black")
                    else:
                        self.lbl_time_ns.config(text="--s", fg="black")
                        self.lbl_time_ew.config(text="--s", fg="black")

    # ══════════════════════════════════════════════════════════════
    #  LOGIC UPLOAD & HIỂN THỊ ẢNH
    # ══════════════════════════════════════════════════════════════
    def upload_image(self, slot_index):
        filepath = filedialog.askopenfilename(
            title=f"Chọn ảnh/video cho {INTERSECTIONS[self.current_intersection]['cameras'][slot_index]}",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"), ("All files", "*.*")]
        )
        if not filepath: return

        try:
            img = Image.open(filepath)
            self.image_refs[slot_index] = img
            self.image_paths[slot_index] = filepath
            self._display_image_on_canvas(slot_index)

            self.badge_labels[slot_index].grid()
            self.node_labels[slot_index].place(x=8, y=8)
            self.mode_labels[slot_index].place(x=8, rely=1.0, y=-30)

            self.uploaded_count = sum(1 for ref in self.image_refs if ref is not None)
            self.upload_progress_label.config(text=f"Đã tải lên {self.uploaded_count}/4 hình ảnh")

            if self.uploaded_count == 4:
                self.start_btn.config(state="normal", bg=COLORS["success"], cursor="hand2")
                self.upload_progress_label.config(text="Sẵn sàng phân tích!", fg=COLORS["success"])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở file:\n{e}")

    def _display_image_on_canvas(self, idx):
        canvas = self.camera_canvases[idx]
        img = self.image_refs[idx]
        if img is None: return

        canvas.delete("all")
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if cw < 10 or ch < 10: return

        img_ratio = img.width / img.height
        canvas_ratio = cw / ch

        if img_ratio > canvas_ratio:
            new_h = ch
            new_w = int(ch * img_ratio)
        else:
            new_w = cw
            new_h = int(cw / img_ratio)

        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - cw) // 2
        top = (new_h - ch) // 2
        cropped = resized.crop((left, top, left + cw, top + ch))

        photo = ImageTk.PhotoImage(cropped)
        self.photo_refs[idx] = photo
        canvas.create_image(0, 0, anchor="nw", image=photo)

        if self.node_labels[idx].winfo_ismapped():
            self.node_labels[idx].lift()
            self.mode_labels[idx].lift()

    def reset_dashboard(self, event=None):
        # 1. Lấy thông tin ngã tư mới chọn
        old_topic = self.topic
        self.current_intersection = self.intersection_var.get()
        self.topic = INTERSECTIONS[self.current_intersection]["topic"]

        # 2. Đổi kênh MQTT (Hủy nghe cũ, lắng nghe mới)
        if hasattr(self, 'mqtt_client') and old_topic != self.topic:
            self.mqtt_client.unsubscribe(old_topic)
            self.mqtt_client.subscribe(self.topic)
            print(f"🔄 Đã chuyển kết nối MQTT sang: {self.topic}")

        # 3. Đổi Tiêu đề cửa sổ & Header
        node_name = self.topic.split("/")[-1].upper()
        self.root.title(f"Techno Traffix - Central Command ({node_name})")
        if hasattr(self, 'header_label'):
            self.header_label.config(text=f"Techno Traffix - Central Command | {node_name}")

        # 4. Ngắt luồng AI cũ nếu đang chạy
        if self.is_processing:
            self.stop_thread = True
            self.is_processing = False

        # 5. Reset biến trạng thái đèn về mặc định
        self.current_action = 0
        self.target_action = 0
        self.countdown = 30
        self.is_transitioning = False
        self._set_mode("Auto") # Ép về mode Auto cho an toàn

        # 6. Xóa giao diện Ảnh & Thống kê
        self.image_refs = [None, None, None, None]
        self.photo_refs = [None, None, None, None]
        self.image_paths = [None, None, None, None]
        self.uploaded_count = 0

        for idx in range(4):
            self.camera_canvases[idx].delete("all")
            self.badge_labels[idx].grid_remove()
            self.node_labels[idx].place_forget()
            self.mode_labels[idx].place_forget()
            self._draw_placeholder(idx)
            self.camera_labels[idx].config(text=f"  {INTERSECTIONS[self.current_intersection]['cameras'][idx]}")

        self._toggle_intersection_features()
        self._update_stats(water_level=0, fps=0.0, total_cars=0, emergency=False, accident=False)
        self.stats_intersection_label.config(text=INTERSECTIONS[self.current_intersection]["short"])
        self.start_btn.config(text="\u25B6  BẮT ĐẦU PHÂN TÍCH", bg=COLORS["text_muted"], state="disabled", cursor="arrow")
        self.upload_progress_label.config(text="Tải lên 0/4 hình ảnh để bắt đầu", fg=COLORS["text_muted"])

    # ══════════════════════════════════════════════════════════════
    #  LOGIC NÚT BẤM GỬI MQTT GIAO THÔNG
    # ══════════════════════════════════════════════════════════════
    def _set_traffic_light(self, mode):
        self.btn_stop_all.config(bg=COLORS["danger"])
        self.btn_horizontal.config(bg=COLORS["primary"])
        self.btn_vertical.config(bg=COLORS["success"])
        self._set_mode("Manual")

        if mode == "stop_all":
            self.btn_stop_all.config(bg=COLORS["danger_dark"])
            self.manual_action = 2
        elif mode == "horizontal":
            self.btn_horizontal.config(bg=COLORS["primary_dark"])
            self.manual_action = 1
        elif mode == "vertical":
            self.btn_vertical.config(bg=COLORS["success_dark"])
            self.manual_action = 0

        if not self.is_processing: self._publish_mqtt_immediate()

    def _set_mode(self, mode):
        self.operation_mode.set(mode.lower())
        for name, btn in self.mode_buttons.items():
            if name == mode: btn.config(bg=COLORS["primary"], fg=COLORS["text_light"])
            else: btn.config(bg=COLORS["bg_card_dark"], fg=COLORS["text_dark"])
        for lbl in self.mode_labels:
            lbl.config(text=f"Mode: {mode.upper()}")
            
        if not self.is_processing: self._publish_mqtt_immediate()

    def _publish_mqtt_immediate(self):
        if not hasattr(self, 'mqtt_client'): return
        self._lock_controls()
        payload = {
            "mode": self.operation_mode.get(),
            "action": self.manual_action if self.operation_mode.get() == "manual" else 0,
            "has_ambulance": False,
            "has_accident": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.mqtt_client.publish(self.topic, json.dumps(payload))
   
    # ══════════════════════════════════════════════════════════════..... 
    def _lock_controls(self):
        """Khóa các nút điều khiển trong 2 giây để chống spam MQTT"""
        # Làm mờ và đổi con trỏ chuột thành hình chờ (đồng hồ cát)
        self.btn_stop_all.config(state="disabled", cursor="watch")
        self.btn_horizontal.config(state="disabled", cursor="watch")
        self.btn_vertical.config(state="disabled", cursor="watch")
        for btn in self.mode_buttons.values():
            btn.config(state="disabled", cursor="watch")
            
        # Hẹn giờ đúng 2000ms (2 giây) sau thì gọi hàm mở khóa
        self.root.after(2000, self._unlock_controls)

    def _unlock_controls(self):
        """Mở khóa lại các nút sau khi hết thời gian chờ"""
        # Chỉ mở khóa nếu KHÔNG PHẢI là nút ngã tư Lê Lợi (vì Lê Lợi chỉ đo nước)
        if self.current_intersection != "Ngã tư 3 (Lê Lợi)":
            self.btn_stop_all.config(state="normal", cursor="hand2")
            self.btn_horizontal.config(state="normal", cursor="hand2")
            self.btn_vertical.config(state="normal", cursor="hand2")
            for btn in self.mode_buttons.values():
                btn.config(state="normal", cursor="hand2")
    # ══════════════════════════════════════════════════════════════..... 
    # ══════════════════════════════════════════════════════════════
    #  LUỒNG AI BACKEND (GIỮ NGUYÊN)
    # ══════════════════════════════════════════════════════════════
    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        self.stop_thread = False
        
        self.start_btn.config(text="\u23F3  ĐANG XỬ LÝ...", bg=COLORS["warning"], state="disabled")
        self.upload_progress_label.config(text="Hệ thống AI đang khởi động...", fg=COLORS["warning"])

        self.ai_thread = threading.Thread(target=self._ai_worker_loop, daemon=True)
        self.ai_thread.start()

    def _ai_worker_loop(self):
        try:
            print("Loading models...")
            detector = YOLODetector(model_path=str(_VD_DIR / "vehicle_detection_yolov8l.pt"), device="cuda" if torch.cuda.is_available() else "cpu")
            accident_model = YOLO(_DEFAULT_ACCIDENT_MODEL)
            ambulance_model = YOLO(_DEFAULT_AMBULANCE_MODEL)
            
            agent = DoubleDQNagent()
            agent.policy_net.load_state_dict(torch.load("dqn_weights.pth", map_location="cpu", weights_only=True))
            agent.policy_net.eval()
            connector = TrafficDataConnector()

            self.root.after(0, lambda: self.upload_progress_label.config(text="AI đang theo dõi ngã tư...", fg=COLORS["success"]))
            self.root.after(0, lambda: self.start_btn.config(text="ĐANG THEO DÕI", bg=COLORS["success"]))

            directions = ["north", "south", "east", "west"]

            while not self.stop_thread:
                loop_start = time.time()
                current_mode = self.operation_mode.get()

                intersection_ambulance = False
                intersection_accident = False
                action = 0

                if current_mode == "ai":
                    results = {}
                    total_cars_intersection = 0

                    for i, dir_name in enumerate(directions):
                        if self.image_paths[i] is None: continue
                        frame = cv2.imread(self.image_paths[i])
                        if frame is None: continue

                        detections = detector.detect(frame)
                        veh_counts = {}
                        for det in detections:
                            if det.class_name != "ambulance":
                                veh_counts[det.class_name] = veh_counts.get(det.class_name, 0) + 1
                        
                        amb_res = ambulance_model(frame, conf=0.7, verbose=False)
                        has_amb = len(amb_res[0].boxes) > 0 if amb_res else False
                        if has_amb: veh_counts["ambulance"] = 1
                        
                        acc_res = accident_model(frame, verbose=False)
                        has_acc = (acc_res[0].probs.top1 == 0) if acc_res and acc_res[0].probs else False
                        if has_amb: has_acc = False

                        results[dir_name] = {"vehicle_counts": veh_counts, "has_ambulance": has_amb, "has_accident": has_acc}

                        total_cars_intersection += sum(veh_counts.values())

                    traffic_dict = {"directions": results}
                    state, override_action = connector.process_traffic_data(traffic_dict)
                    
                    intersection_accident = any(d.get("has_accident", False) for d in results.values())
                    intersection_ambulance = any(d.get("has_ambulance", False) for d in results.values())

                    if override_action is not None: action = override_action
                    else: action = int(agent.act(state))
                    
                    connector.update_light_state(action, BLOCK_TIME)

                    fps = round(1.0 / (time.time() - loop_start), 1)
                    
                    self.root.after(0, lambda f=fps, tc=total_cars_intersection, em=intersection_ambulance, acc=intersection_accident: 
                        self._update_stats(
                            fps=f, 
                            total_cars=tc, 
                            emergency=em, 
                            accident=acc
                        )
                    )
                elif current_mode == "manual":
                    action = self.manual_action
                
                payload = {
                    "mode": current_mode,
                    "action": action,
                    "has_ambulance": intersection_ambulance,
                    "has_accident": intersection_accident,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                print(f">>> Hàng đợi BN: {state[0]:.2f}+{state[1]:.2f} | ĐT: {state[2]:.2f}+{state[3]:.2f} ==> AI Chọn: {action}")
                self.mqtt_client.publish(self.topic, json.dumps(payload))

                processing_time = time.time() - loop_start
                sleep_time = max(0.0, BLOCK_TIME - processing_time)
                time.sleep(sleep_time)

        except Exception as e:
            print(f"AI Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Lỗi AI", str(e)))
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.start_btn.config(text="\u25B6  BẮT ĐẦU PHÂN TÍCH", bg=COLORS["text_muted"], state="normal"))

    def _update_stats(self, **kwargs):
        self.stats.update(kwargs)
        self.fps_label.config(text=str(self.stats["fps"]))
        self.total_cars_label.config(text=str(self.stats["total_cars"]))

        if self.stats["emergency"]: self.emergency_badge.config(text="  \U0001F6A8 Cấp cứu: CÓ  ", bg=COLORS["danger"])
        else: self.emergency_badge.config(text="  \U0001F6A8 Cấp cứu: KHÔNG  ", bg=COLORS["success"])

        if self.stats["accident"]: self.accident_badge.config(text="  \u26A0 Tai nạn: CÓ  ", bg=COLORS["danger"])
        else: self.accident_badge.config(text="  \u26A0 Tai nạn: KHÔNG  ", bg=COLORS["text_muted"])

    def on_closing(self):
        self.stop_thread = True 
        if hasattr(self, 'mqtt_client'): self.mqtt_client.loop_stop()
        self.root.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs='*', help="4 đường dẫn ảnh (Tùy chọn)")
    parser.add_argument("--topic", type=str, default="KHKT_DQN/traffic_control")
    args = parser.parse_args()

    root = tk.Tk()
    
    img_paths = args.images if len(args.images) == 4 else None
    app = SmartFixDashboard(root, img_paths, args.topic)
    
    root.mainloop()