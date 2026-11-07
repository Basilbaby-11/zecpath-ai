"""Recruiter-configurable candidate eligibility decision engine."""
from eligibility.eligibility_engine import evaluate_eligibility, load_eligibility_rules

__all__ = ["evaluate_eligibility", "load_eligibility_rules"]
