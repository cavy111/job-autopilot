"""
agents/sample_profile.py

A generic, fictional CV profile used for offline demos and the __main__ test
blocks in each agent (no real personal data). Real runs build the profile from
the user's uploaded CV via agents/cv_parser.py.
"""

SAMPLE_CV_PROFILE = {
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+1 555 0100",
    "location": "Anytown",
    "summary": (
        "BSc (Hons) Information Systems graduate with over a year of professional "
        "software development and IT systems experience. Skilled in debugging and "
        "troubleshooting across the full stack, maintaining production systems, and "
        "providing technical support to end users. Proficient in Python, JavaScript, "
        "PHP, and Java, with a structured, analytical approach to technical problems."
    ),
    "skills": {
        "languages":  ["Python", "JavaScript", "PHP", "Java", "HTML5", "CSS3"],
        "frameworks": ["Django", "React", "Laravel", "Spring Boot"],
        "databases":  ["SQL", "MySQL", "PostgreSQL", "SQLite"],
        "devops":     ["Docker", "Git", "REST APIs"],
        "other":      ["Full-stack debugging", "IT systems support", "Technical documentation"],
    },
    "experience": [
        {
            "title":    "Web Applications Developer",
            "company":  "Example Software Ltd",
            "location": "Anytown",
            "period":   "May 2024 – June 2025",
            "bullets":  [
                "Provided ongoing IT systems support for internal web applications.",
                "Diagnosed and resolved software defects across a React/Django stack.",
                "Maintained production systems and supported end users across teams.",
            ],
        },
        {
            "title":    "ICT Facilitator",
            "company":  "Example Junior School",
            "location": "Anytown",
            "period":   "February 2026 – April 2026",
            "bullets":  [
                "Managed classroom computer equipment and troubleshot hardware/software issues.",
                "Delivered ICT support and training to staff and students.",
            ],
        },
    ],
    "education": [
        {
            "degree":      "BSc (Hons) Information Systems",
            "grade":       "2.1",
            "institution": "Example University",
            "location":    "Anytown",
            "period":      "2017 – 2022",
        },
        {
            "degree":      "National Certificate in Information Technology",
            "grade":       None,
            "institution": "Example Polytechnic",
            "location":    "Anytown",
            "period":      "2016",
        },
    ],
    "certifications": [
        "Software Engineering Job Simulation · Example Provider · 2026",
        "Class 4 Driver's Licence",
    ],
    "references": [
        {
            "name":    "Reference One",
            "role":    "Director, Example Organisation",
            "contact": "+1 555 0101 · reference.one@example.com",
        },
        {
            "name":    "Reference Two",
            "role":    "Department Chair, Example University",
            "contact": "+1 555 0102 · reference.two@example.com",
        },
    ],
    "raw_text": "",
}
