import re
from typing import Any, Dict, List

FIELDS = {'skills': 'skills', 'experience': 'experience', 'availability': 'availability', 'salary_expectation': 'salary_expectation'}
FOLLOW_UPS = {
    'skills': 'Which specific technical skills have you used?',
    'experience': 'How many months or years of experience do you have?',
    'availability': 'When exactly would you be able to join?',
    'salary_expectation': 'What salary amount, currency, and pay period do you expect?',
}

class AnswerValidator:
    def validate(self, answer: str, expected: List[str], entities: Dict[str, Any], off_topic: bool) -> Dict[str, Any]:
        text = answer.strip()
        vague = bool(re.fullmatch(r'(?:yes|no|maybe|ok(?:ay)?|fine|not sure|i don\'t know|depends|anything|whatever|some|many|a lot|n/?a)[.! ]*', text, re.I)) or len(text.split()) < 2
        missing = []
        for intent in expected:
            field = FIELDS[intent]
            value = entities.get(field)
            if not value:
                missing.append(field)
            elif intent == 'salary_expectation' and (value.get('currency') is None or value.get('period') is None):
                missing.append(field)
        return {
            'is_vague': vague,
            'is_complete': not vague and not off_topic and not missing and bool(text),
            'missing_fields': missing,
            'follow_up_question': FOLLOW_UPS[missing[0]] if missing else ('Could you give a more specific answer to the question?' if vague or off_topic else None),
        }
