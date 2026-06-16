# Engineer Profile Database Schema

This database stores **engineer profiles extracted from CVs** and enriches them with **real-time project data (e.g., JIRA tasks)**.

The goal is to support:

- engineer experience tracking
- skill identification
- project history
- job qualification and ranking

---

# Collection: employees

Each document represents **one engineer** identified by their **company email**.

## Example Document

```json
{
  "_id": "engineer@company.com",

  "name": "Engineer Name",

  "current_role": "AI Engineer",

  "education": [
    {
      "degree": "Engineering",
      "field": "Computer Science",
      "school": "University Name",
      "year": 2026
    }
  ],

  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "AWS",
      "date": "2025"
    }
  ],

  "skills": [
    "Python",
    "Docker",
    "MongoDB",
    "LLM",
    "LangGraph"
  ],

  "projects": [
    {
      "project_id": "PROJECT-ID",

      "client": "Client Name",

      "role": "AI Engineer",

      "start_date": "YYYY-MM",
      "end_date": null,

      "technologies": [
        "Python",
        "Docker",
        "MongoDB"
      ],

      "tasks": [
        {
          "jira_id": "TASK-ID",

          "title": "Task title",

          "description": "Optional task description",

          "technologies": [
            "Python",
            "FastAPI"
          ],

          "complexity": {
            "story_points": 8,
            "difficulty": "hard",
            "type": "feature",
            "responsibility": "implementation"
          },

          "date": "YYYY-MM-DD"
        }
      ]
    }
  ],

  "source": {
    "cv_parsed": true,
    "jira_sync": true,
    "last_update": "YYYY-MM-DD"
  }
}
