
import json
from pathlib import Path

from parsers.jd_parser import (
    parse_job_description,
    validate_against_schema,
)


def test_jd_parser_output_matches_schema():
    sample_jd = """
    AI Engineer - Fresher

    Job Summary:
    We are looking for an entry-level AI Engineer to build machine learning applications.

    Responsibilities:
    - Develop machine learning models.
    - Build Python applications.
    - Collaborate with the engineering team.

    Requirements:
    - Required: Python and machine learning.
    - Preferred: TensorFlow and Docker.
    - Bachelor's degree in Computer Science.
    - 0 to 1 years of experience.
    - Full-time position.
    - Remote work.
    """

    result = parse_job_description(
        raw_text=sample_jd,
        file_name="sample_jd.txt",
        document_id="test-document-001",
        job_id="test-job-001",
    )

    schema_path = Path(__file__).resolve().parents[1] / "job_description_schema.json"
    validate_against_schema(result, str(schema_path))

    assert result["title"] == "Artificial Intelligence Engineer - Fresher"
    assert result["job_id"] == "test-job-001"
    assert isinstance(result["skills"], list)
    assert result["experience_requirements"]["minimum_months"] == 0

    output_path = Path(__file__).resolve().parents[1] / "data" / "sample_parsed_jd.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    skills_by_name = {
        skill["name"]: skill["requirement_type"]
        for skill in result["skills"]
    }

    assert skills_by_name["python"] == "required"
    assert skills_by_name["machine learning"] == "required"
    assert skills_by_name["tensorflow"] == "preferred"
    assert skills_by_name["docker"] == "preferred"

        # Education should not become mandatory just because
    # another requirement elsewhere uses the word "Required".
    assert result["education_requirements"][0]["mandatory"] is False

    # Explicitly mandatory education should be detected.
    mandatory_education = parse_job_description(
        "AI Engineer\nBachelor's degree required."
    )
    assert mandatory_education["education_requirements"][0]["mandatory"] is True


def test_skill_synonyms_are_normalized():
    result = parse_job_description(
        raw_text=(
            "Machine Learning Engineer\n"
            "Must have ML and Python programming."
        ),
        file_name="synonym_test.txt",
    )

    skill_names = [skill["name"] for skill in result["skills"]]

    assert "machine learning" in skill_names
    assert "python" in skill_names
    assert skill_names.count("machine learning") == 1
    assert skill_names.count("python") == 1

def test_role_variations_are_normalized():
    from parsers.jd_parser import normalize_role_name

    assert normalize_role_name("ML Engineer") == "Machine Learning Engineer"
    assert normalize_role_name("NLP Engineer") == "Natural Language Processing Engineer"
    assert normalize_role_name("AI Engineer - Fresher") == "Artificial Intelligence Engineer - Fresher"

def test_generate_additional_jd_samples():
    import json
    from pathlib import Path
    from parsers.jd_parser import parse_job_description, validate_against_schema

    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "data" / "parsed_job_descriptions"
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = project_root / "job_description_schema.json"

    samples = [
        {
            "filename": "data_analyst_jd.json",
            "job_id": "sample-data-analyst-001",
            "document_id": "sample-data-analyst-document",
            "text": """
Data Analyst

Job Summary:
We are looking for a Data Analyst to analyze business data and prepare reports.

Responsibilities:
- Analyze datasets using SQL and Python.
- Build dashboards and communicate findings.

Requirements:
- Required: SQL and Python.
- Preferred: Tableau.
- Bachelor's degree in Statistics or Computer Science.
- 1 to 2 years of experience.
- Full-time position.
- Hybrid work.
""",
        },
        {
            "filename": "ml_engineer_jd.json",
            "job_id": "sample-ml-engineer-001",
            "document_id": "sample-ml-engineer-document",
            "text": """
ML Engineer

Job Summary:
We are looking for an ML Engineer to develop machine learning models.

Responsibilities:
- Train and evaluate machine learning models.
- Build Python-based ML pipelines.

Requirements:
- Required: Python and machine learning.
- Preferred: TensorFlow and Docker.
- Master's degree in Computer Science preferred.
- 2 to 3 years of experience.
- Full-time position.
- Remote work.
""",
        },
    ]

    for sample in samples:
        parsed = parse_job_description(
            raw_text=sample["text"],
            file_name=sample["filename"].replace("_jd.json", ".txt"),
            document_id=sample["document_id"],
            job_id=sample["job_id"],
        )

        validate_against_schema(parsed, str(schema_path))

        output_path = output_dir / sample["filename"]
        output_path.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    assert (output_dir / "data_analyst_jd.json").exists()
    assert (output_dir / "ml_engineer_jd.json").exists()

def test_tableau_is_extracted_as_preferred_skill():
    result = parse_job_description(
        raw_text=(
            "Data Analyst\n"
            "Preferred: SQL, Python, and Tableau."
        ),
        file_name="tableau_test.txt",
    )

    skills_by_name = {
        skill["name"]: skill["requirement_type"]
        for skill in result["skills"]
    }

    assert skills_by_name["sql"] == "preferred"
    assert skills_by_name["python"] == "preferred"
    assert skills_by_name["tableau"] == "preferred"
