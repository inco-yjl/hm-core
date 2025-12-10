class AirQualityCard extends HTMLElement {
  constructor() {
    super();
    this.handleAlertEvent = this.handleAlertEvent.bind(this);
    this._handleCardClick = this._handleCardClick.bind(this);
  }

  // Backend attribute keys to user-friendly display names
  static get DISPLAY_MAPPING() {
    return {
      air_quality_index: "AQI",
      carbon_dioxide: "CO₂",
      carbon_monoxide: "CO",
      nitrogen_oxide: "N₂O",
      nitrogen_monoxide: "NO",
      nitrogen_dioxide: "NO₂",
      ozone: "O₃",
      particulate_matter_0_1: "PM0.1",
      particulate_matter_10: "PM10",
      particulate_matter_2_5: "PM2.5",
      sulphur_dioxide: "SO₂",
    };
  }

  // Air Quality Category to MDI Icon Mapping
  static get CATEGORY_ICON_MAPPING() {
    return {
      Good: "mdi:check-circle-outline",
      Moderate: "mdi:alert-circle-outline",
      Unhealthy: "mdi:alert-box-outline",
      "Very Unhealthy": "mdi:alert-box-outline",
      Hazardous: "mdi:alert-box-outline",
      Unknown: "mdi:help-circle-outline",
    };
  }

  // Stores configuration and historical values
  config = {};
  prevValues = {};
  _cardInitialized = false; // Flag to ensure click listener is added only once
  _unsub = null; // Used for event subscription cleanup
  _hass = null;

  // List of pollutants currently marked as alert (updated by backend events)
  alertPollutants = new Set();

  // ---------------------- Lifecycle and Configuration ----------------------
  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this.config = config;
    this.prevValues = {};
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub(); // Unsubscribe function
      this._unsub = undefined;
    }
  }

  // ---------------------- Event and Data Handling ----------------------

  /**
   * Called when Home Assistant state updates
   */
  set hass(hass) {
    this._hass = hass;

    // Subscribe to the event bus on first set hass call
    if (!this._unsub && hass.connection) {
      // Subscribe to 'air_quality_alert' events via WebSocket connection
      this._unsub = hass.connection
        .subscribeEvents(this.handleAlertEvent, "air_quality_alert")
        .catch((err) =>
          console.error("Error subscribing to air_quality_alert:", err)
        );
    }

    // Re-render to display the latest state data
    this.render();
  }

  /**
   * Called when the backend 'air_quality_alert' event fires (Bound to 'this')
   */
  handleAlertEvent(event) {
    const { pollutant, entity_id } = event.data;

    // Ensure configuration is available and matches this entity
    if (!this.config || entity_id !== this.config.entity) {
      return;
    }

    // Add the pollutant to the alert set
    this.alertPollutants.add(pollutant);

    console.log("Alert Received for pollutant:", pollutant);
    // Force card redraw
    this.render();
  }

  /**
   * Handles card click event to open the More Info dialog
   */
  _handleCardClick(ev) {
    // Prevent click event from propagating further (e.g., if clicking on an inner button)
    ev.stopPropagation();

    if (!this.config || !this.config.entity) {
      return;
    }

    // Fire 'hass-more-info' event, which the Lovelace core will capture to open the dialog
    const event = new Event("hass-more-info", {
      bubbles: true, // Must bubble up to the Lovelace root
      composed: true,
    });

    // Attach the target entity ID to the event
    event.detail = { entityId: this.config.entity };

    // Dispatch the event
    this.dispatchEvent(event);
  }

  // ---------------------- Rendering Logic ----------------------

  /**
   * Draws the HTML structure and styles of the card
   */
  render() {
    const hass = this._hass;
    // Check if hass and config are valid before proceeding
    if (!hass || !this.config || !this.config.entity) return;

    const entity = hass.states[this.config.entity];
    if (!entity) return;

    // Add click listener only on first render
    if (!this._cardInitialized) {
      this.addEventListener("click", (e) => this._handleCardClick(e));
      this._cardInitialized = true;
    }

    const attrs = entity.attributes;
    let rows = "";

    // --- Main Display Logic ---
    console.log(attrs.air_quality_category_label);
    const category = attrs.air_quality_category_label || "Unknown";
    const iconName =
      AirQualityCard.CATEGORY_ICON_MAPPING[category] ||
      "mdi:help-circle-outline";
    const friendlyName = entity.attributes.friendly_name || entity.entity_id;

    // Determine icon color based on category
    let iconColor = "var(--label-badge-green)"; // Default: Green
    if (category === "Moderate") {
      iconColor = "var(--label-badge-yellow)"; // Yellow/Orange
    } else if (
      category === "Unhealthy" ||
      category === "Very Unhealthy" ||
      category === "Hazardous"
    ) {
      iconColor = "var(--label-badge-red)"; // Red
    } else if (category === "Unknown") {
      iconColor = "var(--state-icon-color)"; // Default gray
    }

    // --- Right-Side Attributes List Logic ---
    for (const [key, value] of Object.entries(attrs)) {
      // Exclude the category attribute itself
      if (key === "air_quality_category") continue;

      const prev = this.prevValues[key];
      let arrow = "=";
      if (prev !== undefined) {
        if (value > prev) arrow = "↑";
        else if (value < prev) arrow = "↓";
      }
      this.prevValues[key] = value;

      const displayName = AirQualityCard.DISPLAY_MAPPING[key] || key;
      // Check if the pollutant is in the alert set to determine warning style
      const warn = this.alertPollutants.has(key);

      if (value >= 0)
        rows += `
                                <div class="item ${warn ? "warn" : ""}">
                                    ${arrow} ${displayName}: ${value}
                                </div>
                                `;
    }

    // Render main structure
    this.innerHTML = `
            <ha-card header="${friendlyName}">
              <div class="wrapper">
                <div class="main">
                    <div class="category-icon" style="color: ${iconColor};">
                        <ha-icon icon="${iconName}"></ha-icon>
                    </div>
                </div>
                <div class="attrs">
                    ${rows}
                </div>
              </div>
            </ha-card>

            <style>
              ha-card {
                padding: 16px;
                cursor: pointer;
              }
              .wrapper {
                width: 100%;
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: var(--card-content-padding, 0 8px);
              }
              .main {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin-right: 16px;
              }
              .category-icon {
                /* Use MDI variable to set the icon size */
                --mdc-icon-size: 72px;
                line-height: 1;
                margin-bottom: 4px;
              }

              .attrs {
                display: flex;
                flex-direction: column;
                text-align: right;
                font-size: 14px;
                min-width: 140px;
              }
              .item {
                margin-bottom: 2px;
              }
              .warn {
                color: var(--label-badge-red, red);
                font-weight: bold;
              }
            </style>
        `;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("air-quality-card", AirQualityCard);
