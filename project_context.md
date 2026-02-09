# Project Context: Techno Traffix (Traffic-Platform)

## 1. Tổng quan Dự án
**Techno Traffix** là hệ thống giám sát giao thông thông minh ứng dụng AI tại Việt Nam. 
- **Chức năng chính:** Phát hiện phương tiện, phân loại tai nạn, nhận diện ùn tắc giao thông từ hình ảnh/video và cung cấp chatbot tư vấn luật giao thông (NOVA TRAFFIX).
- **Phạm vi địa lý:** Dữ liệu mẫu tập trung tại Đắk Lắk (Buôn Ma Thuột) và Hà Nội.

## 2. Kiến trúc Hệ thống
Hệ thống được chia làm 3 khối chính:

### A. AI & Computer Vision (`video_detection/` & `training/`)
- **Framework:** YOLOv8 (Ultralytics).
- **Models (.pt):**
  - `vehicle_detection_yolov8l.pt`: Phát hiện các loại xe (xe máy, ô tô, xe tải, xe buýt, xe cứu thương).
  - `accident_classification_yolov8l.pt`: Phân loại trạng thái tai nạn (Binary: Accident/No Accident).
  - `traffic_classification_yolov8l.pt`: Phân loại mật độ giao thông (Jam/No Jam).
- **Tracking:** Sử dụng ByteTrack để theo dõi phương tiện trong video.
- **Workflow:** Có quy trình tự động từ cắt frame -> gán nhãn tự động -> train model.

### B. Backend API (`web-user/backend/`)
- **Framework:** Flask.
- **AI Service:** Tích hợp trực tiếp 3 model YOLOv8 (.pt) để xử lý media upload.
- **Chat Service (Hybrid Brain):** 
  - **RAG System:** Tìm kiếm ưu tiên trong cơ sở dữ liệu luật địa phương (`faq.json`, `gplx.json`, `nd_168_2024.json`).
  - **LLM Fallback:** Sử dụng Anthropic Claude (3-haiku) khi kết quả RAG không đủ độ tin cậy.
  - **Luật áp dụng:** Nghị định 168/2024/NĐ-CP (mới nhất), Nghị định 100/2019.
- **Traffic Service:** Gọi OSRM API để mô phỏng dữ liệu giao thông thực tế trên bản đồ.

### C. Frontend (`web-user/frontend/`)
- **Công nghệ:** Vanilla JS (ES Modules), Leaflet.js (Maps), CSS hiện đại (Blue & White theme).
- **Modules:**
  - `tabs.js`: Quản lý điều hướng tab (Overview, Analysis, Maps, News, Report).
  - `upload.js`: Xử lý kéo thả và gửi file ảnh/video lên server để AI phân tích.
  - `chat.js`: Giao diện chatbot NOVA TRAFFIX với các tính năng Quick Actions.
  - `maps.js`: Hiển thị bản đồ nhiệt giao thông và chỉ số không khí (AQI).

## 3. Cấu hình Quan trọng
- **Model Format:** Dự án đang sử dụng **YOLOv8 PyTorch (.pt)**.
- **Chatbot Thresholds:**
  - `RAG_FAQ_THRESHOLD`: 3.0
  - `RAG_VIOLATION_THRESHOLD`: 4.0
  - `RAG_GPLX_THRESHOLD`: 3.0
- **Địa điểm mặc định:** 12.6976, 108.0674 (42 Phạm Hùng, Tân An, Buôn Ma Thuột).

## 4. Tình trạng Mã nguồn
- Backend và Frontend đang chạy chung trên port 5000 (Flask phục vụ cả static files).
- Hệ thống RAG đã được tối ưu để giảm 60-70% chi phí API LLM bằng cách trả lời trực tiếp từ dữ liệu JSON nếu độ khớp cao.
- Video analysis thực hiện inference theo từng frame và trả về video đã được vẽ bounding boxes.