const socket = io();
let lastPicoUpdate = 0;
let historyChart = null;
let dailyChart = null;
let currentChartType = 'power';
let currentDailyChartType = 'power';
let alertsBadgeInterval = null;

// Tab management
function openTab(tabName, evt) {
    const e = evt || window.event;

    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    if (e && e.currentTarget) {
        e.currentTarget.classList.add('active');
    }

    if (tabName === 'history') {
        setTimeout(() => {
            loadHistoryChart();
        }, 100);
    } else if (tabName === 'daily') {
        setTimeout(() => {
            loadAvailableDates();
        }, 100);
    } else if (tabName === 'alerts') {
        setTimeout(() => {
            loadAlertsHistory();
        }, 100);
    }
}

// ================== WEATHER FUNCTIONS ==================
function loadWeatherData() {
    fetch('/api/weather/current')
        .then(response => response.json())
        .then(data => {
            updateWeatherUI(data);
        })
        .catch(error => {
            console.error('Weather error:', error);
        });
}

function updateWeatherUI(data) {
    document.getElementById('weatherTemp').textContent = data.temperature.toFixed(1) + '°C';
    document.getElementById('weatherDesc').textContent = data.description;
    document.getElementById('weatherIcon').textContent = data.icon;
    document.getElementById('weatherHumidity').textContent = data.humidity.toFixed(0) + '%';
    document.getElementById('weatherWind').textContent = data.wind_speed.toFixed(1) + ' km/h';
    document.getElementById('weatherClouds').textContent = data.cloud_cover.toFixed(0) + '%';

    if (data.sunrise && data.sunset) {
        const sunriseTime = data.sunrise.split('T')[1]?.substring(0, 5) || data.sunrise.substring(11, 16);
        const sunsetTime = data.sunset.split('T')[1]?.substring(0, 5) || data.sunset.substring(11, 16);
        document.getElementById('weatherSunrise').textContent = sunriseTime + ' / ' + sunsetTime;
    }

    // Update forecast
    loadWeatherForecast();
}

function loadWeatherForecast() {
    fetch('/api/weather/forecast')
        .then(response => response.json())
        .then(data => {
            updateForecastUI(data.forecast);
        })
        .catch(error => {
            console.error('Forecast error:', error);
        });
}

function updateForecastUI(forecast) {
    const forecastContainer = document.getElementById('weatherForecast');
    forecastContainer.innerHTML = '';

    forecast.forEach(item => {
        const forecastItem = document.createElement('div');
        forecastItem.className = 'forecast-item';

        let icon = '☀️';
        if (item.cloud_cover > 70) icon = '☁️';
        else if (item.cloud_cover > 30) icon = '🌤️';

        forecastItem.innerHTML = `
            <div class="forecast-time">${item.time}</div>
            <div class="forecast-icon">${icon}</div>
            <div class="forecast-temp">${item.temperature.toFixed(0)}°</div>
            <div style="font-size: 0.8em; opacity: 0.8;">${item.humidity.toFixed(0)}%</div>
        `;

        forecastContainer.appendChild(forecastItem);
    });
}

function updateWeather(evt) {
    fetch('/api/weather/update')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                loadWeatherData();
                showToast('✅ Đã cập nhật thời tiết', 'success');
            }
        });
}

// ================== SENSOR DATA FUNCTIONS ==================
socket.on('sensor_update', function(data) {
    updateDashboard(data);
    lastPicoUpdate = Date.now();
    updatePicoStatus(true);
});

socket.on('weather_update', function(data) {
    updateWeatherUI(data);
});

function updateDashboard(data) {
    // Update sensor data
    document.getElementById('azimuthValue').textContent = data.azimuth.toFixed(1) + '°';
    document.getElementById('elevationValue').textContent = data.elevation.toFixed(1) + '°';
    document.getElementById('currentValue').textContent = data.current.toFixed(2) + ' A';
    document.getElementById('voltageValue').textContent = data.voltage.toFixed(1) + ' V';
    document.getElementById('powerValue').textContent = data.power.toFixed(1) + ' W';
    document.getElementById('efficiencyValue').textContent = (data.efficiency || 0).toFixed(1) + '%';

    // Update battery data
    const batteryVoltage = data.battery_voltage || 0;
    const batterySoc = data.battery_soc || 0;
    const remainingCapacity = data.remaining_capacity_ah || 0;
    const batteryCapacity = data.battery_capacity_ah || 3.0;

    document.getElementById('batteryVoltageValue').textContent = batteryVoltage.toFixed(1) + ' V';
    document.getElementById('batterySocValue').textContent = batterySoc.toFixed(0) + '%';
    document.getElementById('batteryCapacityText').textContent =
        remainingCapacity.toFixed(1) + ' / ' + batteryCapacity.toFixed(1) + ' Ah';

    // Update battery progress bar
    const progressBar = document.getElementById('batteryProgressBar');
    progressBar.style.width = batterySoc + '%';

    // Update battery color based on SOC
    const socValue = document.getElementById('batterySocValue');
    const statusText = document.getElementById('batteryStatusText');

    if (batterySoc >= 80) {
        socValue.className = 'battery-percentage battery-full';
        progressBar.style.background = '#38a169';
        statusText.textContent = 'ĐẦY';
        statusText.style.color = '#38a169';
    } else if (batterySoc >= 50) {
        socValue.className = 'battery-percentage battery-high';
        progressBar.style.background = '#68d391';
        statusText.textContent = 'TỐT';
        statusText.style.color = '#68d391';
    } else if (batterySoc >= 20) {
        socValue.className = 'battery-percentage battery-medium';
        progressBar.style.background = '#d69e2e';
        statusText.textContent = 'TRUNG BÌNH';
        statusText.style.color = '#d69e2e';
    } else {
        socValue.className = 'battery-percentage battery-low';
        progressBar.style.background = '#e53e3e';
        statusText.textContent = 'YẾU';
        statusText.style.color = '#e53e3e';
    }

    // Update sliders
    document.getElementById('azimuthSlider').value = data.azimuth;
    document.getElementById('elevationSlider').value = data.elevation;
    document.getElementById('azimuthSliderValue').textContent = data.azimuth.toFixed(1) + '°';
    document.getElementById('elevationSliderValue').textContent = data.elevation.toFixed(1) + '°';

    // Update toggles
    document.getElementById('energySavingToggle').checked = data.energy_saving;

    // Update mode buttons
    updateModeButtons(data.mode);

    // Update timestamp
    const now = new Date();
    document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
}

function updateModeButtons(mode) {
    const autoBtn = document.getElementById('autoBtn');
    const manualBtn = document.getElementById('manualBtn');
    const manualControls = document.getElementById('manualControls');

    if (mode === 'AUTO') {
        autoBtn.classList.add('active');
        manualBtn.classList.remove('active');
        manualControls.style.display = 'none';
    } else {
        autoBtn.classList.remove('active');
        manualBtn.classList.add('active');
        manualControls.style.display = 'block';
    }
}

function updatePicoStatus(online) {
    const picoDot = document.getElementById('picoStatus');
    picoDot.className = 'status-dot ' + (online ? 'online' : 'offline');
}

function sendControl(command, value) {
    const data = { command: command };

    if (command === 'SET_MODE') data.mode = value;
    if (command === 'SET_ENERGY_MODE') data.energy_saving = value;

    socket.emit('control_command', data);
    console.log('Sent control:', data);
}

function updateSlider(type) {
    const slider = document.getElementById(type + 'Slider');
    const valueDisplay = document.getElementById(type + 'SliderValue');
    valueDisplay.textContent = slider.value + '°';
}

function sendManualAngles() {
    const azimuth = document.getElementById('azimuthSlider').value;
    const elevation = document.getElementById('elevationSlider').value;

    socket.emit('control_command', {
        command: 'SET_ANGLE',
        azimuth: parseFloat(azimuth),
        elevation: parseFloat(elevation)
    });
}

// ================== SLACK TEST FUNCTIONS ==================
async function testSlackAlert(evt) {
    const e = evt || window.event;
    const button = e && e.currentTarget ? e.currentTarget : null;
    if (!button) return;

    const originalText = button.innerHTML;
    const originalBackground = button.style.background;

    try {
        button.innerHTML = '<span class="loading"></span> Đang gửi...';
        button.disabled = true;
        button.style.opacity = '0.7';
        button.style.cursor = 'wait';

        const response = await fetch('/api/test-slack-alert');
        const data = await response.json();

        if (data.status === 'success') {
            button.innerHTML = '✅ Đã gửi!';
            button.style.background = 'linear-gradient(135deg, #38a169 0%, #2f855a 100%)';
            showToast('✅ Đã gửi test cảnh báo thành công!', 'success');
        } else {
            button.innerHTML = '❌ Thất bại';
            button.style.background = 'linear-gradient(135deg, #e53e3e 0%, #c53030 100%)';
            showToast('❌ Gửi test cảnh báo thất bại', 'error');
        }

    } catch (error) {
        console.error('Test alert error:', error);
        button.innerHTML = '❌ Lỗi';
        button.style.background = 'linear-gradient(135deg, #718096 0%, #4a5568 100%)';
        showToast('❌ Lỗi kết nối', 'error');
    } finally {
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
            button.style.background = originalBackground || 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)';
        }, 2000);
    }
}

async function testSlackReport(evt) {
    const e = evt || window.event;
    const button = e && e.currentTarget ? e.currentTarget : null;
    if (!button) return;

    const originalText = button.innerHTML;
    const originalBackground = button.style.background;

    try {
        button.innerHTML = '<span class="loading"></span> Đang gửi...';
        button.disabled = true;
        button.style.opacity = '0.7';
        button.style.cursor = 'wait';

        const response = await fetch('/api/test-slack-report');
        const data = await response.json();

        if (data.status === 'success') {
            button.innerHTML = '✅ Đã gửi!';
            button.style.background = 'linear-gradient(135deg, #38a169 0%, #2f855a 100%)';
            showToast('✅ Đã gửi test báo cáo thành công!', 'success');
        } else {
            button.innerHTML = '❌ Thất bại';
            button.style.background = 'linear-gradient(135deg, #e53e3e 0%, #c53030 100%)';
            showToast('❌ Gửi test báo cáo thất bại', 'error');
        }

    } catch (error) {
        console.error('Test report error:', error);
        button.innerHTML = '❌ Lỗi';
        button.style.background = 'linear-gradient(135deg, #718096 0%, #4a5568 100%)';
        showToast('❌ Lỗi kết nối', 'error');
    } finally {
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
            button.style.background = originalBackground || 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
        }, 2000);
    }
}

// ================== ALERTS HISTORY FUNCTIONS ==================
async function loadAlertsHistory() {
    try {
        const alertsContainer = document.getElementById('alertsHistory');
        alertsContainer.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Đang tải...</div>';

        const response = await fetch('/api/alerts/history?limit=20');
        const alerts = await response.json();

        if (alerts.length === 0) {
            alertsContainer.innerHTML = '<div class="no-data">Không có cảnh báo nào</div>';
            return;
        }

        let html = '';
        alerts.forEach(alert => {
            const alertClass = alert.severity || 'info';
            const icon = getAlertIcon(alert.severity);
            const time = new Date(alert.timestamp).toLocaleString('vi-VN', {
                timeZone: 'Asia/Ho_Chi_Minh',
                hour12: false
            });
            html += `
                <div class="alert-item ${alertClass}">
                    <div class="alert-time">${time}</div>
                    <div class="alert-message">${icon} ${alert.message}</div>
                    ${alert.data ? `<div style="font-size: 0.9em; margin-top: 5px; color: #4a5568;">
                        ${Object.entries(alert.data).map(([key, value]) => `${key}: ${value}`).join(', ')}
                    </div>` : ''}
                    <div class="alert-type">${alert.alert_type}</div>
                </div>
            `;
        });

        alertsContainer.innerHTML = html;

        // Cập nhật badge sau khi tải xong
        updateAlertsBadge();

    } catch (error) {
        console.error('Load alerts error:', error);
        document.getElementById('alertsHistory').innerHTML =
            '<div class="no-data">Lỗi khi tải cảnh báo</div>';
    }
}

function getAlertIcon(severity) {
    switch(severity) {
        case 'critical': return '🔥';
        case 'warning': return '⚠️';
        case 'success': return '✅';
        default: return 'ℹ️';
    }
}

// ================== ALERTS BADGE FUNCTIONS ==================
async function updateAlertsBadge() {
    try {
        // Lấy tổng số cảnh báo
        const response = await fetch('/api/alerts/count');
        const data = await response.json();

        const badge = document.getElementById('alertsBadge');
        const tabBtn = document.getElementById('alertsTabBtn');

        if (data.total_alerts > 0) {
            // Hiển thị badge
            badge.style.display = 'inline-block';
            badge.textContent = data.total_alerts > 99 ? '99+' : data.total_alerts;

            // Đổi màu theo loại cảnh báo nghiêm trọng nhất
            if (data.critical_count > 0) {
                badge.style.background = '#e53e3e';
                badge.classList.add('badge-pulse');
                tabBtn.innerHTML = '🔴 Cảnh báo <span id="alertsBadge" class="badge">' + badge.textContent + '</span>';
            } else if (data.warning_count > 0) {
                badge.style.background = '#d69e2e';
                badge.classList.remove('badge-pulse');
                tabBtn.innerHTML = '⚠️ Cảnh báo <span id="alertsBadge" class="badge">' + badge.textContent + '</span>';
            } else {
                badge.style.background = '#4299e1';
                badge.classList.remove('badge-pulse');
                tabBtn.innerHTML = '🚨 Cảnh báo <span id="alertsBadge" class="badge">' + badge.textContent + '</span>';
            }

            // Cập nhật title để hiển thị chi tiết
            tabBtn.title = `Có ${data.total_alerts} cảnh báo\n- Khẩn cấp: ${data.critical_count}\n- Cảnh báo: ${data.warning_count}\n- Thông tin: ${data.info_count}`;
        } else {
            badge.style.display = 'none';
            tabBtn.innerHTML = '🚨 Cảnh báo';
            tabBtn.title = 'Không có cảnh báo';
        }

    } catch (error) {
        console.error('Update badge error:', error);
        // Fallback: lấy từ history và đếm
        try {
            const response = await fetch('/api/alerts/history?limit=50');
            const alerts = await response.json();

            const badge = document.getElementById('alertsBadge');
            if (alerts.length > 0) {
                badge.style.display = 'inline-block';
                badge.textContent = alerts.length > 99 ? '99+' : alerts.length;
                badge.style.background = '#4299e1';
            } else {
                badge.style.display = 'none';
            }
        } catch (fallbackError) {
            console.error('Fallback badge error:', fallbackError);
        }
    }
}

async function clearAlerts() {
    if (!confirm('Bạn có chắc muốn xóa TẤT CẢ lịch sử cảnh báo? Hành động này không thể hoàn tác.')) {
        return;
    }

    try {
        const response = await fetch('/api/alerts/clear', {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.status === 'success') {
            showToast(`✅ Đã xóa ${result.deleted_count} cảnh báo`, 'success');
            loadAlertsHistory(); // Tải lại danh sách
            updateAlertsBadge(); // Cập nhật badge
        } else {
            showToast(`❌ ${result.message}`, 'error');
        }

    } catch (error) {
        console.error('Clear alerts error:', error);
        showToast('❌ Lỗi khi xóa cảnh báo', 'error');
    }
}

// ================== TOAST NOTIFICATION ==================
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastIcon = toast.querySelector('.toast-icon');
    const toastTitle = toast.querySelector('.toast-title');
    const toastMessage = toast.querySelector('.toast-message');

    toastMessage.textContent = message;
    toast.className = 'toast';
    toast.classList.add(type);

    if (type === 'success') {
        toastIcon.textContent = '✅';
        toastTitle.textContent = 'Thành công';
    } else if (type === 'error') {
        toastIcon.textContent = '❌';
        toastTitle.textContent = 'Lỗi';
    } else {
        toastIcon.textContent = '💡';
        toastTitle.textContent = 'Thông báo';
    }

    toast.classList.add('show');

    setTimeout(() => {
        hideToast();
    }, 5000);
}

function hideToast() {
    const toast = document.getElementById('toast');
    toast.classList.remove('show');
}

// ================== CHART FUNCTIONS ==================
function changeChartType(type, evt) {
    currentChartType = type;
    document.querySelectorAll('#history .chart-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    if (evt && evt.currentTarget) evt.currentTarget.classList.add('active');
    loadHistoryChart();
}

function changeDailyChartType(type, evt) {
    currentDailyChartType = type;
    document.querySelectorAll('#daily .chart-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    if (evt && evt.currentTarget) evt.currentTarget.classList.add('active');
    loadDailyChart();
}

function loadHistoryChart() {
    const timeRange = document.getElementById('timeRange').value;

    fetch(`/api/history-chart?hours=${timeRange}`)
        .then(response => response.json())
        .then(data => {
            if (data.labels.length === 0) {
                showNoDataMessage('historyChart', 'Không có dữ liệu để hiển thị');
                return;
            }
            createTimeSeriesChart(data);
        })
        .catch(error => {
            console.error('Error loading chart:', error);
            showNoDataMessage('historyChart', 'Lỗi khi tải dữ liệu');
        });
}

function createTimeSeriesChart(data) {
    const ctx = document.getElementById('historyChart').getContext('2d');

    if (historyChart) {
        historyChart.destroy();
    }

    const chartConfig = getChartConfig(currentChartType, data);

    historyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: chartConfig.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: chartConfig.title,
                    font: { size: 16 }
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Thời gian'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: chartConfig.yAxisLabel
                    },
                    beginAtZero: true
                }
            }
        }
    });
}

function getChartConfig(type, data) {
    const configs = {
        power: {
            title: 'Biểu đồ Công suất theo thời gian',
            yAxisLabel: 'Công suất (W)',
            datasets: [{
                label: 'Công suất',
                data: data.power,
                borderColor: '#ff6384',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        voltage: {
            title: 'Biểu đồ Điện áp theo thời gian',
            yAxisLabel: 'Điện áp (V)',
            datasets: [{
                label: 'Điện áp',
                data: data.voltage,
                borderColor: '#36a2eb',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        current: {
            title: 'Biểu đồ Dòng điện theo thời gian',
            yAxisLabel: 'Dòng điện (A)',
            datasets: [{
                label: 'Dòng điện',
                data: data.current,
                borderColor: '#ffcd56',
                backgroundColor: 'rgba(255, 205, 86, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        efficiency: {
            title: 'Biểu đồ Hiệu suất theo thời gian',
            yAxisLabel: 'Hiệu suất (%)',
            datasets: [{
                label: 'Hiệu suất',
                data: data.efficiency,
                borderColor: '#4bc0c0',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        battery_voltage: {
            title: 'Biểu đồ Điện áp Pin theo thời gian',
            yAxisLabel: 'Điện áp Pin (V)',
            datasets: [{
                label: 'Điện áp Pin',
                data: data.battery_voltage,
                borderColor: '#9f7aea',
                backgroundColor: 'rgba(159, 122, 234, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        battery_soc: {
            title: 'Biểu đồ % Dung lượng Pin theo thời gian',
            yAxisLabel: 'Dung lượng Pin (%)',
            datasets: [{
                label: '% Pin',
                data: data.battery_soc,
                borderColor: '#38a169',
                backgroundColor: 'rgba(56, 161, 105, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        }
    };

    return configs[type] || configs.power;
}

// Daily chart functions
function loadAvailableDates() {
    fetch('/api/available-dates')
        .then(response => response.json())
        .then(dates => {
            const dateSelect = document.getElementById('dateSelect');
            dateSelect.innerHTML = '<option value="">Chọn ngày...</option>';

            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = formatDateDisplay(date);
                dateSelect.appendChild(option);
            });

            const today = new Date().toISOString().split('T')[0];
            const todayOption = dateSelect.querySelector(`option[value="${today}"]`);
            if (todayOption) {
                todayOption.selected = true;
                loadDailyChart();
            }
        });
}

function formatDateDisplay(dateStr) {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
        return `Hôm nay (${dateStr})`;
    } else if (date.toDateString() === yesterday.toDateString()) {
        return `Hôm qua (${dateStr})`;
    } else {
        return dateStr;
    }
}

function loadDailyChart() {
    const dateSelect = document.getElementById('dateSelect');
    const selectedDate = dateSelect.value;

    if (!selectedDate) {
        showNoDataMessage('dailyChart', 'Vui lòng chọn ngày');
        return;
    }

    fetch(`/api/daily-chart?date=${selectedDate}`)
        .then(response => response.json())
        .then(data => {
            if (data.labels.length === 0) {
                showNoDataMessage('dailyChart', `Không có dữ liệu cho ngày ${selectedDate}`);
                return;
            }
            createDailyChart(data, selectedDate);
        })
        .catch(error => {
            console.error('Error loading daily chart:', error);
            showNoDataMessage('dailyChart', 'Lỗi khi tải dữ liệu');
        });
}

function createDailyChart(data, selectedDate) {
    const ctx = document.getElementById('dailyChart').getContext('2d');

    if (dailyChart) {
        dailyChart.destroy();
    }

    const chartConfig = getDailyChartConfig(currentDailyChartType, data, selectedDate);

    dailyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: chartConfig.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: chartConfig.title,
                    font: { size: 16 }
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Thời gian trong ngày'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: chartConfig.yAxisLabel
                    },
                    beginAtZero: true
                }
            }
        }
    });
}

function getDailyChartConfig(type, data, date) {
    const configs = {
        power: {
            title: `Biểu đồ Công suất - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Công suất (W)',
            datasets: [{
                label: 'Công suất',
                data: data.power,
                borderColor: '#ff6384',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        voltage: {
            title: `Biểu đồ Điện áp - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Điện áp (V)',
            datasets: [{
                label: 'Điện áp',
                data: data.voltage,
                borderColor: '#36a2eb',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        current: {
            title: `Biểu đồ Dòng điện - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Dòng điện (A)',
            datasets: [{
                label: 'Dòng điện',
                data: data.current,
                borderColor: '#ffcd56',
                backgroundColor: 'rgba(255, 205, 86, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        efficiency: {
            title: `Biểu đồ Hiệu suất - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Hiệu suất (%)',
            datasets: [{
                label: 'Hiệu suất',
                data: data.efficiency,
                borderColor: '#4bc0c0',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        battery_voltage: {
            title: `Biểu đồ Điện áp Pin - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Điện áp Pin (V)',
            datasets: [{
                label: 'Điện áp Pin',
                data: data.battery_voltage,
                borderColor: '#9f7aea',
                backgroundColor: 'rgba(159, 122, 234, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        battery_soc: {
            title: `Biểu đồ % Dung lượng Pin - ${formatDateDisplay(date)}`,
            yAxisLabel: 'Dung lượng Pin (%)',
            datasets: [{
                label: '% Pin',
                data: data.battery_soc,
                borderColor: '#38a169',
                backgroundColor: 'rgba(56, 161, 105, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        }
    };

    return configs[type] || configs.power;
}

function showNoDataMessage(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');

    if (canvasId === 'historyChart' && historyChart) {
        historyChart.destroy();
    } else if (canvasId === 'dailyChart' && dailyChart) {
        dailyChart.destroy();
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = '16px Arial';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText(message, canvas.width/2, canvas.height/2);
}

function loadReports() {
    fetch('/api/report/daily')
        .then(response => response.json())
        .then(data => {
            let html = `
                <div class="report-item">
                    <h3>📊 Hôm nay - ${data.date}</h3>
                    <p><strong>Công suất trung bình:</strong> ${data.avg_power.toFixed(1)} W</p>
                    <p><strong>Tổng năng lượng:</strong> ${data.total_energy.toFixed(2)} Wh</p>
                    <p><strong>Hiệu suất trung bình:</strong> ${data.avg_efficiency.toFixed(1)}%</p>
                    <p><strong>Pin trung bình:</strong> ${data.avg_battery_soc ? data.avg_battery_soc.toFixed(1) : '0'}%</p>
                    <p><strong>Số lượng dữ liệu:</strong> ${data.data_points}</p>
                </div>
            `;
            document.getElementById('reportsData').innerHTML = html;
        });
}

// Auto-check PICO status
setInterval(() => {
    if (Date.now() - lastPicoUpdate > 15000) {
        updatePicoStatus(false);
    }
}, 5000);

// Load initial data
document.addEventListener('DOMContentLoaded', function() {
    updateSlider('azimuth');
    updateSlider('elevation');
    loadReports();
    loadAvailableDates();
    loadWeatherData();
    loadAlertsHistory();

    // Cập nhật badge lần đầu
    updateAlertsBadge();

    // Auto-refresh weather every 5 minutes
    setInterval(loadWeatherData, 300000);

    // Auto-refresh alerts every 30 seconds
    setInterval(() => {
        if (document.getElementById('alerts').classList.contains('active')) {
            loadAlertsHistory();
        }
    }, 30000);

    // Auto-update badge every 60 seconds
    setInterval(updateAlertsBadge, 60000);
});
