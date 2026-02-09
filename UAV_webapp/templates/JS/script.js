<script>
        let currentFlightId = null;
        let currentUAVId = null;
        let telemetryInterval = null;
        const API_BASE = '/api';
        const token = localStorage.getItem('auth_token'); // Предполагаем, что токен сохранен

        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            loadAvailableUAVs();
            setupJoystick();

            document.getElementById('speed-slider').addEventListener('input', function(e) {
                document.getElementById('speed-value').textContent = e.target.value;
            });
        });

        async function loadAvailableUAVs() {
            try {
                // Здесь должен быть запрос к API для получения доступных БПЛА
                // Для примера используем заглушку
                const uavs = [
                    {id: '550e8400-e29b-41d4-a716-446655440000', name: 'DJI Phantom 4'},
                    {id: '123e4567-e89b-12d3-a456-426614174000', name: 'Custom Drone X1'}
                ];

                const select = document.getElementById('uav-select');
                select.innerHTML = '';
                uavs.forEach(uav => {
                    const option = document.createElement('option');
                    option.value = uav.id;
                    option.textContent = uav.name;
                    select.appendChild(option);
                });

            } catch (error) {
                console.error('Ошибка загрузки БПЛА:', error);
            }
        }

        async function connectToUAV() {
            const uavId = document.getElementById('uav-select').value;
            if (!uavId) {
                alert('Выберите БПЛА');
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/uav/${uavId}/connect/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    currentFlightId = data.flight_id;
                    currentUAVId = uavId;

                    updateStatus('connected', `Подключено к ${data.uav_name}`);
                    document.getElementById('connected-controls').style.display = 'block';
                    document.getElementById('disconnect-btn').disabled = false;

                    // Запускаем обновление телеметрии
                    startTelemetryPolling();
                } else {
                    alert(`Ошибка подключения: ${data.error}`);
                }

            } catch (error) {
                console.error('Ошибка подключения:', error);
                alert('Ошибка сети при подключении');
            }
        }

        async function disconnectFromUAV() {
            if (!currentFlightId) return;

            try {
                const response = await fetch(`${API_BASE}/flight/${currentFlightId}/disconnect/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok) {
                    updateStatus('disconnected', 'Отключено от БПЛА');
                    document.getElementById('connected-controls').style.display = 'none';
                    document.getElementById('disconnect-btn').disabled = true;

                    // Останавливаем опрос телеметрии
                    stopTelemetryPolling();

                    currentFlightId = null;
                    currentUAVId = null;
                } else {
                    alert(`Ошибка отключения: ${data.error}`);
                }

            } catch (error) {
                console.error('Ошибка отключения:', error);
            }
        }

        async function sendCommand(commandType) {
            if (!currentFlightId) {
                alert('Сначала подключитесь к БПЛА');
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/flight/${currentFlightId}/command/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        command_type: commandType
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    console.log('Команда отправлена:', data);
                    // Можно показать уведомление
                } else {
                    alert(`Ошибка команды: ${data.error}`);
                }

            } catch (error) {
                console.error('Ошибка отправки команды:', error);
                alert('Ошибка сети при отправке команды');
            }
        }

        function setupJoystick() {
            const joystick = document.getElementById('joystick');
            const knob = document.getElementById('joystick-knob');
            let isDragging = false;

            joystick.addEventListener('mousedown', startDrag);
            joystick.addEventListener('touchstart', startDrag);

            document.addEventListener('mousemove', drag);
            document.addEventListener('touchmove', drag);
            document.addEventListener('mouseup', stopDrag);
            document.addEventListener('touchend', stopDrag);

            function startDrag(e) {
                if (!currentFlightId) return;
                isDragging = true;
                e.preventDefault();
            }

            function drag(e) {
                if (!isDragging || !currentFlightId) return;

                const rect = joystick.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;

                let clientX, clientY;

                if (e.type.includes('touch')) {
                    clientX = e.touches[0].clientX;
                    clientY = e.touches[0].clientY;
                } else {
                    clientX = e.clientX;
                    clientY = e.clientY;
                }

                // Вычисляем относительные координаты
                let relX = (clientX - centerX) / (rect.width / 2);
                let relY = (clientY - centerY) / (rect.height / 2);

                // Ограничиваем радиус
                const distance = Math.sqrt(relX * relX + relY * relY);
                if (distance > 1) {
                    relX /= distance;
                    relY /= distance;
                }

                // Двигаем ручку
                knob.style.left = `${50 + relX * 50}%`;
                knob.style.top = `${50 + relY * 50}%`;

                // Определяем направление
                const direction = getDirection(relX, relY);
                const speed = parseFloat(document.getElementById('speed-slider').value);

                // Отправляем команду движения
                sendManualControl(direction, speed);
            }

            function stopDrag() {
                if (!isDragging) return;
                isDragging = false;

                // Возвращаем ручку в центр
                knob.style.left = '50%';
                knob.style.top = '50%';

                // Отправляем команду остановки
                if (currentFlightId) {
                    sendCommand('stop');
                }
            }

            function getDirection(x, y) {
                // Определяем направление по углу
                const angle = Math.atan2(y, x) * 180 / Math.PI;

                if (angle >= -22.5 && angle < 22.5) return 'right';
                if (angle >= 22.5 && angle < 67.5) return 'up_right';
                if (angle >= 67.5 && angle < 112.5) return 'up';
                if (angle >= 112.5 && angle < 157.5) return 'up_left';
                if (angle >= 157.5 || angle < -157.5) return 'left';
                if (angle >= -157.5 && angle < -112.5) return 'down_left';
                if (angle >= -112.5 && angle < -67.5) return 'down';
                if (angle >= -67.5 && angle < -22.5) return 'down_right';

                return 'stop';
            }
        }

        async function sendManualControl(direction, speed) {
            if (!currentFlightId) return;

            try {
                await fetch(`${API_BASE}/flight/${currentFlightId}/manual/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        direction: direction,
                        speed: speed,
                        duration: 0.1
                    })
                });

                // Не ждем ответ - отправляем асинхронно для плавности
            } catch (error) {
                console.error('Ошибка ручного управления:', error);
            }
        }

        function startTelemetryPolling() {
            if (telemetryInterval) clearInterval(telemetryInterval);

            telemetryInterval = setInterval(async () => {
                if (!currentUAVId) return;

                try {
                    const response = await fetch(`${API_BASE}/uav/${currentUAVId}/telemetry/`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });

                    if (response.ok) {
                        const data = await response.json();
                        updateTelemetryDisplay(data);
                    }
                } catch (error) {
                    console.error('Ошибка получения телеметрии:', error);
                }
            }, 1000); // Опрос каждую секунду
        }

        function stopTelemetryPolling() {
            if (telemetryInterval) {
                clearInterval(telemetryInterval);
                telemetryInterval = null;
            }
        }

        function updateTelemetryDisplay(telemetry) {
            const telemetryDiv = document.getElementById('telemetry-data');
            telemetryDiv.innerHTML = `
                <p><strong>БПЛА:</strong> ${telemetry.uav_name}</p>
                <p><strong>Статус:</strong> ${telemetry.status}</p>
                <p><strong>Батарея:</strong> ${telemetry.battery}%</p>
                <p><strong>Высота:</strong> ${telemetry.altitude.toFixed(1)} м</p>
                <p><strong>Скорость:</strong> ${telemetry.speed.toFixed(1)} км/ч</p>
                <p><strong>Координаты:</strong> ${telemetry.latitude.toFixed(6)}, ${telemetry.longitude.toFixed(6)}</p>
                <p><strong>Время:</strong> ${new Date(telemetry.timestamp).toLocaleTimeString()}</p>
            `;
        }

        function updateStatus(status, message) {
            const statusDiv = document.getElementById('status');
            statusDiv.className = `status ${status}`;
            statusDiv.textContent = message;
        }
    </script>