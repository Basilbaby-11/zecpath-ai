from .intent_classifier import IntentClassifier

class OffTopicDetector:
    def __init__(self):
        self.classifier = IntentClassifier()

    def is_off_topic(self, question: str, answer_intents: list[str]) -> bool:
        expected = self.classifier.expected_intents(question)
        # Unknown question -> abstain rather than flag an answer.
        return bool(expected) and not bool(set(expected) & set(answer_intents))
