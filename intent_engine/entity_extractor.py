"""Conservative entity extraction: don't infer unspoken details."""
import re
from typing import Any, Dict

SKILLS = {'python': 'Python', 'java': 'Java', 'javascript': 'JavaScript', 'typescript': 'TypeScript', 'sql': 'SQL', 'pytorch': 'PyTorch', 'tensorflow': 'TensorFlow', 'fastapi': 'FastAPI', 'react': 'React', 'docker': 'Docker', 'aws': 'AWS', 'machine learning': 'Machine Learning', 'nlp': 'NLP'}

class EntityExtractor:
    def extract(self, answer: str) -> Dict[str, Any]:
        text = answer.lower()
        skills = [canonical for token, canonical in SKILLS.items() if re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', text)]
        # Avoid interpreting "I don't know Python" as a positive skill.
        skills = [s for s in skills if not re.search(r"\b(?:don't|do not|never|no)\s+(?:know|use|have experience (?:with|in))\s+" + re.escape(s.lower()) + r'\b', text)]
        experience = None
        match = re.search(r'\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*(years?|yrs?|months?|mos?)\b', text)
        number_words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
        if match:
            duration = float(number_words.get(match.group(1), match.group(1)))
            months = round(duration * 12 if match.group(2).startswith(('year', 'yr')) else duration)
            experience = {'duration_months': months, 'type': 'internship' if re.search(r'\bintern(?:ship)?\b', text) else 'unspecified'}
        elif re.search(r'\b(?:fresher|no (?:work |professional )?experience)\b', text):
            experience = {'duration_months': 0, 'type': 'fresher'}
        availability = None
        if re.search(r'\b(?:immediately|immediate|right away|as soon as possible)\b', text):
            availability = {'status': 'immediate'}
        elif (m := re.search(r'\b(?:in|after|within|notice period (?:of|is)?)\s*(\d+)\s*(days?|weeks?|months?)\b', text)):
            availability = {'status': 'relative', 'value': int(m.group(1)), 'unit': m.group(2).rstrip('s')}
        elif re.search(r'\bnext week\b', text):
            availability = {'status': 'relative', 'value': 1, 'unit': 'week'}
        elif re.search(r'\bnext month\b', text):
            availability = {'status': 'relative', 'value': 1, 'unit': 'month'}
        salary = None
        # Currency / salary context required to avoid mistaking experience durations for salary.
        pattern = r'(?:₹|\brs\.?\s*|\binr\s*|\baud\s*|\busd\s*|\$\s*|\b(?:salary|ctc|compensation|expect(?:ing)?|pay)\s*(?:is|of|around|about|approximately)?\s*)(\d[\d,]*(?:\.\d+)?)\s*(k|lpa|lakh(?:s)?|lac(?:s)?)?\b'
        m = re.search(pattern, text, re.I)
        if m:
            amount = float(m.group(1).replace(',', ''))
            unit = (m.group(2) or '').lower()
            if unit == 'k': amount *= 1000
            if unit in ('lpa', 'lakh', 'lakhs', 'lac', 'lacs'): amount *= 100000
            currency = 'INR' if re.search(r'₹|\brs\.?|\binr\b|\blpa\b|\blakhs?\b', text) else ('AUD' if re.search(r'\baud\b', text) else ('USD' if re.search(r'\busd\b|\$', text) else None))
            period = 'yearly' if unit == 'lpa' or re.search(r'\b(?:per year|annually|annual|yearly)\b', text) else ('monthly' if re.search(r'\b(?:per month|monthly)\b', text) else None)
            salary = {'amount': int(amount) if amount.is_integer() else amount, 'currency': currency, 'period': period}
        return {'skills': skills, 'experience': experience, 'availability': availability, 'salary_expectation': salary}
