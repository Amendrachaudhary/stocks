"""
interfaces.py - Abstract Base Classes for Signal Transmission & Transport Decoupling
=====================================================================================
Defines the architectural contract for dispatching trading signals and alerts.
Adheres to the Dependency Inversion and Interface Segregation Principles.
"""

from abc import ABC, abstractmethod


class SignalSender(ABC):
    """
    Abstract Base Class defining the contract for message and signal dispatchers.
    Decouples core trading analytics from third-party transport layers (Discord, Telegram, etc.).
    """

    @abstractmethod
    def send_signal(self, message: str) -> bool:
        """
        Dispatches a signal message to the configured downstream transport.

        Args:
            message: Formatted text or serialized signal to transmit.

        Returns:
            bool: True if transmission succeeded, False otherwise.
        """
        pass
