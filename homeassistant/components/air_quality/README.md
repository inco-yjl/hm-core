---
title: Air quality
description: Instructions on how to add air quality sensors with Home Assistant
ha_release: 0.85
ha_domain: air_quality
ha_quality_scale: internal
ha_category: []
ha_codeowners:
  - '@home-assistant/core'
ha_integration_type: entity
---

The **Air quality** {% term integration %} allows other integrations to process information about air quality and pollution details. It is used by integrations that provide an `air_quality` sensor - you can find those under the `health` [integrations](/integrations/#health).

The platforms cover the following levels (if they are available):

- The particulate matter 0.1 (<= 0.1 μm) level.
- The particulate matter 2.5 (<= 2.5 μm) level.
- The particulate matter 10 (<= 10 μm) level.
- The Air Quality Index (AQI).
- The O3 (ozone) level.
- The CO (carbon monoxide) level.
- The CO2 (carbon dioxide) level.
- The SO2 (sulphur dioxide) level.
- The N2O (nitrogen oxide) level.
- The NO (nitrogen monoxide) level.
- The NO2 (nitrogen dioxide) level.

{% include integrations/building_block_integration.md %}

## The state of an air quality entity

The state of an air quality entity represents the concentration of particles in the air that are 2.5 microns or fewer in diameter. The state is a number. The number is followed by the unit of measurement (micrograms per cubic meter: "µg/m³"). For example, *PM2.5: 4 µg/m³*. In this example, the state is 4.

In addition, the entity can have the following states:

- **Unavailable**: The entity is currently unavailable.
- **Unknown**: The state is not yet known.

# Air Quality - Extension Attributes
To improve the readability of numeric air quality values, this integration provides a set of supplemental attributes. These attributes do not modify the entity state defined by the Air Quality platform. Instead, they offer human-friendly interpretations of the state and are intended for display purposes in the frontend.

The additional attributes include:
- **`air_quality_category`**
  A computed category derived from the air quality value
  (e.g., `good`, `moderate`, `unhealthy`).

- **`air_quality_category_label`**
  A localized label for the category, suitable for multilingual user interfaces
  (e.g., `Excellent`, `Good`, `Slightly Polluted`).

- **`air_quality_display`**
  A combined formatted string intended for UI display
  (e.g., `"50 (Good)"`).


# Air Quality - Alert Monitor

This feature extends the **Air Quality** integration by adding a flexible **Alert Monitoring System**. It allows users to define rules that trigger notifications when certain air-quality metrics exceed configured thresholds.

## ✨ Features

  * **Entity Monitoring:** Monitors `air_quality` entity in Home Assistant.
  * **Threshold Alerts:** Triggers alerts when pollutant levels exceed configured thresholds.
  * **Rule Flexibility:** Supports multiple alert rules.
  * **Multiple Channels:** Supports multiple notification channels/handlers.
  * **Timing Control:** Configurable check interval and cooldown period to prevent notification spam.
  * **Extensible Design:** Modular architecture allows for easy addition of custom rules and notification handlers.

## 🛠️ Installation and Setup

Alerts are configured in Home Assistant's `configuration.yaml`.

### 1\. Enable the `air_quality` Integration

First, ensure the core `air_quality` integration is enabled in your configuration.

**Example:**

```yaml
air_quality:
  - platform: demo # your air quality platform
```

### 2\. Add Alert Monitoring Configuration

The `alert_monitor` section is configured under the same `air_quality` entry.

**Example:**

```yaml
air_quality:
  - platform: demo
    alert_monitor:
      # --- Required ---
      target_entity: air_quality.demo_air_quality_test

      # --- Rules (at least one) ---
      rules:
        - type: threshold
          pollutant: particulate_matter_2_5
          threshold: 25

      # --- Notification Handlers (at least one) ---
      notifications:
        - type: hass_notify
          service_id: persistent_notification

      # --- Optional Testing Parameters ---
      # test_check_interval: 3    # How often to evaluate rules (seconds)
      # test_cooldown_time: 10    # Cooldown between repeated alerts (seconds)
```

**Note:** Monitoring will **only** start if the configuration is fully complete (a `target_entity`, at least one `rule`, and at least one `notification` handler).

## ⚙️ Configuration Details

### `target_entity`

The entity ID whose attributes should be monitored.

| Key | Description               | Example |
| :--- |:--------------------------| :--- |
| `target_entity` | The entity ID to monitor. | `air_quality.demo_air_quality_test` |

-----

### `rules` List

Defines the conditions that will trigger an alert.

#### 1\. `threshold` Rule

Triggers when a specific pollutant value exceeds a defined numeric threshold.

| Key | Meaning | Example Value |
| :--- | :--- | :--- |
| `type` | Must be `"threshold"` | `threshold` |
| `pollutant` | The name of the pollutant attribute to check. | `particulate_matter_2_5` |
| `threshold` | The numeric value that, when exceeded, triggers the alert. | `25` |

**Example:**

```yaml
rules:
  - type: threshold
    pollutant: particulate_matter_2_5
    threshold: 25
```

**Valid Pollutant Names Include:**

  * `particulate_matter_2_5`
  * `particulate_matter_10`
  * `air_quality_index`
  * `ozone`
  * `carbon_dioxide`
  * `carbon_monoxide`
  * `nitrogen_dioxide`
  * *... and others defined in the specific air quality integration.*

-----

### `notifications` List

Defines where the triggered alerts should be sent.

#### 1\. `hass_notify` Handler

Uses Home Assistant's built-in `notify.*` services.

```yaml
- type: hass_notify
  service_id: persistent_notification
```

This configuration will call the service `notify.persistent_notification`. You can replace `persistent_notification` with any other configured notification service.

#### 2\. `logging` Handler

Outputs the alert message to the Home Assistant log. Useful primarily for debugging.

```yaml
- type: logging
```

-----

### Optional Testing Parameters

These parameters override the default monitoring and cooldown settings.

| Key | Meaning | Default |
| :--- | :--- |:--------|
| `test_check_interval` | How often, in **seconds**, to evaluate the rules. | 5 min   |
| `test_cooldown_time` | The **seconds** cooldown period between repeated alerts for the same condition. | 60 min  |

**Example:**

```yaml
test_check_interval: 3
test_cooldown_time: 10
```

## 🧠 How Alerts Work

1.  **Periodic Check:** The `AlertMonitor` periodically reads the state of the `target_entity`.
2.  **Rule Evaluation:** Each configured rule evaluates whether its alert condition has been met.
3.  **Cooldown Logic:** If an alert is triggered, a cooldown timer is checked. If the timer is active, the alert is suppressed to prevent notification spam.
4.  **Notification Dispatch:** If the alert is triggered and not in cooldown, each registered `NotificationHandler` sends out the alert message.

## 🏗️ Architecture Overview

The system is designed with a clear separation of concerns, ensuring maintainability and scalability.

| Component                | Role | Description                                                                                                                                                              |
|:-------------------------| :--- |:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **AlertRule**            | **Condition Logic** | Abstract base class. Defines conditions for triggering an alert. `ThresholdAlertRule` is the initial implementation.                                                     |
| **NotificationHandler**  | **Delivery Method** | Abstract base class. Defines how an alert is delivered. `HassNotificationHandler` and `LoggingNotificationHandler` are current implementations.                          |
| **AlertMonitor**       | **Core Engine** | Tracks the entity state periodically, evaluates rules, applies cooldown, and dispatches notifications.                                                                   |
