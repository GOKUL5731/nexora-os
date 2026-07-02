"""
Sentiment Analysis Module
Analyzes sentiment of voice commands and text inputs
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Sentiment(Enum):
    """Sentiment categories"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    URGENT = "urgent"
    QUESTION = "question"


@dataclass(slots=True)
class SentimentResult:
    """Result of sentiment analysis"""
    sentiment: Sentiment
    confidence: float
    keywords: list[str]
    emotion: Optional[str] = None


class SentimentAnalyzer:
    """Simple rule-based sentiment analyzer"""
    
    # Positive keywords
    POSITIVE_KEYWORDS = {
        "good", "great", "excellent", "awesome", "happy", "love", "like",
        "thanks", "thank you", "please", "appreciate", "wonderful", "amazing",
        "perfect", "best", "nice", "cool", "yes", "yeah", "sure", "okay",
        "நன்றி", "நலம்", "மகிழ்ச்சி", "வாழ்த்துகள்"
    }
    
    # Negative keywords
    NEGATIVE_KEYWORDS = {
        "bad", "terrible", "awful", "hate", "dislike", "angry", "frustrated",
        "sad", "upset", "annoyed", "no", "not", "never", "stop", "cancel",
        "error", "fail", "wrong", "broken", "stupid", "dumb", "hate",
        "வேதனை", "கோபம்", "பயம்", "சோகம்"
    }
    
    # Urgent keywords
    URGENT_KEYWORDS = {
        "urgent", "emergency", "immediately", "now", "asap", "hurry", "quick",
        "fast", "help", "save", "critical", "important", "priority",
        "அவசரம்", "உடனடி", "உதவி"
    }
    
    # Question indicators
    QUESTION_INDICATORS = {
        "?", "what", "how", "why", "when", "where", "who", "which", "can",
        "could", "would", "should", "is", "are", "do", "does", "did",
        "என்ன", "எப்படி", "ஏன்", "எங்கே", "யார்"
    }
    
    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of text
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentResult with sentiment and confidence
        """
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_count = sum(1 for word in words if word in self.POSITIVE_KEYWORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_KEYWORDS)
        urgent_count = sum(1 for word in words if word in self.URGENT_KEYWORDS)
        question_count = sum(1 for word in words if word in self.QUESTION_INDICATORS)
        
        # Check for question mark
        if "?" in text:
            question_count += 1
        
        # Determine sentiment
        sentiment = Sentiment.NEUTRAL
        confidence = 0.5
        keywords = []
        
        if urgent_count > 0:
            sentiment = Sentiment.URGENT
            confidence = min(0.6 + (urgent_count * 0.1), 1.0)
            keywords = [word for word in words if word in self.URGENT_KEYWORDS]
        elif question_count > 0:
            sentiment = Sentiment.QUESTION
            confidence = min(0.6 + (question_count * 0.1), 1.0)
            keywords = [word for word in words if word in self.QUESTION_INDICATORS]
        elif positive_count > negative_count:
            sentiment = Sentiment.POSITIVE
            confidence = min(0.5 + ((positive_count - negative_count) * 0.1), 1.0)
            keywords = [word for word in words if word in self.POSITIVE_KEYWORDS]
        elif negative_count > positive_count:
            sentiment = Sentiment.NEGATIVE
            confidence = min(0.5 + ((negative_count - positive_count) * 0.1), 1.0)
            keywords = [word for word in words if word in self.NEGATIVE_KEYWORDS]
        
        # Determine emotion
        emotion = self._determine_emotion(sentiment, keywords)
        
        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            keywords=keywords,
            emotion=emotion
        )
    
    def _determine_emotion(self, sentiment: Sentiment, keywords: list[str]) -> Optional[str]:
        """Determine specific emotion based on sentiment and keywords"""
        if sentiment == Sentiment.POSITIVE:
            if any(word in ["happy", "love", "great", "awesome"] for word in keywords):
                return "joy"
            elif any(word in ["thanks", "thank you", "appreciate"] for word in keywords):
                return "gratitude"
            return "satisfaction"
        
        elif sentiment == Sentiment.NEGATIVE:
            if any(word in ["angry", "frustrated", "annoyed"] for word in keywords):
                return "anger"
            elif any(word in ["sad", "upset"] for word in keywords):
                return "sadness"
            elif any(word in ["error", "fail", "broken"] for word in keywords):
                return "frustration"
            return "disappointment"
        
        elif sentiment == Sentiment.URGENT:
            return "urgency"
        
        elif sentiment == Sentiment.QUESTION:
            return "curiosity"
        
        return None
    
    def get_response_tone(self, sentiment: Sentiment) -> str:
        """
        Get appropriate response tone based on sentiment
        
        Args:
            sentiment: Detected sentiment
            
        Returns:
            Suggested response tone
        """
        tone_map = {
            Sentiment.POSITIVE: "friendly and enthusiastic",
            Sentiment.NEGATIVE: "empathetic and supportive",
            Sentiment.NEUTRAL: "professional and direct",
            Sentiment.URGENT: "calm and efficient",
            Sentiment.QUESTION: "informative and helpful"
        }
        return tone_map.get(sentiment, "neutral")


# Global sentiment analyzer instance
global_sentiment_analyzer = SentimentAnalyzer()


def analyze_sentiment(text: str) -> SentimentResult:
    """Analyze sentiment using the global analyzer"""
    return global_sentiment_analyzer.analyze(text)
