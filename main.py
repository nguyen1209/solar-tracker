from machine import Pin, PWM, I2C, ADC
import time, math, network, urequests, json
from ads1x15 import ADS1115

# ================== CONFIG ==================
SSID = "awd"
PASSWORD = "nguyen12"
SERVER_URL = "http://192.168.137.1:5000"

# ================== PANEL CONFIG ==================
PANEL_V_RATED = 6.0
PANEL_P_MAX = 20.0
PANEL_I_MAX = PANEL_P_MAX / PANEL_V_RATED

# ================== BATTERY CONFIG ==================
BATTERY_V_MAX = 12.6
BATTERY_V_MIN = 10.5
BATTERY_CAPACITY_AH = 3.0
VOLTAGE_DIVIDER_RATIO = 5.7

# ================== TRACKING CONFIG ==================
SMOOTHING_ALPHA = 0.6
MOVEMENT_SPEED = 14
ELEVATION_BOTTOM_BOOST = 1
MIN_LIGHT_DIFF = 20

# ================== WIFI ==================
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("📡 Dang ket noi WiFi...")
        wlan.connect(SSID, PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
            print('.', end='')
    if wlan.isconnected():
        print(f"\n✅ WiFi OK: {wlan.ifconfig()[0]}")
        return True
    print("\n❌ WiFi that bai")
    return False

# ================== HTTP CLIENT ==================
def send_sensor_data(data):
    try:
        res = urequests.post(f"{SERVER_URL}/api/sensor-data", json=data, timeout=3)
        res.close()
        return True
    except Exception as e:
        print("❌ Loi gui data:", e)
        return False

def get_control_command():
    try:
        res = urequests.get(f"{SERVER_URL}/api/get-command", timeout=3)
        data = res.json()
        res.close()
        return data if data.get("command") else None
    except:
        return None

# ================== LCD CLASS ==================
class I2cLcd:
    def __init__(self, i2c, addr, lines, cols):
        self.i2c = i2c
        self.addr = addr
        self.lines = lines
        self.cols = cols
        self.backlight = 0x08
        self.init_display()
    
    def init_display(self):
        for cmd in (0x33, 0x32, 0x28, 0x0C, 0x06, 0x01):
            self.cmd(cmd)
            time.sleep_ms(5)
    
    def cmd(self, val):
        hi = val & 0xF0
        lo = (val << 4) & 0xF0
        for x in (hi | 0x0C | self.backlight,
                  hi | 0x08 | self.backlight,
                  lo | 0x0C | self.backlight,
                  lo | 0x08 | self.backlight):
            self.i2c.writeto(self.addr, bytes([x]))
    
    def write_char(self, val):
        hi = val & 0xF0
        lo = (val << 4) & 0xF0
        for x in (hi | 0x0D | self.backlight,
                  hi | 0x09 | self.backlight,
                  lo | 0x0D | self.backlight,
                  lo | 0x09 | self.backlight):
            self.i2c.writeto(self.addr, bytes([x]))
    
    def putstr(self, s):
        for c in s:
            self.write_char(ord(c))
    
    def clear(self):
        self.cmd(0x01)
        time.sleep_ms(5)
    
    def move_to(self, col, row):
        addr = col + (0x40 if row else 0)
        self.cmd(0x80 | addr)

# ================== LCD UI ==================
def lcd_welcome():
    if lcd_available:
        lcd.clear()
        lcd.putstr(" HE THONG")
        lcd.move_to(0, 1)
        lcd.putstr(" KHOI DONG")

def lcd_connecting():
    if lcd_available:
        lcd.clear()
        lcd.putstr(" Dang ket noi")
        lcd.move_to(0, 1)
        lcd.putstr(" Vui long doi")

def lcd_ready():
    if lcd_available:
        lcd.clear()
        lcd.putstr(" SAN SANG")
        lcd.move_to(0, 1)
        lcd.putstr(" BAT DAU...")

def lcd_update_status(auto_mode, az, el, voltage, battery_voltage, battery_soc, remaining_capacity):
    if lcd_available:
        lcd.clear()
        if energy_saving:
            mode_text = "TIET KIEM"
        else:
            mode_text = "TU DONG" if auto_mode else "THU CONG"
        line1 = f"{mode_text[:8]} {voltage:.1f}V"
        line2 = f"PIN:{battery_voltage:.1f}V {battery_soc:.0f}%"
        lcd.putstr(line1[:16])
        lcd.move_to(0, 1)
        lcd.putstr(line2[:16])

# ================== INIT HARDWARE ==================
i2c = I2C(1,sda=Pin(2), scl=Pin(3), freq=400000)

# LCD setup
lcd_available = False
lcd = None
try:
    dev = i2c.scan()
    print("I2C found:", dev)
    if 0x27 in dev:
        lcd = I2cLcd(i2c, 0x27, 2, 16)
        lcd_available = True
    elif 0x3F in dev:
        lcd = I2cLcd(i2c, 0x3F, 2, 16)
        lcd_available = True
except:
    lcd_available = False

# Servo setup - SERVO 180 DO
servos = [PWM(Pin(4)), PWM(Pin(5))]
for s in servos:
    s.freq(50)

# ================== SERVO FUNCTIONS (SERVO 180 DO) ==================
def set_servo_angle(servo, angle):
    """
    Dieu khien servo 180 do bang goc (0–180)
    """
    angle = max(0, min(180, angle))  # Gioi han cung 0–180 do
    # Map 0–180° -> 500–2500 us
    duty_us = 500 + int((angle / 180.0) * 2000)
    duty_u16 = int((duty_us / 20000.0) * 65535)
    servo.duty_u16(max(0, min(65535, duty_u16)))

def stop_servos():
    """
    Ngung gui xung PWM de tiet kiem dien
    """
    for servo in servos:
        servo.duty_u16(0)

# ADS1115 setup
ads = None
ads_available = False
try:
    ads = ADS1115(i2c, address=0x48)
    ads_available = True
    print("✅ ADS1115 OK")
except:
    ads_available = False
    print("❌ ADS1115 not found")

# Voltage ADC
adc_voltage = ADC(Pin(27))
adc_battery = ADC(Pin(26))

def read_voltage():
    try:
        raw = adc_voltage.read_u16()
        voltage = ((raw / 65535.0) * 5.0) * 6
        return voltage
    except:
        return 0.0

def read_battery_voltage():
    try:
        raw = adc_battery.read_u16()
        voltage = (raw / 65535.0) * 3 * VOLTAGE_DIVIDER_RATIO
        return round(voltage, 2)
    except Exception as e:
        print("❌ Loi doc battery voltage:", e)
        return 0.0

def calculate_battery_soc(voltage):
    if voltage >= BATTERY_V_MAX:
        return 100
    elif voltage <= BATTERY_V_MIN:
        return 0
    else:
        soc = ((voltage - BATTERY_V_MIN) / (BATTERY_V_MAX - BATTERY_V_MIN)) * 100
        return max(0, min(100, round(soc)))

def estimate_remaining_capacity(soc):
    return (soc / 100.0) * BATTERY_CAPACITY_AH

def estimate_current(v):
    if v <= 0:
        return 0.0
    v = min(v, PANEL_V_RATED)
    return round(PANEL_I_MAX * (v / PANEL_V_RATED), 2)

def read_light():
    """Doc 4 cam bien anh sang tu ADS1115"""
    if ads_available:
        try:
            return [
                ads.read(0, 0),  # A0: Top Right
                ads.read(1, 1),  # A1: Top Left
                ads.read(2, 2),  # A2: Bottom Left
                ads.read(3, 3)   # A3: Bottom Right
            ]
        except:
            return [1000, 1100, 900, 1200]
    return [1000, 1100, 900, 1200]

def calculate_efficiency(voltage, current):
    actual_power = voltage * current
    if PANEL_P_MAX > 0:
        efficiency = (actual_power / PANEL_P_MAX) * 100
        return min(100, max(0, efficiency))
    return 0.0

def calculate_light_intensity(light_values):
    if light_values and len(light_values) > 0:
        return sum(light_values) / len(light_values)
    return 0

# ================== SMOOTH RATIO CALCULATION ==================
def compute_smooth_ratio(light1, light2, sensitivity=2):
    """Tinh ty le anh sang muot ma"""
    total = light1 + light2
    if total == 0:
        return 0
    ratio = (light1 - light2) / total
    smooth_ratio = ratio * sensitivity
    return max(-1.0, min(1.0, smooth_ratio))

# ================== TRACKING ==================
def compute_tracking_smooth(smoothed_values):
    """
    Tra ve speed_azimuth, speed_elevation
    (gia tri ty le, se duoc nhan voi MOVEMENT_SPEED)
    """
    # Azimuth
    left_light = smoothed_values[1] + smoothed_values[2]
    right_light = smoothed_values[0] + smoothed_values[3]
    
    light_diff_az = abs(left_light - right_light)
    if light_diff_az > MIN_LIGHT_DIFF:
        az_ratio = compute_smooth_ratio(right_light, left_light, sensitivity=1)
        speed_azimuth = az_ratio * MOVEMENT_SPEED
    else:
        speed_azimuth = 0
    
    # Elevation
    top_light = smoothed_values[0] + smoothed_values[1]
    bottom_light = smoothed_values[2] + smoothed_values[3]
    bottom_boosted = bottom_light * ELEVATION_BOTTOM_BOOST
    
    light_diff_el = abs(top_light - bottom_boosted)
    if light_diff_el > MIN_LIGHT_DIFF:
        el_ratio = compute_smooth_ratio(bottom_boosted, top_light, sensitivity=1)
        speed_elevation = -el_ratio * MOVEMENT_SPEED
    else:
        speed_elevation = 0
    
    return speed_azimuth, speed_elevation

# ================== MAIN ==================
print("🚀 Bat dau he thong...")
print(f"⚙️ Tracking: α={SMOOTHING_ALPHA}, Speed={MOVEMENT_SPEED}, Min_diff={MIN_LIGHT_DIFF}")

if lcd_available:
    lcd_welcome()

time.sleep(2)

if lcd_available:
    lcd_connecting()

wifi_ok = connect_wifi()

# Khoi tao goc va smoothed values
current_angles = [90.0, 90.0]
smoothed_values = [0.0, 0.0, 0.0, 0.0]
angle_history = [[90.0, 90.0] for _ in range(5)]
history_index = 0

# Dung servo ban dau (tat PWM)
stop_servos()

if lcd_available:
    lcd_ready()

time.sleep(1)

auto_mode = True
energy_saving = False
battery_voltage = 0.0
battery_soc = 0
remaining_capacity = 0.0
last_send = 0
last_cmd = 0
last_lcd = 0
prev_energy_saving = energy_saving  # de detect chuyen trang thai tiet kiem

led = Pin("LED", Pin.OUT)

print("🌞 He thong da san sang!")
print("🌞 Layout cam bien: A0=TopRight, A1=TopLeft, A2=BottomLeft, A3=BottomRight")

try:
    while True:
        now = time.time()
        led.toggle()
        
        # ================== DOC THONG SO PIN ==================
        battery_voltage = read_battery_voltage()
        battery_soc = calculate_battery_soc(battery_voltage)
        remaining_capacity = estimate_remaining_capacity(battery_soc)
        
        # ================== LAY LENH WEB ==================
        if wifi_ok and now - last_cmd >= 1:
            cmd = get_control_command()
            if cmd:
                c = cmd["command"]
                if c == "SET_MODE":
                    auto_mode = (cmd["mode"] == "AUTO")
                    print("Chuyen che do:", "AUTO" if auto_mode else "MANUAL")
                elif c == "SET_ANGLE" and not auto_mode and not energy_saving:
                    # Manual mode - dieu khien vi tri truc tiep
                    az = cmd.get("azimuth", current_angles[0])
                    el = cmd.get("elevation", current_angles[1])

                    current_angles[0] = max(0.0, min(180.0, az))
                    current_angles[1] = max(0.0, min(180.0, el))

                    set_servo_angle(servos[0], current_angles[0])
                    set_servo_angle(servos[1], current_angles[1])

                    print(f"🎯 Manual: AZ={current_angles[0]:.1f}°, EL={current_angles[1]:.1f}°")
                elif c == "SET_ENERGY_MODE":
                    energy_saving = cmd.get("energy_saving", False)
                    print("Nang luong:", "TIET KIEM" if energy_saving else "BINH THUONG")
            last_cmd = now

        # ================== CHUYEN TRANG THAI TIET KIEM ==================
        if energy_saving != prev_energy_saving:
            if energy_saving:
                # Vua BAT che do tiet kiem
                current_angles = [90.0, 90.0]
                set_servo_angle(servos[0], current_angles[0])
                set_servo_angle(servos[1], current_angles[1])
               

     
                print("🔋 Vao che do TIET KIEM: dua ve 90° va dung servo")
            else:
                # Vua TAT che do tiet kiem
                set_servo_angle(servos[0], current_angles[0])
                set_servo_angle(servos[1], current_angles[1])
                print("🔋 Thoat che do TIET KIEM: khoi dong lai servo")
            prev_energy_saving = energy_saving
        
        # ================== ENERGY SAVING MODE ==================
        if energy_saving:
            # Che do tiet kiem: khong dieu khien servo, chi gui du lieu cham hon
            light_values = [0, 0, 0, 0]
            send_interval = 10
        else:
            send_interval = 3
            
            # ================== AUTO TRACKING ==================
            if auto_mode:
                # Doc gia tri cam bien anh sang
                light_values = read_light()
                
                # Loc muot cho cam bien anh sang
                for i in range(4):
                    smoothed_values[i] = (SMOOTHING_ALPHA * light_values[i] + 
                                          (1 - SMOOTHING_ALPHA) * smoothed_values[i])
                
                # Tinh toan tracking speed (ty le)
                speed_azimuth, speed_elevation = compute_tracking_smooth(smoothed_values)
                
                # Cap nhat goc hien tai
                angle_step = 1.0
                angle_change_az = speed_azimuth * angle_step
                angle_change_el = speed_elevation * angle_step
                
                max_angle_change = 6.0
                if abs(angle_change_az) > max_angle_change:
                    angle_change_az = max_angle_change * (1 if angle_change_az > 0 else -1)
                if abs(angle_change_el) > max_angle_change:
                    angle_change_el = max_angle_change * (1 if angle_change_el > 0 else -1)
                
                current_angles[0] += angle_change_az
                current_angles[1] += angle_change_el
                current_angles[0] = max(0.0, min(180.0, current_angles[0]))
                current_angles[1] = max(0.0, min(180.0, current_angles[1]))
                
                # Cap nhat lich su goc
                angle_history[history_index] = [current_angles[0], current_angles[1]]
                history_index = (history_index + 1) % 5
                
                # Dieu khien servo theo GOC
                set_servo_angle(servos[0], current_angles[0])
                set_servo_angle(servos[1], current_angles[1])
                
                # Debug display
                left_light = smoothed_values[1] + smoothed_values[2]
                right_light = smoothed_values[0] + smoothed_values[3]
                top_light = smoothed_values[0] + smoothed_values[1]
                bottom_light = smoothed_values[2] + smoothed_values[3]
                
                print(
                    "🌞 L:{} R:{} T:{} B:{} | AZ:{:.1f}° EL:{:.1f}°".format(
                        int(left_light), int(right_light), int(top_light), int(bottom_light),
                        current_angles[0], current_angles[1]
                    )
                )
            else:
                # Manual mode: giu goc hien tai, chi doc cam bien
                light_values = read_light()
        
        # ================== LCD UPDATE ==================
        if now - last_lcd >= 1:
            voltage = read_voltage()
            lcd_update_status(auto_mode, current_angles[0], current_angles[1],
                              voltage, battery_voltage, battery_soc, remaining_capacity)
            last_lcd = now
        
        # ================== SEND DATA WEB ==================
        if wifi_ok and now - last_send >= send_interval:
            voltage = read_voltage()
            current = estimate_current(voltage)
            power = voltage * current
            efficiency = calculate_efficiency(voltage, current)
            light_intensity = calculate_light_intensity(smoothed_values if not energy_saving else light_values)
            
            packet = {
                "azimuth": round(current_angles[0], 1),
                "elevation": round(current_angles[1], 1),
                "voltage": round(voltage, 2),
                "current": current,
                "power": round(power, 2),
                "efficiency": round(efficiency, 1),
                "light_intensity": light_intensity,
                "light_sensors": smoothed_values if not energy_saving else light_values,
                "battery_voltage": battery_voltage,
                "battery_soc": battery_soc,
                "remaining_capacity_ah": round(remaining_capacity, 2),
                "battery_capacity_ah": BATTERY_CAPACITY_AH,
                "mode": "AUTO" if auto_mode else "MANUAL",
                "energy_saving": energy_saving,
                "timestamp": now
            }
            
            if send_sensor_data(packet):
                print(
                    "📤 Gui: AZ={:.1f}° EL={:.1f}° P={:.1f}W Bat={}%".format(
                        current_angles[0], current_angles[1], power, battery_soc
                    )
                )
            last_send = now
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("🛑 Stopping program...")
    stop_servos()
except Exception as e:
    print("❌ Loi:", e)
    stop_servos()
    if lcd_available:
        lcd.clear()
        lcd.putstr(" LOI HE THONG")
        lcd.move_to(0, 1)
        lcd.putstr(" KIEM TRA LOG")

