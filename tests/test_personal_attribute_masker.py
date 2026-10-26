from fairness.personal_attribute_masker import mask_personal_attributes

def test_removes_identifiers_redacts_contact_and_preserves_job_data():
    source = {
        "candidate_id":"C1", "full_name":"Test Person", "email":"test@example.com",
        "phone":"+1 202 555 0188", "skills":["Python"], "summary":"Email test@example.com",
        "candidate":{"name":"Nested Name","location":"Somewhere","experience_years":2}
    }
    masked = mask_personal_attributes(source)
    assert "full_name" not in masked and "email" not in masked and "phone" not in masked
    assert "test@example.com" not in str(masked)
    assert "Python" in masked["skills"]
    assert "experience_years" in masked["candidate"]
    assert source["email"] == "test@example.com"  # original remains unchanged

def test_redacts_dob_text():
    masked = mask_personal_attributes({"summary":"DOB: 01/02/2000; skilled in Python"})
    assert "01/02/2000" not in masked["summary"]
    assert "Python" in masked["summary"]
