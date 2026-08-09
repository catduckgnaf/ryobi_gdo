# Ryobi Garage Door Opener (GDO) Integration for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/catduckgnaf/ryobi_gdo?style=for-the-badge)](https://github.com/catduckgnaf/ryobi_gdo/releases)
[![License](https://img.shields.io/github/license/catduckgnaf/ryobi_gdo?style=for-the-badge)](LICENSE.md)

A Home Assistant custom component integration to control and monitor the **Ryobi Ultra-Quiet Garage Door Opener (GD200 / GD201 / GD125)** and its modular accessories via real-time WebSocket push updates and cloud API.

---

## ✨ Features

- 🚪 **Cover Entity**: Full open, close, opening, and closing states with real-time feedback.
- 💡 **Light Control**: Native light entity to control the overhead LED light.
- 🔋 **Battery Monitoring**: Battery charge level sensor for the backup battery module.
- 📶 **Wi-Fi Signal**: Diagnostic Wi-Fi RSSI strength sensor.
- 🛡️ **Safety & Motion Sensors**: Safety beam obstruction sensor, built-in motion detection, and vacation mode sensors.
- 🔌 **Modular Accessories**: Dynamic support for Ryobi plug-in modules (Inflator switch, Park Assist laser, Bluetooth Speaker & Mic, Fan).
- ⚡ **Real-Time Push**: Persistent WebSocket connection with automatic exponential backoff reconnection for instant state updates.
- ⚙️ **Modern Config Flow**: Easy setup via the Home Assistant UI with friendly opener names and unique ID protection.

---

## 📦 Installation

### Option 1: Via HACS (Recommended)

1. Open **HACS** in your Home Assistant dashboard.
2. Click the three dots in the top right corner and choose **Custom repositories**.
3. Paste `https://github.com/catduckgnaf/ryobi_gdo` and select Category **Integration**.
4. Click **Download**, then restart Home Assistant when prompted.

### Option 2: Manual Installation

1. Download the latest release `.zip` from [Releases](https://github.com/catduckgnaf/ryobi_gdo/releases).
2. Extract and copy the `custom_components/ryobi_gdo` directory into your Home Assistant `config/custom_components/` folder.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **Ryobi Garage Door Opener**.
3. Enter your Ryobi account username and password.
4. Select the Garage Door Opener you want to integrate from the dropdown.

---

## 🛠️ Supported Entities

| Platform | Entity | Description |
| :--- | :--- | :--- |
| `cover` | **Garage Door** | Open/close and state monitoring |
| `light` | **Light** | Overhead garage light on/off |
| `sensor` | **Battery** | Battery charge percentage (if backup charger installed) |
| `sensor` | **Wi-Fi Signal** | Signal strength (dBm) |
| `binary_sensor` | **Motion** | Built-in motion sensor detection |
| `binary_sensor` | **Safety Sensor** | Laser/safety beam obstruction status |
| `binary_sensor` | **Vacation Mode** | Vacation lockout switch state |
| `binary_sensor` | **Park Assist Laser** | Laser module status |
| `binary_sensor` | **Bluetooth Speaker** | Bluetooth speaker connection |
| `binary_sensor` | **Server Connection** | Cloud WebSocket link health |
| `switch` | **Inflator** | Air compressor module control |

---

## 🐞 Issues and Contributions

If you encounter any issues, please report them on the [GitHub Issue Tracker](https://github.com/catduckgnaf/ryobi_gdo/issues).
