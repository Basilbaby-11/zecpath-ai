"""Transparent, deterministic baseline classifier. No training data required."""
import re
from typing import List

PATTERNS = {
    'skills': [r'\b(?:python|java|javascript|typescript|sql|pytorch|tensorflow|fastapi|react|docker|aws|machine learning|ml|nlp|ai|programming|coding|skills?|technolog(?:y|ies)|frameworks?)\b'],
    'experience': [r'\b(?:experience|internship|intern|worked|working|developed|built|projects?|years?|months?|fresher|previous role)\b'],
    'availability': [r'\b(?:join|joining|available|availability|notice period|immediately|immediate|next week|next month|start date|after \d+ (?:days?|weeks?|months?))\b'],
    'salary_expectation': [r'\b(?:salary|compensation|ctc|lpa|lakhs?|expected pay|expect|per month|per year|monthly|annually|inr|₹|rs\.?|usd|\$|aud)\b'],
}

QUESTION_HINTS = {
    'skills': r'\b(?:skills?|technolog(?:y|ies)|stack|tools?|languages?|frameworks?)\b',
    'experience': r'\b(?:experience|internship|worked|projects?|background|years?)\b',
    'availability': r'\b(?:join|joining|available|availability|notice|start)\b',
    'salary_expectation': r'\b(?:salary|compensation|ctc|pay|lpa|expectation)\b',
}

class IntentClassifier:
    def classify(self, answer: str) -> List[str]:
        text = answer.lower()
        matches = [intent for intent, patterns in PATTERNS.items() if any(re.search(p, text, re.I) for p in patterns)]
        return matches or ['unknown']

    def expected_intents(self, question: str) -> List[str]:
        return [name for name, regex in QUESTION_HINTS.items() if re.search(regex, question, re.I)]
