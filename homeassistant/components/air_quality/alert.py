"""Alert notification for air quality integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final, Optional

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER: Final = logging.getLogger(__name__)

@dataclass
class AlertContext:
    """Alert context info."""
    target_entity_id: str
    pollutant: str
    current_value: float
    threshold: float
    triggered_at: datetime
    rule_type: str

# 1. AlertRule - ThresholdAlertRule/CompositeAlertRule
class AlertRule(ABC):
    """Abstract base class for alert rules."""
    
    @abstractmethod
    def evaluate(self, entity_state: State) -> Optional[AlertContext]:
        """Evaluate if alert condition is met."""
        
    @abstractmethod
    def get_alert_message(self, context: AlertContext) -> str:
        """Get the alert message for this rule."""

class ThresholdAlertRule(AlertRule):
    """Threshold-based alert rule."""
    
    def __init__(self, pollutant: str, threshold: float):
        self._pollutant = pollutant
        self._threshold = threshold
    
    def evaluate(self, entity_state: State) -> Optional[AlertContext]:
        """Check if pollutant exceeds threshold."""
        value = entity_state.attributes.get(self._pollutant)
        if value is not None and value > self._threshold:
            return AlertContext(
                target_entity_id=entity_state.entity_id,
                pollutant=self._pollutant,
                current_value=value,
                threshold=self._threshold,
                triggered_at=datetime.now(),
                rule_type="threshold"
            )
        return None
    
    def get_alert_message(self, context: AlertContext) -> str:
        return f"{context.pollutant} level exceeded threshold: {context.current_value} > {context.threshold}"

# TODO: class CompositeAlertRule
# class CompositeAlertRule(AlertRule):
#     """Alert rules based on composite conditions."""

# 2. NotificationHandler
class NotificationHandler(ABC):
    """Abstract base class for notification handlers."""
    
    @abstractmethod
    async def send_alert(self, message: str):
        """Send alert notification."""
    
    @property
    @abstractmethod
    def handler_type(self) -> str:
        """Handler type identifier."""

# TODO class EmailNotificationHandler
# class EmailNotificationHandler(NotificationHandler):
#     """Email notification handler."""

# 3. AlertMonitor
class AlertMonitor:
    """Monitor air quality entities for alert conditions."""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._target_entity_id: Optional[str] = None
        self._rules: list[AlertRule] = []
        self._notification_handlers: list[NotificationHandler] = []
        self._cooldown_periods: dict[str, datetime] = {}
        self._monitoring_active = False
        self._remove_timer = None

    def set_target_entity(self, entity_id: str):
        """Set target entity id"""
        self._target_entity_id = entity_id
    
    async def start_monitoring(self):
        """Start alert monitoring."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._setup_monitoring_timer()
        _LOGGER.info("Air quality alert monitoring started")
    
    def stop_monitoring(self):
        """Stop alert monitoring."""
        if not self._monitoring_active:
            return
            
        self._monitoring_active = False
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None
        _LOGGER.info("Air quality alert monitoring stopped")

    @property
    def is_monitoring_active(self) -> bool:
        return self._monitoring_active
    
    def _setup_monitoring_timer(self):
        """Set monitoring loop timer to check every 5 minutes"""
        if self._remove_timer:
            self._remove_timer()
        
        self._remove_timer = async_track_time_interval(
            self.hass, self._check_alerts, timedelta(minutes=5)
        )
    
    async def _check_alerts(self, now=None):
        """Check all entities for alert conditions."""
        if not self._monitoring_active or not self._target_entity_id:
            return
        
        entity_state = self.hass.states.get(self._target_entity_id)
        if not entity_state:
            _LOGGER.warning(f"Entity does not exist: {self._target_entity_id}")
            return
        
        for rule in self._rules:            
            context = rule.evaluate(entity_state)
            if context and self._should_trigger_alert(context):
                await self._trigger_alert(context, rule)
                        
    def _should_trigger_alert(self, context: AlertContext) -> bool:
        "Check if an alert should be triggered (to prevent duplicate alerts)."
        cooldown_key = f"{context.target_entity_id}_{context.pollutant}_{context.rule_type}"
        last_trigger = self._cooldown_periods.get(cooldown_key)
        
        if last_trigger and (datetime.now() - last_trigger) < timedelta(minutes=60):
            return False
        
        self._cooldown_periods[cooldown_key] = datetime.now()
        return True
    
    async def _trigger_alert(self, context: AlertContext, rule: AlertRule):
        """Trigger alert notification."""
        message = rule.get_alert_message(context)
        
        # send to all notification handlers
        for handler in self._notification_handlers:
            try:
                await handler.send_alert(message)
            except Exception as e:
                _LOGGER.error("Failed to send alert via %s: %s", 
                            handler.handler_type, e)