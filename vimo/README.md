# Machine Monitor — Enterprise Desktop Application

Real-time machine monitoring desktop app built with **Python + PyQt5**.
Designed for MPU6050 accelerometer/gyroscope sensors.

---

## Features

- **Dashboard** — Live overview: stat cards, machine status, real-time charts, live data table
- **Activity** — Alert feed, gyro/accel magnitude charts, event counter
- **Log & Statistics** — Filterable system log, sensor stats per machine
- **Settings** — Server connection (WebSocket / HTTP / MQTT / Serial), alert thresholds, machine management
- Menu bar: File | View | Configure | Tools
- Collapsible sidebar
- Dark gray enterprise theme
- OOP architecture — fully separated modules

---

## Project Structure

```
machine_monitor/
├── main.py                     # Entry point
├── requirements.txt
├── core/
│   ├── app_config.py           # Theme, colors, layout constants
│   ├── data_manager.py         # Real-time data ingestion & distribution
│   └── models.py               # SensorReading, MachineState data models
└── ui/
    ├── main_window.py          # Main window shell
    ├── widgets/
    │   ├── sidebar.py          # Collapsible sidebar navigation
    │   ├── topbar.py           # Top bar with status indicators
    │   ├── cards.py            # StatCard, MachineStatusCard, SectionHeader
    │   ├── charts.py           # RealtimeChart (matplotlib), MultiAxisChart
    │   └── data_table.py       # Live data table
    └── pages/
        ├── dashboard.py        # Dashboard overview page
        ├── activity.py         # Activity & alert feed page
        ├── log_statistic.py    # Log viewer & statistics page
        └── settings.py         # Settings & configuration page
```

---

## Installation

```bash
# 1. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py
```

---

## Connecting to Your Server

By default the app runs in **simulation mode** — it generates realistic MPU6050
data for demonstration. To connect to your real server:

1. Go to **Settings** page
2. Enter your server Host, Port, Protocol, and Endpoint
3. Click **Connect**

### Ingesting Data Programmatically

In `core/data_manager.py`, the `DataManager` class exposes:

```python
# Ingest raw JSON string (from WebSocket/HTTP/MQTT)
data_manager.ingest_raw("MAC-001", '{"accelX":848,"accelY":-124,...}')

# Ingest parsed dict
data_manager.ingest_dict("MAC-001", {"accelX": 848, "accelY": -124, ...})
```

Replace the `_simulate_data()` method with your actual WebSocket client
(e.g. `websockets`, `socketio`) or HTTP polling loop.

### Example WebSocket Integration

```python
import asyncio
import websockets

async def ws_listener(data_manager, url):
    async with websockets.connect(url) as ws:
        async for message in ws:
            data_manager.ingest_raw("MAC-001", message)
```

---

## Sensor Data Format

Expected JSON from MPU6050:

```json
{"accelX": 848, "accelY": -124, "accelZ": -15720,
 "gyroX": -682, "gyroY": -412, "gyroZ": -362}
```

---

## Requirements

- Python 3.9+
- PyQt5 5.15+
- matplotlib 3.5+
- numpy 1.21+

---

## Production Build

For production setup and packaging steps, see [`PRODUCTION.md`](PRODUCTION.md).

