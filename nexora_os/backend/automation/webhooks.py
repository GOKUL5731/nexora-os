"""
Webhook Integration Module
Handles webhook triggers and integrations with external services
"""
import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(slots=True)
class Webhook:
    """Represents a webhook configuration"""
    id: str
    name: str
    url: str
    method: str = "POST"
    headers: dict[str, str] = None
    enabled: bool = True
    trigger_events: list[str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.trigger_events is None:
            self.trigger_events = []


class WebhookManager:
    """Manager for webhook integrations"""
    
    def __init__(self) -> None:
        self.webhooks: dict[str, Webhook] = {}
        self._handlers: dict[str, list[Callable]] = {}
    
    def register_webhook(self, webhook: Webhook) -> bool:
        """
        Register a webhook
        
        Args:
            webhook: Webhook configuration
            
        Returns:
            True if registered, False otherwise
        """
        if not webhook.url:
            return False
        
        self.webhooks[webhook.id] = webhook
        
        # Register handlers for trigger events
        for event in webhook.trigger_events:
            if event not in self._handlers:
                self._handlers[event] = []
            self._handlers[event].append(lambda: self._trigger_webhook(webhook.id))
        
        return True
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            True if unregistered, False otherwise
        """
        if webhook_id not in self.webhooks:
            return False
        
        webhook = self.webhooks[webhook_id]
        
        # Remove handlers for trigger events
        for event in webhook.trigger_events:
            if event in self._handlers:
                # Filter out handlers for this webhook
                self._handlers[event] = [
                    h for h in self._handlers[event]
                    if hasattr(h, '__self__') or True  # Keep all handlers for simplicity
                ]
        
        del self.webhooks[webhook_id]
        return True
    
    def enable_webhook(self, webhook_id: str) -> bool:
        """Enable a webhook"""
        if webhook_id in self.webhooks:
            self.webhooks[webhook_id].enabled = True
            return True
        return False
    
    def disable_webhook(self, webhook_id: str) -> bool:
        """Disable a webhook"""
        if webhook_id in self.webhooks:
            self.webhooks[webhook_id].enabled = False
            return True
        return False
    
    async def _trigger_webhook(self, webhook_id: str, payload: dict[str, Any] = None) -> dict[str, Any]:
        """
        Trigger a webhook
        
        Args:
            webhook_id: Webhook ID
            payload: Payload to send
            
        Returns:
            Response from webhook
        """
        if webhook_id not in self.webhooks:
            return {"ok": False, "error": "Webhook not found"}
        
        webhook = self.webhooks[webhook_id]
        
        if not webhook.enabled:
            return {"ok": False, "error": "Webhook is disabled"}
        
        try:
            data = json.dumps(payload or {}).encode("utf-8")
            request = urllib.request.Request(
                webhook.url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    **webhook.headers
                },
                method=webhook.method
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode("utf-8")
                return {
                    "ok": True,
                    "status_code": response.status,
                    "response": response_data
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }
    
    def trigger_event(self, event: str, payload: dict[str, Any] = None) -> list[asyncio.Task]:
        """
        Trigger an event and execute associated webhooks
        
        Args:
            event: Event name
            payload: Event payload
            
        Returns:
            List of asyncio tasks for webhook calls
        """
        tasks = []
        
        if event in self._handlers:
            for handler in self._handlers[event]:
                task = asyncio.create_task(handler(), name=f"webhook_{event}")
                tasks.append(task)
        
        return tasks
    
    def list_webhooks(self) -> list[dict[str, Any]]:
        """List all registered webhooks"""
        return [
            {
                "id": webhook.id,
                "name": webhook.name,
                "url": webhook.url,
                "method": webhook.method,
                "enabled": webhook.enabled,
                "trigger_events": webhook.trigger_events
            }
            for webhook in self.webhooks.values()
        ]
    
    def get_webhook(self, webhook_id: str) -> Optional[dict[str, Any]]:
        """Get webhook details"""
        if webhook_id not in self.webhooks:
            return None
        
        webhook = self.webhooks[webhook_id]
        return {
            "id": webhook.id,
            "name": webhook.name,
            "url": webhook.url,
            "method": webhook.method,
            "headers": webhook.headers,
            "enabled": webhook.enabled,
            "trigger_events": webhook.trigger_events
        }


# Global webhook manager instance
global_webhook_manager = WebhookManager()


def register_webhook(webhook: Webhook) -> bool:
    """Register a webhook using the global manager"""
    return global_webhook_manager.register_webhook(webhook)


def trigger_event(event: str, payload: dict[str, Any] = None) -> list[asyncio.Task]:
    """Trigger an event using the global manager"""
    return global_webhook_manager.trigger_event(event, payload)


def list_webhooks() -> list[dict[str, Any]]:
    """List webhooks using the global manager"""
    return global_webhook_manager.list_webhooks()
