# Zecpath AI --- Job Description Parsing System

## 1. Purpose

The Job Description (JD) Parsing System converts raw job description
text into a structured, machine-readable JSON object for use by Zecpath
AI hiring workflows.

The parser uses the existing `job_description_schema.json` as its output
contract. It is a rule-based Python implementation; it does not
currently use an LLM or a trained extraction model.

## 2. Project Files

  -----------------------------------------------------------------------------------------
  File or folder                                        Purpose
  ----------------------------------------------------- -----------------------------------
  `parsers/jd_parser.py`                                JD text normalization, extraction,
                                                        skill matching, role normalization,
                                                        and schema validation helper

  `job_description_schema.json`                         Authoritative JSON Schema for
                                                        parsed JD objects

  `tests/test_jd_parser.py`                             Tests for schema compatibility,
                                                        skill synonyms, role variations,
                                                        and Tableau extraction

  `data/sample_parsed_jd.json`                          AI Engineer fresher sample output

  `data/parsed_job_descriptions/data_analyst_jd.json`   Data Analyst sample output

  `data/parsed_job_descriptions/ml_engineer_jd.json`    Machine Learning Engineer sample
                                                        output
  -----------------------------------------------------------------------------------------

The sample job descriptions are synthetic test examples, not real
employer listings.

## 3. Processing Overview

1.  **Input:** Receive raw JD text and optional document/job
    identifiers.
2.  **Text normalization:** Normalize line endings, repeated spaces,
    tabs, and excessive blank lines.
3.  **Title extraction:** Use a labelled title/position/role when
    available; otherwise use the first non-empty line.
4.  **Role normalization:** Map configured role variations to canonical
    names, such as `AI Engineer` to `Artificial Intelligence Engineer`,
    `ML Engineer` to `Machine Learning Engineer`, and `NLP Engineer` to
    `Natural Language Processing Engineer`.
5.  **Skill extraction:** Search configured skill aliases and produce
    skill records with canonical names, categories, requirement types,
    evidence, and heuristic confidence values.
6.  **Requirement extraction:** Apply regular-expression and keyword
    rules to identify responsibilities, experience, education,
    employment type, workplace type, and selected other fields.
7.  **Structured output:** Return a dictionary matching the expected JD
    object shape.
8.  **Validation:** `validate_against_schema()` can validate the output
    against `job_description_schema.json` when the `jsonschema` package
    is installed.

## 4. Extracted Output

The output includes these top-level fields, as defined by the existing
schema:

-   `schema_version`, `job_id`, and `source_document`
-   `title`, `department`, `employment_type`, `workplace_type`, and
    `location`
-   `summary` and `responsibilities`
-   `skills`
-   `experience_requirements` and `education_requirements`
-   `certification_requirements` and `language_requirements`
-   `compensation` and `application_instructions`
-   `metadata`

Each skill record includes `name`, `category`, `requirement_type`,
`minimum_proficiency`, `minimum_years`, `evidence`, and `confidence`.

## 5. Skill and Role Normalization

The parser uses dictionaries of known aliases. Current examples include:

  Input variation        Normalized value
  ---------------------- ----------------------------------------
  `ML`                   `machine learning`
  `Python programming`   `python`
  `sklearn`              `scikit-learn`
  `NodeJS`               `node.js`
  `K8s`                  `kubernetes`
  `AI Engineer`          `Artificial Intelligence Engineer`
  `ML Engineer`          `Machine Learning Engineer`
  `NLP Engineer`         `Natural Language Processing Engineer`

Only configured aliases are recognized. New variations must be added to
the dictionaries to be supported.

## 6. Running Tests

Activate the project's virtual environment, then run the JD parser
tests:

``` powershell
python -m pytest tests/test_jd_parser.py -v
```

Run all project tests, including ATS and resume-extraction tests:

``` powershell
python -m pytest -v
```

At the latest reported run, the full project suite completed with **19
tests passed**. Re-run the tests before submission if the code changes.

## 7. Sample Outputs

The sample JSON files are stored at:

-   `data/sample_parsed_jd.json`
-   `data/parsed_job_descriptions/data_analyst_jd.json`
-   `data/parsed_job_descriptions/ml_engineer_jd.json`

The Data Analyst sample includes SQL and Python as required skills and
Tableau as a preferred skill. The Machine Learning Engineer sample
includes Python and machine learning as required skills, with TensorFlow
and Docker as preferred skills.

## 8. Current Limitations

-   Extraction relies on regular expressions, keyword checks, and
    predefined aliases; it is not semantic AI extraction.
-   Unlisted skills and role variations can be missed.
-   Required/preferred classification is heuristic and may be inaccurate
    when requirements are expressed ambiguously or across multiple
    sentences.
-   Experience parsing supports selected numeric patterns. For example,
    the current classifier may label a 2--3 year role as `other`.
-   Education extraction identifies common qualification types, but
    field-of-study extraction and mandatory/preferred interpretation are
    limited.
-   Location, compensation, certifications, languages, and application
    instructions are extracted only for selected text patterns.
-   Confidence values are heuristic and are not statistically
    calibrated.
-   Human review is recommended before using parsed information in
    hiring decisions.

## 9. Future Improvements

1.  Expand skill aliases and role-variation mappings.
2.  Add broader test cases for experience, education, salary, location,
    and requirement wording.
3.  Improve extraction of education fields of study and
    mandatory/preferred status.
4.  Add evaluation against manually labelled job descriptions to measure
    precision and recall.
5.  Consider an NLP/LLM-assisted extraction layer with schema validation
    and human review.
6.  Integrate the parser with the Zecpath backend through a documented
    API.

## 10. Review Status

The current parser is a tested prototype. Passing the project tests
demonstrates that the tested cases pass; it does not establish accuracy
for every job description format. Parsed outputs should remain in
`pending_review` until reviewed through the intended workflow.
