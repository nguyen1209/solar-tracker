# 🌞 Solar Tracker System

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green)
![MicroPython](https://img.shields.io/badge/MicroPython-Pico_W-orange)
![License](https://img.shields.io/badge/License-MIT-brightgreen)

**Hệ thống giám sát và điều khiển pin mặt trời thông minh với Raspberry Pi Pico W**

## ✨ Tính năng nổi bật

- ✅ **Theo dõi mặt trời tự động** với 4 cảm biến ánh sáng
- ✅ **Dashboard real-time** hiển thị công suất, điện áp, pin
- ✅ **Điều khiển từ xa** qua web từ mọi nơi
- ✅ **Cảnh báo thông minh** qua Slack/Telegram
- ✅ **Quản lý người dùng** với phân quyền chi tiết
- ✅ **Giám sát thời tiết** tích hợp API

## 🏗️ Kiến trúc hệ thống
┌─────────────┐ WiFi ┌─────────────┐ HTTP ┌─────────────┐
│ PICO W ├───────────►│ Flask ├───────────►│ Web │
│ (Hardware) │ Sensor │ Server │ API │ Dashboard │
└─────────────┘ Data └─────────────┘ └─────────────┘
│ │ │
│ 2x Servo 180° │ Slack Webhook │ User
│ 4x Photoresistor │ Weather API │ Control
│ Battery Monitor │ SQLite DB │
└────────────────────────────┴─────────────────────────┘

text

## 🚀 Bắt đầu nhanh

### Yêu cầu hệ thống
- Python 3.10+
- Raspberry Pi Pico W
- 2x Servo SG90 (180°)
- 4x Photoresistor + ADS1115
- LCD 16x2 I2C

### Cài đặt Backend (Flask Server)

```bash
# 1. Clone repository
git clone https://github.com/nguyensieucapvippro/solar-tracker.git
cd solar-tracker/server

# 2. Cài đặt dependencies
pip install -r requirements.txt

# 3. Chạy server
python solar_server.py

# 4. Truy cập dashboard
# Mở trình duyệt: http://localhost:5000
Cài đặt PICO
Nạp code pico/main.py lên Raspberry Pi Pico W

Kết nối phần cứng theo sơ đồ trong docs/wiring.md

Cấu hình WiFi trong file config.py

Khởi động và kiểm tra kết nối

📊 Dashboard Features
Real-time Monitoring
📈 Biểu đồ công suất theo thời gian

🔋 Mức pin và thời gian sử dụng còn lại

🌡️ Nhiệt độ & độ ẩm từ API thời tiết

☀️ Cường độ ánh sáng từ 4 cảm biến

Control Panel
🎮 Chế độ Auto/Manual điều khiển

📐 Điều chỉnh góc Azimuth & Elevation

💡 Chế độ tiết kiệm năng lượng

⚡ Power management thông minh

Alert System
🔔 Cảnh báo pin yếu (<20%)

⚠️ Mất kết nối PICO

📉 Hiệu suất thấp cảnh báo

🌧️ Thời tiết xấu dự báo

🔧 Cấu trúc project
text
solar-tracker/
├── server/                  # Flask backend
│   ├── solar_server.py      # Main application
│   ├── requirements.txt     # Python dependencies
│   ├── templates/          # HTML templates
│   │   ├── dashboard.html
│   │   ├── login.html
│   │   └── users.html
│   └── static/             # CSS, JS, images
│
├── pico/                   # MicroPython code
│   ├── main.py            # Main PICO code
│   ├── lib/               # External libraries
│   │   ├── ads1x15.py     # ADS1115 driver
│   │   └── i2c_lcd.py     # LCD driver
│   └── config_template.py # Configuration template
│
├── docs/                   # Documentation
│   ├── hardware-setup.md  # Hướng dẫn phần cứng
│   ├── wiring-diagram.png # Sơ đồ đấu nối
│   └── api-reference.md   # API documentation
│
├── README.md              # This file
├── .gitignore            # Git ignore rules
└── LICENSE               # MIT License
🔌 API Endpoints
Authentication
POST /login - Đăng nhập

GET /logout - Đăng xuất

Sensor Data
POST /api/sensor-data - PICO gửi dữ liệu

GET /api/history-chart - Lấy dữ liệu biểu đồ

GET /api/report/daily - Báo cáo hàng ngày

Control
POST /api/control/pico - Gửi lệnh điều khiển

GET /api/get-command - PICO lấy lệnh

Weather
GET /api/weather/current - Thời tiết hiện tại

GET /api/weather/forecast - Dự báo 24h

Alerts
GET /api/alerts/history - Lịch sử cảnh báo

DELETE /api/alerts/clear - Xóa cảnh báo

👥 Default Users
Username	Password	Role	Permissions
admin	admin123	Admin	Full system access
operator	operator123	Operator	Control + View
viewer	viewer123	Viewer	View only
guest	guest123	Guest	Limited view
🛠️ Hardware Setup
Components List
Raspberry Pi Pico W - Main controller

2x SG90 Servo (180°) - Pan/Tilt control

ADS1115 ADC - 4-channel analog read

4x Photoresistor - Light sensing

LCD 16x2 I2C - Status display

Voltage divider - Battery monitoring

Solar panel - 6V/20W

Wiring Diagram
text
PICO W GPIO:
- GPIO 4  → Servo 1 (Azimuth)
- GPIO 5  → Servo 2 (Elevation)
- GPIO 2  → I2C SDA (LCD + ADS1115)
- GPIO 3  → I2C SCL (LCD + ADS1115)
- GPIO 26 → Battery voltage sensing
- GPIO 27 → Panel voltage sensing
🌐 Deployment
Local Development
bash
python solar_server.py
# Access: http://localhost:5000
PythonAnywhere (Free Hosting)
text
https://nguyensieucapvippro.pythonanywhere.com
PICO Configuration
python
# In pico/config.py
SSID = "Your_WiFi"
PASSWORD = "Your_Password"
SERVER_URL = "https://nguyensieucapvippro.pythonanywhere.com"
🐛 Troubleshooting
Common Issues
PICO không kết nối WiFi

Kiểm tra SSID/password

Kiểm tra signal strength

Server không nhận data

Kiểm tra firewall port 5000

Xem log server: python solar_server.py

Servo không hoạt động

Kiểm tra nguồn điện 5V

Kiểm tra wiring GPIO

Dashboard không load

Clear browser cache

Check console errors (F12)

📈 Performance Metrics
Data interval: 3 seconds (normal), 10 seconds (power save)

Database: SQLite with automatic cleanup

Max concurrent users: 50+ (tested)

Response time: < 200ms

Uptime: 99.9% (with proper hosting
