# Zecpath AI — Job Description Parsing System

## 1. Objective

The Job Description Parsing System converts raw job description text into a structured JSON object that can be consumed by other Zecpath AI modules.

The output follows the existing `job_description_schema.json` schema.

## 2. Implementation

- Language: Python 3.11
- Parser module: `parsers/jd_parser.py`
- Output schema: `job_description_schema.json`
- Test module: `tests/test_jd_parser.py`
- Sample output: `data/sample_parsed_jd.json`

## 3. Main Responsibilities

The parser performs the following tasks:

1. Normalizes whitespace and line breaks.
2. Extracts a job title from the description.
3. Identifies employment type and workplace type using keywords.
4. Extracts explicitly labelled location information.
5. Identifies likely job responsibilities from section headings.
6. Detects supported skills and maps known aliases to canonical names.
7. Classifies detected skills as required or preferred using text rules.
8. Extracts basic experience ranges and experience levels.
9. Identifies common education qualifications.
10. Extracts basic certification, language, compensation, and application information when recognized.
11. Produces structured JSON and supports validation against the existing JSON Schema.

## 4. Skill Normalization

The parser maintains a dictionary of known skill aliases.

Examples:

| Input variation | Canonical skill |
|---|---|
| ML | machine learning |
| Python programming | python |
| sklearn | scikit-learn |
| NodeJS | node.js |
| K8s | kubernetes |

Only configured aliases are recognized. This is rule-based normalization, not semantic understanding of every possible synonym.

## 5. Output Structure

The parser returns fields defined by the existing job description schema, including:

- Job identification and source document metadata
- Job title, department, employment type, and workplace type
- Location and summary
- Responsibilities and skills
- Experience and education requirements
- Certifications and language requirements
- Compensation and application instructions
- Parser metadata and review status

Each skill record contains its name, category, requirement type, minimum proficiency, minimum years, evidence, and confidence.

## 6. Validation and Testing

Run the JD parser tests:

```powershell
python -m pytest tests/test_jd_parser.py -v
```

Run the complete project test suite:

```powershell
python -m pytest -v
```

Latest recorded full-suite result: 16 tests passed.

The tests cover existing ATS functionality, resume extraction, schema validation of a sample JD, and skill synonym normalization.

## 7. Current Limitations

- Extraction relies on regular expressions, keywords, and predefined aliases.
- Unrecognized skills and unusual job description formats may be missed.
- Required/preferred classification can be incorrect when the wording is ambiguous.
- Experience, compensation, education, and location extraction cover only selected patterns.
- Field-level confidence values are heuristic and are not statistically calibrated.
- The parser does not currently use an LLM or a trained information extraction model.
- Human review is recommended before using parsed information for hiring decisions.

## 8. Future Improvements

1. Expand skill aliases and role variations.
2. Add tests for diverse job description formats.
3. Improve experience, education, salary, and location extraction.
4. Add field-level confidence and review rules based on evidence.
5. Evaluate extraction accuracy against manually labelled job descriptions.
6. Integrate the parser with the Zecpath backend through a documented API.
