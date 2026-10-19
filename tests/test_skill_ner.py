import json
from pathlib import Path

import pytest

from parsers.skill_ner import extract_skill_entities, load_skill_dictionary

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = ROOT / "data" / "skill_dictionary.json"

def entity_names(text):
    return {
        item["name"]
        for item in extract_skill_entities(
            text, dictionary_path=DICTIONARY
        )
    }


def names(text):
    return {item["name"] for item in extract_skill_entities(text, dictionary_path=DICTIONARY)}


def test_recognizes_canonical_skill_entities():
    result = extract_skill_entities("I used Python and TensorFlow to build an NLP project.", DICTIONARY)
    by_name = {item["name"]: item for item in result}
    assert {"Python", "TensorFlow", "Natural Language Processing"} <= set(by_name)
    assert by_name["Python"]["entity_label"] == "SKILL"
    assert by_name["Python"]["recognition_method"] == "spacy_phrase_match"
    assert by_name["Python"]["start_char"] >= 0


def test_normalizes_aliases():
    result = extract_skill_entities("Experience with sklearn, js and golang.", DICTIONARY)
    extracted = {item["name"] for item in result}
    assert "Scikit-learn" in extracted
    assert "JavaScript" in extracted
    assert "Go" in extracted


def test_expands_mern_stack():
    extracted = names("Built a MERN application.")
    assert {"MERN Stack", "MongoDB", "Express.js", "React", "Node.js"} <= extracted


def test_expands_mean_stack():
    extracted = names("Developed an app using MEAN.")
    assert {"MEAN Stack", "MongoDB", "Express.js", "Angular", "Node.js"} <= extracted


def test_deduplicates_canonical_and_alias_mentions():
    result = extract_skill_entities("Python programming; Python; py.", DICTIONARY)
    assert sum(item["name"] == "Python" for item in result) == 1


def test_confidence_is_bounded_and_deterministic():
    text = "Technical skills: Python, JavaScript, and Docker."
    first = extract_skill_entities(text, DICTIONARY)
    second = extract_skill_entities(text, DICTIONARY)
    assert first == second
    assert all(0.5 <= item["confidence"] <= 0.99 for item in first)


def test_empty_text_returns_empty_list():
    assert extract_skill_entities("  ", DICTIONARY) == []


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        extract_skill_entities(None, DICTIONARY)


def test_dictionary_has_unique_names():
    dictionary = load_skill_dictionary(DICTIONARY)
    names = [item["name"].casefold() for item in dictionary]
    assert len(names) == len(set(names))


def test_handles_spelling_and_format_variations():
    extracted = names("Javascript, Scikit Learn, Node JS, Tensor flow, and Kubernets.")
    assert {"JavaScript", "Scikit-learn", "Node.js", "TensorFlow", "Kubernetes"} <= extracted


def test_expands_stack_spelling_variations():
    extracted = names("Built apps using MERN-stack and MEAN stack.")
    assert {"MERN Stack", "MongoDB", "Express.js", "React", "Node.js"} <= extracted
    assert {"MEAN Stack", "Angular"} <= extracted


def test_synonyms_normalize_to_one_canonical_entity():
    result = extract_skill_entities("JavaScript, Javascript, and Java Script were used.", DICTIONARY)
    assert sum(item["name"] == "JavaScript" for item in result) == 1

def test_extracts_technical_and_soft_skills():
    extracted = entity_names(
        "Skills: Python, SQL, Machine Learning, "
        "communication and teamwork."
    )
    assert {
        "Python",
        "SQL",
        "Machine Learning",
        "Communication",
        "Teamwork",
    } <= extracted


def test_normalizes_multiple_aliases():
    extracted = entity_names(
        "Experienced in ML, python programming, and postgres."
    )
    assert {
        "Machine Learning",
        "Python",
        "PostgreSQL",
    } <= extracted
    assert "ML" not in extracted


def test_deduplicates_repeated_skill_mentions():
    result = extract_skill_entities(
        "Python, Python programming, and Python.",
        dictionary_path=DICTIONARY,
    )
    assert sum(
        item["name"] == "Python" for item in result
    ) == 1


def test_confidence_is_bounded():
    result = extract_skill_entities(
        "Technical Skills: Python and SQL",
        dictionary_path=DICTIONARY,
    )
    assert all(
        0 <= item["confidence"] <= 1
        for item in result
    )


def test_empty_input_returns_no_entities():
    assert entity_names("") == set()
    assert entity_names("   ") == set()


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        extract_skill_entities(
            None, dictionary_path=DICTIONARY
        )