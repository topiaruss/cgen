"""
Translation service for multilingual campaign generation.
Supports multiple translation providers with fallback options.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class TranslationProvider(ABC):
    """Abstract base class for translation providers"""
    
    @abstractmethod
    def translate(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """Translate text from source to target language"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured and available"""
        pass


class MockTranslationProvider(TranslationProvider):
    """Mock translation provider for development/testing"""
    
    def translate(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """Return mock translated text"""
        if target_language == source_language:
            return text
        
        # Simple mock translations for common languages
        mock_translations = {
            'es': f"[ES] {text}",
            'fr': f"[FR] {text}",
            'de': f"[DE] {text}",
            'it': f"[IT] {text}",
            'pt': f"[PT] {text}",
            'ja': f"[JA] {text}",
            'ko': f"[KO] {text}",
            'zh': f"[ZH] {text}",
            'ar': f"[AR] {text}",
        }
        
        return mock_translations.get(target_language, f"[{target_language.upper()}] {text}")
    
    def is_available(self) -> bool:
        return True


class OpenAITranslationProvider(TranslationProvider):
    """OpenAI GPT-based translation provider"""
    
    def __init__(self):
        self.client = None
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            try:
                import openai
                self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                logger.warning("OpenAI package not installed")
    
    def translate(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """Translate using OpenAI GPT"""
        if not self.client:
            raise RuntimeError("OpenAI client not available")
        
        if target_language == source_language:
            return text
        
        # Language code to full name mapping
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
        }
        
        source_lang_name = language_names.get(source_language, source_language)
        target_lang_name = language_names.get(target_language, target_language)
        
        prompt = f"""Translate the following {source_lang_name} text to {target_lang_name}. 
        Maintain the tone and marketing intent. Return only the translation:

        {text}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"OpenAI translation failed: {e}")
            raise RuntimeError(f"Translation failed: {e}")
    
    def is_available(self) -> bool:
        return self.client is not None


class GoogleTranslationProvider(TranslationProvider):
    """Google Translate API provider (placeholder for future implementation)"""
    
    def translate(self, text: str, target_language: str, source_language: str = 'en') -> str:
        raise NotImplementedError("Google Translate provider not implemented yet")
    
    def is_available(self) -> bool:
        return False


class TranslationService:
    """Main translation service with provider fallback"""
    
    def __init__(self):
        self.providers = [
            OpenAITranslationProvider(),
            MockTranslationProvider(),  # Always available as fallback
        ]
        
        # Filter to available providers
        self.available_providers = [p for p in self.providers if p.is_available()]
        
        if not self.available_providers:
            logger.warning("No translation providers available")
    
    def translate_text(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """
        Translate text using the first available provider
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'es', 'fr')
            source_language: Source language code (default: 'en')
            
        Returns:
            Translated text
            
        Raises:
            RuntimeError: If no providers are available or all fail
        """
        if not self.available_providers:
            raise RuntimeError("No translation providers available")
        
        if target_language == source_language:
            return text
        
        last_error = None
        
        for provider in self.available_providers:
            try:
                result = provider.translate(text, target_language, source_language)
                logger.info(f"Translation successful using {provider.__class__.__name__}")
                return result
            
            except Exception as e:
                logger.warning(f"Translation failed with {provider.__class__.__name__}: {e}")
                last_error = e
                continue
        
        raise RuntimeError(f"All translation providers failed. Last error: {last_error}")
    
    def translate_campaign_content(self, content_dict: Dict[str, str], target_language: str, source_language: str = 'en') -> Dict[str, str]:
        """
        Translate multiple campaign content fields
        
        Args:
            content_dict: Dictionary of field_name -> text to translate
            target_language: Target language code
            source_language: Source language code
            
        Returns:
            Dictionary of field_name -> translated_text
        """
        translated = {}
        
        for field_name, text in content_dict.items():
            try:
                translated[field_name] = self.translate_text(text, target_language, source_language)
            except Exception as e:
                logger.error(f"Failed to translate field '{field_name}': {e}")
                translated[field_name] = text  # Fallback to original text
        
        return translated
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return [provider.__class__.__name__ for provider in self.available_providers]


# Global translation service instance
translation_service = TranslationService()
