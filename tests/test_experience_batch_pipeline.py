import json
from pathlib import Path

from scripts import experience_batch_pipeline as batch


def test_batch_creates_unique_candidate_ids_and_combined_output(tmp_path, monkeypatch):
    inputs = tmp_path / "input"
    outputs = tmp_path / "output"
    inputs.mkdir()
    (inputs / "resume_b.txt").write_text("Work Experience\nData Analyst | Beta Analytics | Jan 2021 - Dec 2022", encoding="utf-8")
    (inputs / "resume_a.txt").write_text("Work Experience\nPython Developer | Alpha Tech | Jan 2023 - Present", encoding="utf-8")
    monkeypatch.setattr(batch, "INPUT_DIR", inputs)
    monkeypatch.setattr(batch, "OUTPUT_DIR", outputs)
    assert batch.main() == 0
    data = json.loads((outputs / "all_candidate_experiences.json").read_text(encoding="utf-8"))
    assert data["success_count"] == 2
    assert [c["candidate_id"] for c in data["candidates"]] == ["CAND_001", "CAND_002"]
    assert len(list(outputs.glob("CAND_*.json"))) == 2
