from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect
from PySide6.QtGui import QColor

class Animations:
    @staticmethod
    def add_glow(widget, color="#00d4ff", radius=20, offset=0):
        glow = QGraphicsDropShadowEffect(widget)
        glow.setBlurRadius(radius)
        glow.setColor(QColor(color))
        glow.setOffset(offset, offset)
        widget.setGraphicsEffect(glow)
        return glow

    @staticmethod
    def add_opacity(widget, opacity=1.0):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(opacity)
        widget.setGraphicsEffect(effect)
        return effect

    @staticmethod
    def fade_in(widget, duration=800, max_opacity=1.0):
        effect = Animations.add_opacity(widget, 0.0)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(max_opacity)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        # Store reference so it doesn't get garbage collected immediately
        if not hasattr(widget, '_animations'):
            widget._animations = []
        widget._animations.append(anim)
        return anim

    @staticmethod
    def pulse_glow(glow_effect, min_radius=10, max_radius=30, duration=1500):
        anim = QPropertyAnimation(glow_effect, b"blurRadius")
        anim.setDuration(duration)
        anim.setStartValue(min_radius)
        anim.setEndValue(max_radius)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(-1) # Infinite loop
        
        # We simulate a yoyo effect by going back and forth
        anim.setKeyValueAt(0.5, max_radius)
        anim.setKeyValueAt(1.0, min_radius)
        
        anim.start(QPropertyAnimation.KeepWhenStopped)
        if not hasattr(glow_effect.parent(), '_animations'):
            glow_effect.parent()._animations = []
        glow_effect.parent()._animations.append(anim)
        return anim
