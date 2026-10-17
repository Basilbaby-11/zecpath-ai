"""Canonical resume section labels and common heading variations."""

HEADING_MAP = {
    "summary": "summary", "professional summary": "summary",
    "profile": "summary", "career objective": "summary", "objective": "summary",
    "about me": "summary", "career profile": "summary",
    "work experience": "work_experience", "professional experience": "work_experience",
    "employment history": "work_experience", "work history": "work_experience",
    "experience": "work_experience", "career history": "work_experience",
    "internship experience": "work_experience", "internships": "work_experience",
    "education": "education", "educational background": "education",
    "academic background": "education", "academic qualifications": "education",
    "qualifications": "education", "educational qualifications": "education", "education and training": "education",
    "skills": "skills", "technical skills": "skills", "core skills": "skills",
    "key skills": "skills", "technical proficiencies": "skills", "skill set": "skills",
    "competencies": "skills", "core competencies": "skills", "areas of expertise": "skills",
    "projects": "projects", "personal projects": "projects", "academic projects": "projects",
    "key projects": "projects", "project experience": "projects", "selected projects": "projects",
    "certifications": "certifications", "certificates": "certifications",
    "certificates & certifications": "certifications", "certification and training": "certifications",
    "licenses and certifications": "certifications", "professional certifications": "certifications",
    "courses and certifications": "certifications", "training and certifications": "certifications",
    "languages": "languages", "language skills": "languages",
    "achievements": "achievements", "accomplishments": "achievements", "awards": "achievements",
    "honors and awards": "achievements", "awards and achievements": "achievements", "awards and achievements": "achievements",
    "soft skills": "soft_skills", "personal skills": "soft_skills",
    "volunteer experience": "volunteer_experience", "volunteering": "volunteer_experience",
    "publications": "publications", "research publications": "publications",
    "references": "references", "interests": "interests", "hobbies": "interests",
}

SECTION_LABELS = tuple(dict.fromkeys(HEADING_MAP.values())) + ("other",)
