from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
import threading
import time
import sqlite3
import requests
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
app = Flask(__name__)
app.secret_key = 'solar_tracker_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# ================== SLACK CONFIGURATION ==================
SLACK_WEBHOOK_URL = "your url"  # #social
SLACK_ALERT_WEBHOOK_URL = "your url"  # #cảnh-báo
SLACK_CHANNEL = "#báo-cáo"
SLACK_ALERT_CHANNEL = "#cảnh-báo"
DB_PATH = 'dataa.db'

# ================== USER ROLES CONFIGURATION ==================
USER_ROLES = {
    'admin': {
        'level': 100,
        'permissions': ['view_dashboard', 'view_reports', 'view_alerts', 
                       'control_pico', 'manage_users', 'manage_system',
                       'delete_data', 'send_alerts', 'view_weather',
                       'clear_alerts', 'update_settings',  'send_test_alerts', 'send_test_report']
    },
    'operator': {
        'level': 50,
        'permissions': ['view_dashboard', 'view_reports', 'view_alerts',
                       'control_pico', 'view_weather']
    },
    'viewer': {
        'level': 10,
        'permissions': ['view_dashboard', 'view_reports', 'view_weather']
    },
    'guest': {
        'level': 1,
        'permissions': ['view_dashboard']
    }
}

# ================== WEATHER API CONFIG ==================
WEATHER_CONFIG = {
    'latitude': 10.8231,    # TP.HCM
    'longitude': 106.6297,  # TP.HCM
    'timezone': 'Asia/Ho_Chi_Minh',
    'update_interval': 1800  # 30 phút
}

# ================== ALERT CONFIGURATION ==================
ALERT_CONFIG = {
    'battery_low': 10,           # Cảnh báo khi pin < 20%
    'battery_critical': 5,      # Cảnh báo khẩn cấp khi pin < 10%
    'no_power_threshold': 1.0,   # Cảnh báo khi không có công suất (W)
    'offline_threshold': 300,    # Cảnh báo khi PICO offline 5 phút
    'efficiency_low': 30,        # Cảnh báo hiệu suất thấp (%)
    'check_interval': 60         # Kiểm tra cảnh báo mỗi 60 giây
}

# Biến lưu trạng thái cảnh báo đã gửi
alert_states = {
    'battery_low_sent': False,
    'battery_critical_sent': False,
    'pico_offline_sent': False,
    'no_power_sent': False,
    'low_efficiency_sent': False
}

# ================== DATABASE SETUP ==================
def init_db():
    """Khởi tạo database SQLite"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Bảng sensor data
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  azimuth REAL, elevation REAL, current REAL, 
                  voltage REAL, power REAL, mode TEXT,
                  energy_saving BOOLEAN, efficiency REAL,
                  light_intensity REAL,
                  battery_voltage REAL,
                  battery_soc REAL,
                  remaining_capacity_ah REAL,
                  battery_capacity_ah REAL)
               ''')
    
    # Bảng weather data
    c.execute('''CREATE TABLE IF NOT EXISTS weather_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  temperature REAL,
                  humidity REAL,
                  wind_speed REAL,
                  cloud_cover INTEGER,
                  weather_code INTEGER,
                  sunrise TEXT,
                  sunset TEXT,
                  is_day BOOLEAN,
                  forecast_json TEXT)
               ''')
    
    # Bảng alerts log
    c.execute('''CREATE TABLE IF NOT EXISTS alerts_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  alert_type TEXT,
                  message TEXT,
                  severity TEXT,
                  data_json TEXT,
                  acknowledged_by TEXT,
                  acknowledged_at DATETIME)
               ''')
    
    # Bảng users - UPDATED với thêm trường role
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT DEFAULT 'viewer',
                  email TEXT,
                  full_name TEXT,
                  is_active BOOLEAN DEFAULT 1,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  last_login DATETIME,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tạo các user mặc định
    try:
        # Admin user
        admin_hash = generate_password_hash('admin123')
        c.execute('''INSERT OR IGNORE INTO users 
                    (username, password_hash, role, full_name) 
                    VALUES (?, ?, ?, ?)''',
                 ('admin', admin_hash, 'admin', 'Quản trị viên'))
        
        # Operator user
        operator_hash = generate_password_hash('operator123')
        c.execute('''INSERT OR IGNORE INTO users 
                    (username, password_hash, role, full_name) 
                    VALUES (?, ?, ?, ?)''',
                 ('operator', operator_hash, 'operator', 'Vận hành viên'))
        
        # Viewer user
        viewer_hash = generate_password_hash('viewer123')
        c.execute('''INSERT OR IGNORE INTO users 
                    (username, password_hash, role, full_name) 
                    VALUES (?, ?, ?, ?)''',
                 ('viewer', viewer_hash, 'viewer', 'Người xem'))
        
        # Guest user
        guest_hash = generate_password_hash('guest123')
        c.execute('''INSERT OR IGNORE INTO users 
                    (username, password_hash, role, full_name) 
                    VALUES (?, ?, ?, ?)''',
                 ('guest', guest_hash, 'guest', 'Khách'))
        
    except Exception as e:
        print(f"❌ Error creating default users: {e}")
    
    # Bảng user_activity_log
    c.execute('''CREATE TABLE IF NOT EXISTS user_activity_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  activity_type TEXT,
                  description TEXT,
                  ip_address TEXT,
                  user_agent TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with role-based user management")

# ================== PERMISSION DECORATORS ==================
def permission_required(permission):
    """Decorator kiểm tra quyền truy cập"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user_role = session.get('role', 'guest')
            user_permissions = USER_ROLES.get(user_role, USER_ROLES['guest'])['permissions']
            
            if permission not in user_permissions:
                # Log unauthorized access attempt
                log_user_activity(
                    session.get('user_id'),
                    session.get('username'),
                    'unauthorized_access',
                    f'Tried to access {request.path} without {permission} permission',
                    request.remote_addr,
                    request.user_agent.string
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'status': 'error',
                        'message': 'Không có quyền truy cập!'
                    }), 403
                else:
                    return render_template('error.html', 
                                         error_code=403,
                                         error_message='Không có quyền truy cập!'), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(min_role_level):
    """Decorator kiểm tra role level"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user_role = session.get('role', 'guest')
            user_level = USER_ROLES.get(user_role, USER_ROLES['guest'])['level']
            
            if user_level < min_role_level:
                # Log unauthorized access attempt
                log_user_activity(
                    session.get('user_id'),
                    session.get('username'),
                    'insufficient_role',
                    f'Tried to access {request.path} with role {user_role} (level {user_level}), required level {min_role_level}',
                    request.remote_addr,
                    request.user_agent.string
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'status': 'error',
                        'message': 'Không có quyền truy cập! Vai trò không đủ!'
                    }), 403
                else:
                    return render_template('error.html',
                                         error_code=403,
                                         error_message='Không có quyền truy cập! Vai trò không đủ!'), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ================== LOGGING FUNCTIONS ==================
def log_user_activity(user_id, username, activity_type, description, ip_address, user_agent):
    """Ghi log hoạt động của người dùng"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT INTO user_activity_log 
                    (user_id, username, activity_type, description, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (user_id, username, activity_type, description, ip_address, user_agent))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error logging user activity: {e}")
        return False

# ================== SLACK INTEGRATION ==================
def send_slack_message(webhook_url, channel, message, attachments=None, is_alert=False):
    """Gửi message đến Slack"""
    try:
        username = "🚨 Solar Tracker Alert Bot" if is_alert else "🌞 Solar Tracker Bot"
        icon_emoji = ":warning:" if is_alert else ":sunny:"
        
        payload = {
            "channel": channel,
            "username": username,
            "icon_emoji": icon_emoji,
            "text": message
        }
        
        if attachments:
            payload["attachments"] = attachments
            
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return False

def send_daily_slack_report():
    """Gửi báo cáo hàng ngày qua Slack"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''SELECT 
                 MAX(power) as max_power,
                 AVG(power) as avg_power,
                 SUM(power * 3 / 3600) as total_energy,
                 AVG(efficiency) as avg_efficiency,
                 AVG(battery_soc) as avg_battery_soc,
                 COUNT(*) as data_points
                 FROM sensor_data 
                 WHERE date(timestamp) = ?''', (today,))
    
    result = c.fetchone()
    conn.close()
    
    if result and result[5] > 0:
        max_power, avg_power, total_energy, avg_efficiency, avg_battery_soc, data_points = result
        
        message = f"📊 *BÁO CÁO HÀNG NGÀY - {datetime.now().strftime('%d/%m/%Y')}*"
        
        attachments = [{
            "color": "#36a64f",
            "fields": [
                {"title": "Công suất trung bình", "value": f"{avg_power:.1f} W", "short": True},
                {"title": "Tổng năng lượng", "value": f"{total_energy:.2f} Wh", "short": True},
                {"title": "Hiệu suất trung bình", "value": f"{avg_efficiency:.1f}%", "short": True},
                {"title": "Pin trung bình", "value": f"{avg_battery_soc:.1f}%", "short": True},
                {"title": "Số lượng data points", "value": f"{data_points}", "short": True}
            ],
            "footer": "Solar Tracker System",
            "ts": int(time.time())
        }]
        
        success = send_slack_message(SLACK_WEBHOOK_URL, SLACK_CHANNEL, message, attachments)
        if success:
            print("✅ Đã gửi báo cáo Slack")
            return True
        else:
            print("❌ Gửi báo cáo Slack thất bại")
            return False
    return False

def send_alert_slack(message, alert_type, data=None, severity="warning"):
    """Gửi cảnh báo qua Slack"""
    try:
        # Màu sắc dựa trên mức độ nghiêm trọng
        colors = {
            "info": "#3498db",
            "warning": "#f39c12",
            "critical": "#e74c3c",
            "success": "#2ecc71"
        }
        color = colors.get(severity, "#f39c12")
        
        attachments = [{
            "color": color,
            "title": f"🚨 CẢNH BÁO: {alert_type}",
            "text": message,
            "fields": [],
            "footer": f"Solar Tracker Alert • {datetime.now().strftime('%H:%M:%S')}",
            "ts": int(time.time())
        }]
        
        if data:
            for key, value in data.items():
                attachments[0]["fields"].append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        success = send_slack_message(
            SLACK_ALERT_WEBHOOK_URL, 
            SLACK_ALERT_CHANNEL, 
            message, 
            attachments, 
            is_alert=True
        )
        
        if success:
            # Lưu log cảnh báo vào database
            save_alert_log(alert_type, message, severity, data)
            print(f"✅ Đã gửi cảnh báo: {alert_type}")
        else:
            print(f"❌ Gửi cảnh báo thất bại: {alert_type}")
            
        return success
    except Exception as e:
        print(f"❌ Alert error: {e}")
        return False

def save_alert_log(alert_type, message, severity, data=None):
    """Lưu log cảnh báo vào database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        data_json = json.dumps(data) if data else None
        
        c.execute('''INSERT INTO alerts_log 
                    (alert_type, message, severity, data_json)
                    VALUES (?, ?, ?, ?)''',
                 (alert_type, message, severity, data_json))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Save alert log error: {e}")
        return False

# ================== WEATHER FUNCTIONS ==================

def get_weather_data_openmeteo():
    """Lấy dữ liệu thời tiết từ Open-Meteo (MIỄN PHÍ)"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        
        params = {
            'latitude': WEATHER_CONFIG['latitude'],
            'longitude': WEATHER_CONFIG['longitude'],
            'timezone': WEATHER_CONFIG['timezone'],
            'current_weather': 'true',
            'hourly': 'temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m',
            'daily': 'sunrise,sunset',
            'forecast_days': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            current = data.get('current_weather', {})
            hourly = data.get('hourly', {})
            daily = data.get('daily', {})
            
            # Tìm index của giờ hiện tại
            current_hour_index = None
            if 'time' in hourly:
                current_hour = datetime.now().strftime('%H')
                for i, time_str in enumerate(hourly['time']):
                    if time_str.startswith(datetime.now().strftime('%Y-%m-%dT')):
                        time_hour = time_str[11:13]
                        if time_hour == current_hour:
                            current_hour_index = i
                            break
            
            # Chuẩn bị weather data
            weather_data = {
                'temperature': current.get('temperature', 0),
                'wind_speed': current.get('windspeed', 0),
                'wind_direction': current.get('winddirection', 0),
                'weather_code': current.get('weathercode', 0),
                'is_day': current.get('is_day', 1) == 1,
                'time': current.get('time', ''),
                'humidity': hourly.get('relative_humidity_2m', [0])[current_hour_index] if current_hour_index is not None else 0,
                'cloud_cover': hourly.get('cloud_cover', [0])[current_hour_index] if current_hour_index is not None else 0,
                'sunrise': daily.get('sunrise', [''])[0] if daily.get('sunrise') else '',
                'sunset': daily.get('sunset', [''])[0] if daily.get('sunset') else '',
                'hourly_forecast': {
                    'times': hourly.get('time', [])[:24],
                    'temperatures': hourly.get('temperature_2m', [])[:24],
                    'humidities': hourly.get('relative_humidity_2m', [])[:24],
                    'clouds': hourly.get('cloud_cover', [])[:24],
                    'winds': hourly.get('wind_speed_10m', [])[:24]
                }
            }
            
            # Lưu vào database
            save_weather_data(weather_data)
            
            print(f"🌤️  Weather updated: {weather_data['temperature']}°C, {weather_data['humidity']}%")
            return weather_data
            
    except Exception as e:
        print(f"❌ Weather API error: {e}")
    
    # Fallback data
    return {
        'temperature': 28.5,
        'humidity': 75,
        'wind_speed': 2.5,
        'cloud_cover': 40,
        'weather_code': 3,
        'is_day': True,
        'sunrise': '05:45',
        'sunset': '18:15'
    }

def save_weather_data(weather_data):
    """Lưu dữ liệu thời tiết vào database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT INTO weather_data 
                    (temperature, humidity, wind_speed, cloud_cover, 
                     weather_code, sunrise, sunset, is_day, forecast_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (weather_data['temperature'],
                  weather_data['humidity'],
                  weather_data['wind_speed'],
                  weather_data['cloud_cover'],
                  weather_data['weather_code'],
                  weather_data['sunrise'],
                  weather_data['sunset'],
                  weather_data['is_day'],
                  json.dumps(weather_data.get('hourly_forecast', {}))))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Save weather error: {e}")
        return False

def get_weather_code_description(code):
    """Chuyển mã thời tiết thành mô tả"""
    weather_codes = {
        0: "Trời quang", 1: "Chủ yếu quang", 2: "Mây rải rác", 3: "Nhiều mây",
        45: "Sương mù", 48: "Sương mù",
        51: "Mưa phùn nhẹ", 53: "Mưa phùn vừa", 55: "Mưa phùn dày",
        61: "Mưa nhẹ", 63: "Mưa vừa", 65: "Mưa to",
        71: "Tuyết nhẹ", 73: "Tuyết vừa", 75: "Tuyết dày",
        80: "Mưa rào nhẹ", 81: "Mưa rào vừa", 82: "Mưa rào to",
        95: "Giông bão", 96: "Giông bão mưa đá", 99: "Giông bão nặng"
    }
    return weather_codes.get(code, "Không xác định")

def get_weather_icon(code, is_day):
    """Lấy icon thời tiết"""
    if code in [0, 1]:
        return "☀️" if is_day else "🌙"
    elif code in [2]:
        return "🌤️"
    elif code in [3]:
        return "☁️"
    elif code in [45, 48]:
        return "🌫️"
    elif code in [51, 53, 55, 61, 63, 65]:
        return "🌧️"
    elif code in [80, 81, 82]:
        return "⛈️"
    elif code in [95, 96, 99]:
        return "⛈️"
    else:
        return "🌈"

# ================== ALERT FUNCTIONS ==================
def check_alerts():
    """Kiểm tra và gửi cảnh báo"""
    try:
        # Lấy dữ liệu mới nhất
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT battery_soc, power, efficiency, timestamp
                     FROM sensor_data 
                     ORDER BY timestamp DESC LIMIT 1''')
        row = c.fetchone()
        conn.close()
        
        if not row:
            return
        
        battery_soc, power, efficiency, timestamp = row
        
        # Kiểm tra thời gian dữ liệu
        data_time_utc = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        
        # Chuyển UTC sang timezone Việt Nam
        # Vietnam timezone = UTC + 7
        data_time_vn = data_time_utc + timedelta(hours=7, minutes=22)
        current_time_vn = datetime.now()  # Server time (nên là VN time)
        
        # Tính thời gian offline với timezone VN
        time_diff = (current_time_vn - data_time_vn).total_seconds()
        
        # 1. Cảnh báo pin yếu
        if battery_soc < ALERT_CONFIG['battery_critical']:
            if not alert_states['battery_critical_sent']:
                message = f"⚠️ PIN YẾU KHẨN CẤP: {battery_soc:.1f}%"
                send_alert_slack(
                    message, 
                    "PIN YẾU KHẨN CẤP",
                    {"Mức pin": f"{battery_soc:.1f}%", "Trạng thái": "KHẨN CẤP"},
                    "critical"
                )
                alert_states['battery_critical_sent'] = True
                alert_states['battery_low_sent'] = True  # Đánh dấu cảnh báo thấp đã gửi
        elif battery_soc < ALERT_CONFIG['battery_low']:
            if not alert_states['battery_low_sent']:
                message = f"🔋 PIN YẾU: {battery_soc:.1f}%"
                send_alert_slack(
                    message, 
                    "PIN YẾU",
                    {"Mức pin": f"{battery_soc:.1f}%", "Ngưỡng": f"{ALERT_CONFIG['battery_low']}%"},
                    "warning"
                )
                alert_states['battery_low_sent'] = True
        else:
            # Reset trạng thái nếu pin đã sạc lại
            if battery_soc > ALERT_CONFIG['battery_low'] + 5:
                alert_states['battery_low_sent'] = False
            if battery_soc > ALERT_CONFIG['battery_critical'] + 5:
                alert_states['battery_critical_sent'] = False
        
        # 2. Cảnh báo không có công suất
        if power < ALERT_CONFIG['no_power_threshold']:
            if not alert_states['no_power_sent']:
                message = f"⚡ KHÔNG CÓ CÔNG SUẤT: {power:.1f}W"
                send_alert_slack(
                    message, 
                    "KHÔNG CÓ CÔNG SUẤT",
                    {"Công suất": f"{power:.1f}W", "Ngưỡng": f"{ALERT_CONFIG['no_power_threshold']}W"},
                    "warning"
                )
                alert_states['no_power_sent'] = True
        else:
            alert_states['no_power_sent'] = False
        
        # 3. Cảnh báo hiệu suất thấp
        if efficiency < ALERT_CONFIG['efficiency_low'] and power > 5:  # Chỉ cảnh báo khi có công suất
            if not alert_states['low_efficiency_sent']:
                message = f"📉 HIỆU SUẤT THẤP: {efficiency:.1f}%"
                send_alert_slack(
                    message, 
                    "HIỆU SUẤT THẤP",
                    {"Hiệu suất": f"{efficiency:.1f}%", "Công suất": f"{power:.1f}W", "Ngưỡng": f"{ALERT_CONFIG['efficiency_low']}%"},
                    "warning"
                )
                alert_states['low_efficiency_sent'] = True
        else:
            alert_states['low_efficiency_sent'] = False
        
        # 4. Cảnh báo PICO offline
        if time_diff > ALERT_CONFIG['offline_threshold']:
            if not alert_states['pico_offline_sent']:
                # SỬA: Format thời gian cho dễ đọc
                offline_minutes = int(time_diff / 60)
                last_data_time = data_time_vn.strftime('%H:%M:%S %d/%m/%Y')
                
                message = f"🔌 PICO OFFLINE: {offline_minutes} phút"
                send_alert_slack(
                    message, 
                    "PICO OFFLINE",
                    {
                        "Thời gian offline": f"{offline_minutes} phút", 
                        "Dữ liệu cuối": last_data_time,
                        "Giờ VN": f"{data_time_vn.hour:02d}:{data_time_vn.minute:02d}:{data_time_vn.second:02d}"
                    },
                    "critical"
                )
                alert_states['pico_offline_sent'] = True
        else:
            alert_states['pico_offline_sent'] = False
            
    except Exception as e:
        print(f"❌ Check alerts error: {e}")

# ================== AUTHENTICATION ==================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Kiểm tra xem tài khoản còn active không
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT is_active FROM users WHERE id = ?', (session.get('user_id'),))
            result = c.fetchone()
            conn.close()
            
            if result and (result[0] is None or result[0] == 0 or result[0] is False):
                # Tài khoản đã bị vô hiệu hóa
                session.clear()
                return redirect(url_for('login'))
        except:
            pass
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        print(f"=== LOGIN ATTEMPT ===")
        print(f"Username: {username}")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT id, username, password_hash, role, full_name, is_active 
                     FROM users WHERE username = ?''', (username,))
        user = c.fetchone()
        conn.close()
        
        if user:
            print(f"✅ User found in DB: {user[1]}")
            print(f"User ID: {user[0]}")
            print(f"is_active raw value: {user[5]}")
            print(f"Type of is_active: {type(user[5])}")
            
            # DEBUG CHI TIẾT
            print("\n--- DEBUG is_active checks ---")
            print(f"user[5] == 0: {user[5] == 0}")
            print(f"user[5] == False: {user[5] == False}")
            print(f"user[5] is None: {user[5] is None}")
            print(f"not bool(user[5]): {not bool(user[5])}")
            print(f"user[5] in [0, False, None]: {user[5] in [0, False, None]}")
            
            # Kiểm tra mật khẩu
            if not check_password_hash(user[2], password):
                print("❌ Password incorrect")
                return render_template('login.html', error='Tên đăng nhập hoặc mật khẩu không đúng!')
            
            print("✅ Password correct")
            
            # Kiểm tra is_active
        
            # Cập nhật last_login
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user[0],))
            conn.commit()
            conn.close()
            
            # Set session
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            session['full_name'] = user[4]
            
            # Log login activity
            log_user_activity(
                user[0], user[1], 'login', 
                f'User logged in with role {user[3]}',
                request.remote_addr,
                request.user_agent.string
            )
            
            return redirect(url_for('dashboard'))
        else:
            print(f"❌ User not found in DB: {username}")
            return render_template('login.html', error='Tên đăng nhập hoặc mật khẩu không đúng!')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Chỉ admin mới có thể tạo user mới từ register page
    # Hoặc có thể mở cho tất cả nhưng với role mặc định là 'viewer'
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form.get('full_name', '')
        
        if password != confirm_password:
            return render_template('register.html', error='Mật khẩu xác nhận không khớp!')
        
        if len(password) < 6:
            return render_template('register.html', error='Mật khẩu phải có ít nhất 6 ký tự!')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        try:
            password_hash = generate_password_hash(password)
            # Mặc định role là 'viewer' khi đăng ký qua trang này
            role = 'viewer'
            c.execute('''INSERT INTO users (username, password_hash, role, full_name) 
                         VALUES (?, ?, ?, ?)''',
                     (username, password_hash, role, full_name))
            conn.commit()
            conn.close()
            
            # Gửi thông báo cho admin
            if session.get('role') == 'admin':
                admin_msg = f"👤 User mới đã được tạo: {username} ({full_name}) - Role: {role}"
                send_slack_message(SLACK_WEBHOOK_URL, SLACK_CHANNEL, admin_msg)
            
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Tên đăng nhập đã tồn tại!')
        except Exception as e:
            conn.close()
            return render_template('register.html', error=f'Lỗi: {str(e)}')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Log logout activity
    if 'user_id' in session:
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'logout',
            'User logged out',
            request.remote_addr,
            request.user_agent.string
        )
    
    session.clear()
    return redirect(url_for('login'))

# ================== USER MANAGEMENT ROUTES ==================
@app.route('/users')
@login_required
@role_required(100)  # Chỉ admin
def user_management():
    """Quản lý người dùng"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT id, username, role, full_name, email, 
                        is_active, created_at, last_login 
                 FROM users ORDER BY created_at DESC''')
    
    users = []
    for row in c.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'role': row[2],
            'full_name': row[3],
            'email': row[4],
            'is_active': bool(row[5]),
            'created_at': row[6],
            'last_login': row[7]
        })
    
    conn.close()
    
    # Log access
    log_user_activity(
        session.get('user_id'),
        session.get('username'),
        'access_user_management',
        'Accessed user management page',
        request.remote_addr,
        request.user_agent.string
    )
    
    return render_template('users.html', 
                         users=users,
                         user_roles=list(USER_ROLES.keys()),
                         current_user=session)

# ================== USER MANAGEMENT API ROUTES ==================
@app.route('/api/users')
@login_required
@role_required(100)  # Chỉ admin
def get_users():
    """API lấy danh sách users"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT id, username, role, full_name, email, 
                        is_active, created_at, last_login 
                 FROM users ORDER BY created_at DESC''')
    
    users = []
    for row in c.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'role': row[2],
            'full_name': row[3],
            'email': row[4],
            'is_active': bool(row[5]),
            'created_at': row[6],
            'last_login': row[7]
        })
    
    conn.close()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
@login_required
@role_required(100)  # Chỉ admin
def create_user():
    """API tạo user mới"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'viewer')
        full_name = data.get('full_name', '')
        email = data.get('email', '')
        
        if not username or not password:
            return jsonify({'status': 'error', 'message': 'Thiếu username hoặc password!'}), 400
        
        if role not in USER_ROLES:
            return jsonify({'status': 'error', 'message': 'Role không hợp lệ!'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        password_hash = generate_password_hash(password)
        c.execute('''INSERT INTO users 
                    (username, password_hash, role, full_name, email)
                    VALUES (?, ?, ?, ?, ?)''',
                 (username, password_hash, role, full_name, email))
        
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        
        # Log activity
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'create_user',
            f'Created user: {username} with role {role}',
            request.remote_addr,
            request.user_agent.string
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Đã tạo user {username} thành công!',
            'user_id': user_id
        })
        
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Username đã tồn tại!'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi: {str(e)}'}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@role_required(100)  # Chỉ admin
def update_user(user_id):
    """API cập nhật user"""
    try:
        data = request.json
        
        # Không cho phép tự sửa role của chính mình xuống thấp hơn
        if user_id == session.get('user_id'):
            current_role = session.get('role')
            new_role = data.get('role')
            if new_role and USER_ROLES.get(new_role, {}).get('level', 0) < USER_ROLES[current_role]['level']:
                return jsonify({'status': 'error', 'message': 'Không thể tự hạ cấp role của chính mình!'}), 403
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Build update query
        update_fields = []
        update_values = []
        
        if 'username' in data:
            update_fields.append('username = ?')
            update_values.append(data['username'])
        
        if 'role' in data:
            if data['role'] not in USER_ROLES:
                return jsonify({'status': 'error', 'message': 'Role không hợp lệ!'}), 400
            update_fields.append('role = ?')
            update_values.append(data['role'])
        
        if 'full_name' in data:
            update_fields.append('full_name = ?')
            update_values.append(data['full_name'])
        
        if 'email' in data:
            update_fields.append('email = ?')
            update_values.append(data['email'])
         
        if 'is_active' in data:
            update_fields.append('is_active = ?')
            update_values.append(1 if data['is_active'] else 0)
        
        if 'password' in data and data['password']:
            update_fields.append('password_hash = ?')
            update_values.append(generate_password_hash(data['password']))
        
        if update_fields:
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(user_id)
            
            query = f'UPDATE users SET {", ".join(update_fields)} WHERE id = ?'
            c.execute(query, update_values)
            
            conn.commit()
        
        # Get updated user info
        c.execute('SELECT username, role FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        
        # Log activity
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'update_user',
            f'Updated user ID {user_id} ({user[0]})',
            request.remote_addr,
            request.user_agent.string
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Đã cập nhật user {user[0]} thành công!'
        })
        
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Username đã tồn tại!'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi: {str(e)}'}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@role_required(100)  # Chỉ admin
def delete_user(user_id):
    """API xóa user"""
    try:
        # Không cho phép xóa chính mình
        if user_id == session.get('user_id'):
            return jsonify({'status': 'error', 'message': 'Không thể xóa tài khoản của chính mình!'}), 403
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get user info for logging
        c.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'status': 'error', 'message': 'User không tồn tại!'}), 404
        
        # Xóa user
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        # Log activity
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'delete_user',
            f'Deleted user ID {user_id} ({user[0]})',
            request.remote_addr,
            request.user_agent.string
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Đã xóa user {user[0]} thành công!'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi: {str(e)}'}), 500

@app.route('/api/users/activity')
@login_required
@role_required(100)  # Chỉ admin
def get_user_activity():
    """API lấy log hoạt động người dùng"""
    limit = request.args.get('limit', 100, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT 
                 datetime(timestamp, 'localtime') as local_time,
                 username, activity_type, description, ip_address
                 FROM user_activity_log 
                 ORDER BY timestamp DESC LIMIT ?''', (limit,))
    
    activities = []
    for row in c.fetchall():
        activities.append({
            'timestamp': row[0],
            'username': row[1],
            'activity_type': row[2],
            'description': row[3],
            'ip_address': row[4]
        })
    
    conn.close()
    
    return jsonify(activities)


# ================== SYSTEM STATE ==================
system_state = {
    'sensors': {
        'azimuth': 90.0, 'elevation': 90.0, 'current': 0.0, 'voltage': 0.0, 
        'power': 0.0, 'mode': 'AUTO', 'energy_saving': False, 'efficiency': 0.0, 
        'light_intensity': 0.0, 'timestamp': time.time(),
        'battery_voltage': 0.0, 'battery_soc': 0, 'remaining_capacity_ah': 0.0,
        'battery_capacity_ah': 3.0
    },
    'pico_online': False,
    'last_pico_update': None
}

command_queue = []

# ================== DATABASE FUNCTIONS ==================
def save_sensor_data(data):
    """Lưu sensor data vào database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''INSERT INTO sensor_data 
                    (azimuth, elevation, current, voltage, power, mode, energy_saving, 
                     efficiency, light_intensity, battery_voltage, battery_soc, 
                     remaining_capacity_ah, battery_capacity_ah)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (data['azimuth'], data['elevation'], data['current'], data['voltage'],
                  data['power'], data['mode'], data['energy_saving'], 
                  data.get('efficiency', 0), data.get('light_intensity', 0),
                  data.get('battery_voltage', 0), data.get('battery_soc', 0),
                  data.get('remaining_capacity_ah', 0), data.get('battery_capacity_ah', 3.0)))
        
        conn.commit()
        conn.close()
        print(f"💾 Saved data: {data['power']:.1f}W, Bat:{data.get('battery_soc', 0)}%")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

# ================== ROUTES ==================
@app.route('/')
@login_required
@permission_required('view_dashboard')
def dashboard():
    # Lấy thông tin thời tiết
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT temperature, weather_code, is_day FROM weather_data 
                     ORDER BY timestamp DESC LIMIT 1''')
        row = c.fetchone()
        conn.close()
        
        if row:
            weather_info = {
                'temperature': row[0],
                'weather_desc': get_weather_code_description(row[1]),
                'weather_icon': get_weather_icon(row[1], row[2] == 1)
            }
        else:
            weather_info = {
                'temperature': 28,
                'weather_desc': 'Trời quang',
                'weather_icon': '☀️'
            }
    except:
        weather_info = {
            'temperature': 28,
            'weather_desc': 'Trời quang',
            'weather_icon': '☀️'
        }
    
    # Get user permissions for frontend
    user_role = session.get('role', 'guest')
    user_permissions = USER_ROLES.get(user_role, USER_ROLES['guest'])['permissions']
    
    return render_template('dashboard.html', 
                         username=session.get('username'),
                         full_name=session.get('full_name', ''),
                         role=session.get('role', 'guest'),
                         permissions=user_permissions,
                         weather=weather_info)

# ================== API ROUTES ==================
@app.route('/api/sensor-data', methods=['POST'])
def receive_sensor_data():
    """PICO gửi sensor data lên đây"""
    try:
        data = request.json
        system_state['sensors'].update(data)
        system_state['sensors']['timestamp'] = time.time()
        system_state['pico_online'] = True
        system_state['last_pico_update'] = datetime.now().strftime("%H:%M:%S")
        
        save_sensor_data(data)
        
        socketio.emit('sensor_update', system_state['sensors'])
        socketio.emit('status_update', {
            'pico_online': True,
            'last_update': system_state['last_pico_update']
        })
        
        print(f"📊 PICO data: AZ={data.get('azimuth', 0)}°, EL={data.get('elevation', 0)}°, P={data.get('power', 0)}W, Bat={data.get('battery_soc', 0)}%")
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(f"❌ Error receiving data: {e}")
        return jsonify({"status": "error"})

@app.route('/api/get-command', methods=['GET'])
def get_command():
    """PICO lấy lệnh từ web"""
    if command_queue:
        command = command_queue.pop(0)
        print(f"📨 Sending command to PICO: {command}")
        return jsonify(command)
    return jsonify({"command": None})

@app.route('/api/history-chart')
@login_required
@permission_required('view_reports')
def get_history_chart():
    """Lấy dữ liệu cho biểu đồ time series"""
    hours = request.args.get('hours', 24, type=int)
    
    # Xác định số điểm dữ liệu
    if hours == 1: target_points = 8
    elif hours == 6: target_points = 10
    elif hours == 24: target_points = 12
    elif hours == 168: target_points = 14
    else: target_points = 12
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(f'''SELECT 
                 datetime(timestamp, 'localtime') as local_time,
                 current, voltage, power, efficiency, battery_voltage, battery_soc
                 FROM sensor_data 
                 WHERE timestamp > datetime('now', '-{hours} hours')
                 ORDER BY timestamp ASC''')
    
    all_rows = c.fetchall()
    conn.close()
    
    # Lọc dữ liệu
    filtered_rows = []
    total_points = len(all_rows)
    
    if total_points > target_points:
        step = max(1, total_points // target_points)
        for i in range(0, total_points, step):
            if len(filtered_rows) < target_points:
                filtered_rows.append(all_rows[i])
        if total_points > 0 and len(filtered_rows) > 0:
            filtered_rows[0] = all_rows[0]
            filtered_rows[-1] = all_rows[-1]
    else:
        filtered_rows = all_rows
    
    # Chuẩn bị dữ liệu
    labels = []
    power_data = []
    voltage_data = []
    current_data = []
    efficiency_data = []
    battery_voltage_data = []
    battery_soc_data = []
    
    for row in filtered_rows:
        timestamp_str = row[0]
        time_parts = timestamp_str.split(' ')
        time_only = time_parts[1][:5] if len(time_parts) > 1 else timestamp_str[11:16]
            
        labels.append(time_only)
        power_data.append(float(row[3]) if row[3] is not None else 0)
        voltage_data.append(float(row[2]) if row[2] is not None else 0)
        current_data.append(float(row[1]) if row[1] is not None else 0)
        efficiency_data.append(float(row[4]) if row[4] is not None else 0)
        battery_voltage_data.append(float(row[5]) if row[5] is not None else 0)
        battery_soc_data.append(float(row[6]) if row[6] is not None else 0)
    
    return jsonify({
        'labels': labels,
        'power': power_data,
        'voltage': voltage_data,
        'current': current_data,
        'efficiency': efficiency_data,
        'battery_voltage': battery_voltage_data,
        'battery_soc': battery_soc_data 
    })

@app.route('/api/daily-chart')
@login_required
@permission_required('view_reports')
def get_daily_chart():
    """Lấy dữ liệu cho biểu đồ theo ngày"""
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT 
                 datetime(timestamp, 'localtime') as local_time,
                 current, voltage, power, efficiency, battery_voltage, battery_soc
                 FROM sensor_data 
                 WHERE date(timestamp) = ?
                 ORDER BY timestamp ASC''', (date_str,))
    
    all_rows = c.fetchall()
    conn.close()
    
    # Lọc dữ liệu
    filtered_rows = []
    if len(all_rows) > 24:
        step = max(1, len(all_rows) // 24)
        for i in range(0, len(all_rows), step):
            if len(filtered_rows) < 24:
                filtered_rows.append(all_rows[i])
        if len(all_rows) > 0:
            filtered_rows[0] = all_rows[0]
            filtered_rows[-1] = all_rows[-1]
    else:
        filtered_rows = all_rows
    
    # Chuẩn bị dữ liệu
    labels = []
    power_data = []
    voltage_data = []
    current_data = []
    efficiency_data = []
    battery_voltage_data = []
    battery_soc_data = []
    
    for row in filtered_rows:
        timestamp_str = row[0]
        time_parts = timestamp_str.split(' ')
        time_only = time_parts[1][:5] if len(time_parts) > 1 else timestamp_str[11:16]
            
        labels.append(time_only)
        power_data.append(float(row[3]) if row[3] is not None else 0)
        voltage_data.append(float(row[2]) if row[2] is not None else 0)
        current_data.append(float(row[1]) if row[1] is not None else 0)
        efficiency_data.append(float(row[4]) if row[4] is not None else 0)
        battery_voltage_data.append(float(row[5]) if row[5] is not None else 0)
        battery_soc_data.append(float(row[6]) if row[6] is not None else 0)
    
    return jsonify({
        'labels': labels,
        'power': power_data,
        'voltage': voltage_data,
        'current': current_data,
        'efficiency': efficiency_data,
        'battery_voltage': battery_voltage_data,
        'battery_soc': battery_soc_data,
        'date': date_str
    })

@app.route('/api/available-dates')
@login_required
@permission_required('view_reports')
def get_available_dates():
    """Lấy danh sách các ngày có dữ liệu"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT DISTINCT date(timestamp) as date 
                 FROM sensor_data 
                 ORDER BY date DESC''')
    
    dates = [row[0] for row in c.fetchall()]
    conn.close()
    
    return jsonify(dates)

@app.route('/api/report/daily')
@login_required
@permission_required('view_reports')
def daily_report():
    """Báo cáo hiệu suất ngày"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''SELECT 
                 MAX(power) as max_power,
                 AVG(power) as avg_power,
                 SUM(power * 3 / 3600) as total_energy,
                 AVG(efficiency) as avg_efficiency,
                 AVG(battery_soc) as avg_battery_soc,
                 COUNT(*) as data_points
                 FROM sensor_data 
                 WHERE date(timestamp) = ?''', (today,))
    
    result = c.fetchone()
    conn.close()
    
    if result and result[0] is not None:
        report = {
            'max_power': result[0], 'avg_power': result[1], 'total_energy': result[2],
            'avg_efficiency': result[3], 'avg_battery_soc': result[4], 'data_points': result[5], 'date': today
        }
    else:
        report = {
            'max_power': 0, 'avg_power': 0, 'total_energy': 0,
            'avg_efficiency': 0, 'avg_battery_soc': 0, 'data_points': 0, 'date': today
        }
    
    return jsonify(report)

# ================== SLACK API ROUTES ==================
@app.route('/api/test-slack-report')
@login_required
@permission_required('send_test_report')
def test_slack_report():
    """Test gửi báo cáo Slack"""
    success = send_daily_slack_report()
    
    # Log activity
    log_user_activity(
        session.get('user_id'),
        session.get('username'),
        'test_slack_report',
        'Tested Slack report functionality',
        request.remote_addr,
        request.user_agent.string
    )
    
    return jsonify({"status": "success" if success else "error"})

@app.route('/api/test-slack-alert')
@login_required
@permission_required('send_test_alerts')
def test_slack_alert():
    """Test gửi cảnh báo Slack"""
    test_data = {
        "Battery": "25%",
        "Power": "15.5W",
        "Voltage": "12.3V",
        "Status": "TEST MODE",
        "User": session.get('username')
    }
    success = send_alert_slack(
        "🧪 TEST ALERT: Hệ thống đang chạy bình thường",
        "TEST ALERT",
        test_data,
        "info"
    )
    
    # Log activity
    log_user_activity(
        session.get('user_id'),
        session.get('username'),
        'test_slack_alert',
        'Tested Slack alert functionality',
        request.remote_addr,
        request.user_agent.string
    )
    
    return jsonify({"status": "success" if success else "error"})

@app.route('/api/alerts/history')
@login_required
@permission_required('view_alerts')
def get_alerts_history():
    """Lấy lịch sử cảnh báo"""
    limit = request.args.get('limit', 50, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT datetime(timestamp, 'localtime') as local_time, alert_type, message, severity, data_json 
                 FROM alerts_log 
                 ORDER BY timestamp DESC LIMIT ?''', (limit,))
    
    alerts = []
    for row in c.fetchall():
        alert = {
            'timestamp': row[0],
            'alert_type': row[1],
            'message': row[2],
            'severity': row[3],
            'data': json.loads(row[4]) if row[4] else None
        }
        alerts.append(alert)
    
    conn.close()
    return jsonify(alerts)

# ================== WEATHER API ROUTES ==================
@app.route('/api/weather/current')
@login_required
@permission_required('view_weather')
def get_current_weather():
    """Lấy thông tin thời tiết hiện tại"""
    try:
        # Lấy từ database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT temperature, humidity, wind_speed, cloud_cover, 
                            weather_code, sunrise, sunset, is_day, timestamp 
                     FROM weather_data 
                     ORDER BY timestamp DESC LIMIT 1''')
        row = c.fetchone()
        conn.close()
        
        if row:
            weather_data = {
                'temperature': row[0],
                'humidity': row[1],
                'wind_speed': row[2],
                'cloud_cover': row[3],
                'weather_code': row[4],
                'sunrise': row[5],
                'sunset': row[6],
                'is_day': row[7] == 1,
                'last_update': row[8],
                'description': get_weather_code_description(row[4]),
                'icon': get_weather_icon(row[4], row[7] == 1),
                'source': 'database'
            }
        else:
            # Lấy từ API
            weather_data = get_weather_data_openmeteo()
            weather_data.update({
                'description': get_weather_code_description(weather_data.get('weather_code', 0)),
                'icon': get_weather_icon(weather_data.get('weather_code', 0), weather_data.get('is_day', True)),
                'source': 'api',
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify(weather_data)
        
    except Exception as e:
        print(f"❌ Get weather error: {e}")
        return jsonify({
            'temperature': 28.5,
            'humidity': 75,
            'wind_speed': 2.5,
            'cloud_cover': 40,
            'description': 'Dữ liệu tạm thời',
            'icon': '🌤️',
            'source': 'fallback'
        })

@app.route('/api/weather/forecast')
@login_required
@permission_required('view_weather')
def get_weather_forecast():
    """Lấy dự báo thời tiết 24h"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT forecast_json FROM weather_data 
                     ORDER BY timestamp DESC LIMIT 1''')
        row = c.fetchone()
        conn.close()
        
        if row and row[0]:
            forecast_data = json.loads(row[0])
            
            # Format dữ liệu
            formatted_forecast = []
            times = forecast_data.get('times', [])
            temps = forecast_data.get('temperatures', [])
            humids = forecast_data.get('humidities', [])
            clouds = forecast_data.get('clouds', [])
            winds = forecast_data.get('winds', [])
            
            for i in range(min(12, len(times))):
                if i < len(times):
                    time_str = times[i]
                    hour = time_str[11:16] if 'T' in time_str else time_str
                    
                    formatted_forecast.append({
                        'time': hour,
                        'temperature': temps[i] if i < len(temps) else 0,
                        'humidity': humids[i] if i < len(humids) else 0,
                        'cloud_cover': clouds[i] if i < len(clouds) else 0,
                        'wind_speed': winds[i] if i < len(winds) else 0
                    })
            
            return jsonify({'forecast': formatted_forecast})
        
    except Exception as e:
        print(f"❌ Forecast error: {e}")
    
    # Fallback
    return jsonify({
        'forecast': [
            {'time': '09:00', 'temperature': 28, 'humidity': 75, 'cloud_cover': 30, 'wind_speed': 2},
            {'time': '12:00', 'temperature': 32, 'humidity': 65, 'cloud_cover': 20, 'wind_speed': 3},
            {'time': '15:00', 'temperature': 31, 'humidity': 70, 'cloud_cover': 40, 'wind_speed': 2},
            {'time': '18:00', 'temperature': 29, 'humidity': 80, 'cloud_cover': 60, 'wind_speed': 1},
        ]
    })

@app.route('/api/weather/update')
@login_required
@permission_required('manage_system')
def update_weather():
    """Cập nhật thủ công dữ liệu thời tiết"""
    try:
        weather_data = get_weather_data_openmeteo()
        
        # Log activity
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'manual_weather_update',
            'Manually updated weather data',
            request.remote_addr,
            request.user_agent.string
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Cập nhật thời tiết thành công',
            'temperature': weather_data['temperature']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    

@app.route('/api/alerts/count')
@login_required
@permission_required('view_alerts')
def get_alerts_count():
    """Lấy số lượng cảnh báo theo loại"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Tổng số cảnh báo
        c.execute('SELECT COUNT(*) FROM alerts_log')
        total_alerts = c.fetchone()[0]
        
        # Số cảnh báo theo mức độ
        c.execute('''SELECT severity, COUNT(*) 
                     FROM alerts_log 
                     GROUP BY severity''')
        
        severity_counts = {'critical': 0, 'warning': 0, 'info': 0, 'success': 0}
        for row in c.fetchall():
            severity = row[0]
            count = row[1]
            if severity in severity_counts:
                severity_counts[severity] = count
        
        # Số cảnh báo trong 24 giờ qua
        c.execute('''SELECT COUNT(*) FROM alerts_log 
                     WHERE timestamp > datetime('now', '-24 hours')''')
        last_24h = c.fetchone()[0]
        
        # Số cảnh báo chưa đọc (trong 1 giờ qua)
        c.execute('''SELECT COUNT(*) FROM alerts_log 
                     WHERE timestamp > datetime('now', '-1 hour')''')
        recent_alerts = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'total_alerts': total_alerts,
            'critical_count': severity_counts['critical'],
            'warning_count': severity_counts['warning'],
            'info_count': severity_counts['info'],
            'success_count': severity_counts['success'],
            'last_24h': last_24h,
            'recent_alerts': recent_alerts,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"❌ Get alerts count error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Lỗi khi đếm cảnh báo: {str(e)}'
        }), 500

# ================== DELETE ALERTS API ==================
@app.route('/api/alerts/clear', methods=['DELETE'])
@login_required
@permission_required('clear_alerts')
def clear_all_alerts():
    """Xóa tất cả lịch sử cảnh báo"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Đếm số lượng cảnh báo trước khi xóa
        c.execute('SELECT COUNT(*) FROM alerts_log')
        count_before = c.fetchone()[0]
        
        # Xóa tất cả cảnh báo
        c.execute('DELETE FROM alerts_log')
        
        conn.commit()
        
        # Đếm số lượng sau khi xóa
        c.execute('SELECT COUNT(*) FROM alerts_log')
        count_after = c.fetchone()[0]
        
        conn.close()
        
        # Ghi log hành động
        user = session.get('username', 'unknown')
        print(f"🗑️ User '{user}' cleared all alerts. Removed {count_before} alerts.")
        
        # Log activity
        log_user_activity(
            session.get('user_id'),
            session.get('username'),
            'clear_all_alerts',
            f'Cleared {count_before} alerts from history',
            request.remote_addr,
            request.user_agent.string
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Đã xóa {count_before} cảnh báo',
            'deleted_count': count_before,
            'remaining_count': count_after
        })
        
    except Exception as e:
        print(f"❌ Clear alerts error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Lỗi khi xóa cảnh báo: {str(e)}'
        }), 500

# ================== CONTROL ROUTES (PICO Control) ==================
@app.route('/api/control/pico', methods=['POST'])
@login_required
@permission_required('control_pico')
def control_pico():
    """Gửi lệnh điều khiển đến PICO"""
    try:
        data = request.json
        command = data.get('command')
        
        if command:
            command_queue.append(data)
            
            # Log activity
            log_user_activity(
                session.get('user_id'),
                session.get('username'),
                'pico_control',
                f'Sent command to PICO: {command}',
                request.remote_addr,
                request.user_agent.string
            )
            
            return jsonify({
                'status': 'success',
                'message': f'Đã gửi lệnh {command} đến PICO'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Thiếu lệnh!'
            }), 400
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Lỗi: {str(e)}'
        }), 500

# ================== WEB SOCKET ==================
@socketio.on('connect')
def handle_connect():
    print(f'🌐 Web client connected: {session.get("username", "unknown")}')
    
    # Emit user info on connect
    if 'user_id' in session:
        socketio.emit('user_info', {
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name'),
            'permissions': USER_ROLES.get(session.get('role', 'guest'), USER_ROLES['guest'])['permissions']
        })
    
    socketio.emit('sensor_update', system_state['sensors'])
    socketio.emit('status_update', {
        'pico_online': system_state['pico_online'],
        'last_update': system_state['last_pico_update']
    })
    
    # Gửi thông tin thời tiết
    current_weather = get_current_weather()
    socketio.emit('weather_update', current_weather.json)

@socketio.on('control_command')
def handle_control_command(data):
    """Nhận lệnh từ web dashboard"""
    # Kiểm tra quyền trước khi xử lý
    if 'user_id' not in session:
        socketio.emit('error', {'message': 'Chưa đăng nhập!'})
        return
    
    user_role = session.get('role', 'guest')
    if 'control_pico' not in USER_ROLES.get(user_role, USER_ROLES['guest'])['permissions']:
        socketio.emit('error', {'message': 'Không có quyền điều khiển!'})
        return
    
    print(f"🎮 Web control from {session.get('username')}: {data}")
    command_queue.append(data)
    
    if data.get('command') == 'SET_MODE':
        system_state['sensors']['mode'] = data.get('mode', 'AUTO')
    elif data.get('command') == 'SET_ENERGY_MODE':
        system_state['sensors']['energy_saving'] = data.get('energy_saving', False)
    
    socketio.emit('sensor_update', system_state['sensors'])
    
    # Log activity
    log_user_activity(
        session.get('user_id'),
        session.get('username'),
        'socket_control',
        f'Sent control command via socket: {data.get("command")}',
        request.remote_addr,
        request.user_agent.string
    )

# ================== SCHEDULED TASKS ==================
def scheduled_tasks():
    """Các task chạy định kỳ"""
    last_daily_report_sent = None
    
    while True:
        try:
            now = datetime.now()
            
            # 1. Gửi báo cáo hàng ngày lúc 18:00
            if now.hour == 18 and now.minute == 0:
                if last_daily_report_sent != now.date():
                    send_daily_slack_report()
                    last_daily_report_sent = now.date()
                    time.sleep(60)  # Chờ 1 phút để không gửi nhiều lần
            
            # 2. Cập nhật thời tiết
            weather_data = get_weather_data_openmeteo()
            
            # Tạo dữ liệu thời tiết để gửi qua socket
            try:
                # Lấy dữ liệu thời tiết từ database hoặc API
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''SELECT temperature, humidity, wind_speed, cloud_cover, 
                                    weather_code, sunrise, sunset, is_day 
                             FROM weather_data 
                             ORDER BY timestamp DESC LIMIT 1''')
                row = c.fetchone()
                conn.close()
                
                if row:
                    current_weather = {
                        'temperature': row[0],
                        'humidity': row[1],
                        'wind_speed': row[2],
                        'cloud_cover': row[3],
                        'weather_code': row[4],
                        'sunrise': row[5],
                        'sunset': row[6],
                        'is_day': row[7] == 1,
                        'description': get_weather_code_description(row[4]),
                        'icon': get_weather_icon(row[4], row[7] == 1),
                        'source': 'database'
                    }
                else:
                    current_weather = {
                        'temperature': weather_data['temperature'],
                        'humidity': weather_data['humidity'],
                        'wind_speed': weather_data['wind_speed'],
                        'cloud_cover': weather_data['cloud_cover'],
                        'description': get_weather_code_description(weather_data.get('weather_code', 0)),
                        'icon': get_weather_icon(weather_data.get('weather_code', 0), weather_data.get('is_day', True)),
                        'source': 'api'
                    }
                
                # Gửi qua socket
                socketio.emit('weather_update', current_weather)
                
            except Exception as weather_error:
                print(f"⚠️  Weather socket error: {weather_error}")
                # Gửi dữ liệu fallback
                socketio.emit('weather_update', {
                    'temperature': 28.5,
                    'humidity': 75,
                    'wind_speed': 2.5,
                    'cloud_cover': 40,
                    'description': 'Dữ liệu tạm thời',
                    'icon': '🌤️',
                    'source': 'fallback'
                })
            
            # 3. Kiểm tra cảnh báo
            check_alerts()
            
            # 4. Kiểm tra PICO online
            if (system_state['pico_online'] and 
                time.time() - system_state['sensors']['timestamp'] > 30):
                system_state['pico_online'] = False
                socketio.emit('status_update', {
                    'pico_online': False,
                    'last_update': system_state['last_pico_update']
                })
                print("⚠️  PICO offline - no data received")
                
        except Exception as e:
            print(f"❌ Scheduled task error: {e}")
        
        time.sleep(ALERT_CONFIG['check_interval'])

# ================== ERROR HANDLERS ==================
@app.errorhandler(403)
def forbidden_error(error):
    return render_template('error.html', 
                         error_code=403,
                         error_message='Không có quyền truy cập!',
                         username=session.get('username')), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html',
                         error_code=404,
                        error_message='Trang không tồn tại!',
                         username=session.get('username')), 404
@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
                         error_code=500,
                         error_message='Lỗi server nội bộ!',
                         username=session.get('username')), 500

# ================== MAIN ==================
if __name__ == '__main__':
    init_db()
    # Start scheduled tasks
    task_thread = threading.Thread(target=scheduled_tasks, daemon=True)
    task_thread.start()
    
    print("🚀 Solar Tracker Server starting...")
    print("🔐 Role-Based Access Control ENABLED")
    print("📊 User Roles:")
    for role_name, role_info in USER_ROLES.items():
        print(f"   - {role_name}: Level {role_info['level']}")
    print("👤 Default Users:")
    print("   - admin / admin123 (Quản trị viên)")
    print("   - operator / operator123 (Vận hành viên)")
    print("   - viewer / viewer123 (Người xem)")
    print("   - guest / guest123 (Khách)")
    print("🌤️  Weather API: Open-Meteo (Free)")
    print("📊 Báo cáo Slack: #social (18:00 hàng ngày)")
    print("🚨 Cảnh báo Slack: #cảnh-báo (tự động)")
    print("🌐 Dashboard: http://localhost:5000")
    print("🔐 Login: http://localhost:5000/login")
    print("🔋 Alerts: Pin <20%, Không công suất, PICO offline, Hiệu suất thấp")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  