"""Language detection utilities for document parsing."""

import re
from typing import Literal

LanguageType = Literal["zh", "en", "mixed"]


def detect_language(text: str) -> LanguageType:
    """
    Detect the primary language of a text segment.
    
    Args:
        text: The text to analyze.
        
    Returns:
        "zh" for Chinese, "en" for English, "mixed" for mixed content.
    """
    if not text or not text.strip():
        return "en"
    
    # Count Chinese characters (CJK Unified Ideographs range)
    chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
    chinese_chars = len(chinese_pattern.findall(text))
    
    # Count English letters
    english_pattern = re.compile(r'[a-zA-Z]')
    english_chars = len(english_pattern.findall(text))
    
    total_chars = chinese_chars + english_chars
    
    if total_chars == 0:
        return "en"
    
    chinese_ratio = chinese_chars / total_chars
    english_ratio = english_chars / total_chars
    
    # Thresholds for language classification
    if chinese_ratio > 0.7:
        return "zh"
    elif english_ratio > 0.7:
        return "en"
    else:
        return "mixed"


def segment_by_language(text: str) -> list[tuple[str, LanguageType]]:
    """
    Segment text by language boundaries.
    
    Args:
        text: The text to segment.
        
    Returns:
        List of (text_segment, language) tuples.
    """
    if not text:
        return []
    
    segments = []
    current_segment = ""
    current_lang = None
    
    # Pattern to match Chinese character sequences or non-Chinese sequences
    pattern = re.compile(r'([\u4e00-\u9fff\u3400-\u4dbf]+|[^\u4e00-\u9fff\u3400-\u4dbf]+)')
    
    for match in pattern.finditer(text):
        chunk = match.group()
        chunk_lang = detect_language(chunk)
        
        if current_lang is None:
            current_lang = chunk_lang
            current_segment = chunk
        elif chunk_lang == current_lang or chunk_lang == "mixed":
            current_segment += chunk
        else:
            if current_segment.strip():
                segments.append((current_segment, current_lang))
            current_segment = chunk
            current_lang = chunk_lang
    
    if current_segment.strip():
        segments.append((current_segment, current_lang))
    
    return segments
