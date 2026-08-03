# IoTrix Cloud for Home Assistant

An unofficial, cloud-push Home Assistant integration for IoTrix energy devices. It talks directly from Home Assistant to the IoTrix HTTPS/WebSocket API, so it does **not** require an Android emulator, ESP32, WireGuard, or another relay device.

## Design

- One Home Assistant config entry represents one IoTrix account.
- The integration calls the IoTrix owned-device endpoint and creates one HA Device for every cloud-returned `device_id`.
- Device names, counts, IDs, and account topology are never hardcoded.
- A driver capability registry maps a returned `driver` to known fields. Unknown drivers remain visible as devices without guessed entities.
- The device list refreshes periodically. Realtime values arrive over one account WebSocket connection.
- Hybrid inverter, BMS, and the virtual **IoTrix D18 Guard** are separate HA devices.

Currently understood drivers:

| IoTrix driver | HA role | Control |
| --- | --- | --- |
| `mppt_makeskyblue_v1` | Hybrid inverter | D18 only |
| `bms_jikong_v2` | BMS | Read-only |

The integration intentionally omits BMS cell-by-cell voltages and high-churn clock/work-time fields. Fast electrical values are coalesced to about 5 seconds; temperature, difference, capacity, and energy values use longer intervals to reduce Recorder churn.

## Install with HACS

Until this repository is accepted into the HACS default store:

1. Open HACS → Integrations → three-dot menu → **Custom repositories**.
2. Add `https://github.com/chinawrj/iotrix-ha` as an **Integration**.
3. Install **IoTrix Cloud** and restart Home Assistant.
4. Open Settings → Devices & services → Add integration → **IoTrix Cloud**.
5. Enter the IoTrix API host and account access token.

The access token is stored in Home Assistant's config entry storage. It is never included in diagnostics or logs. Do not paste tokens into GitHub issues.

## D18 and battery guard

The compatible inverter exposes **D18 Maximum Grid Current** as a writable `number` entity. No other IoTrix command is implemented.

The HA-side D18 Guard:

- trips from the selected **BMS current** (negative means discharge), never inverter battery current;
- reduces D18 once using load-path power and preserves calculated PV headroom;
- defaults to **disabled** to prevent double control with an existing ESP32 automation;
- enforces a default 10-minute minimum write interval;
- restores only after the BMS current is safe and actual grid-path demand stays below the limited D18 ceiling for 10 minutes;
- verifies a restore for 10 minutes and can roll back immediately on renewed sustained overcurrent;
- records requested → accepted → confirmed/failed events, sequence numbers, status, and JSON details in HA.

All thresholds, observation windows, restore behavior, and the enable switch are configurable on the virtual D18 Guard device. A manual D18 change releases any guard-owned limit and records a `manual_confirmed` event.

## Home Assistant Energy dashboard

- BMS State of Charge uses `%`, battery device class, and measurement state class.
- Charge/discharge daily energy and estimated cumulative cycle energy use the energy device class.
- **Charge Energy Total Placeholder** is a deliberate constant `0 kWh` total-increasing sensor for installations that need a valid charged-energy statistic before a true cumulative source is available.
- Estimated cycle energy is `cycle_capacity (Ah) × 51.2 V ÷ 1000`. It is an estimate, while the original cycle capacity remains available in Ah.

## Safety

This is an unofficial integration. Confirm limits against your inverter/BMS installation. Keep Guard disabled while another controller can write D18. Control is allow-listed to D18, requires cloud command acceptance plus realtime readback, and never embeds account credentials or device IDs in source code.

## Development

```bash
python -m pip install -e .[test]
ruff check .
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the test and release policy.
