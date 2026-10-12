from utils.logger import get_logger

logger = get_logger(__name__)

def calculate_match_score(
    required_skills: list[str],
    candidate_skills: list[str],
) -> float:
    """Calculate a simple skill-overlap score from 0 to 100."""
    if not required_skills:
        return 0.0

    required = {skill.strip().casefold() for skill in required_skills}
    candidate = {skill.strip().casefold() for skill in candidate_skills}

    score = len(required & candidate) / len(required) * 100
    logger.info("Calculated ATS skill-overlap score")
    return round(score, 2)
