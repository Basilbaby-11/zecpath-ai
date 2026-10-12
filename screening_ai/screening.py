
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_candidate_profile(profile: dict) -> bool:
    """Check whether basic candidate profile fields are present."""
    required_fields = ("candidate_id", "resume_text")
    valid = all(profile.get(field) for field in required_fields)

    logger.info("Candidate profile validation completed")
    return valid
