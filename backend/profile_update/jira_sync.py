"""
jira_sync.py
------------
Fetches all DONE Jira tickets across every project (since last_update per employee)
and saves them to MongoDB using the functions from db.py.

Run:
    python jira_sync.py
"""

import os
import requests
from dotenv import load_dotenv
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.operations import add_jira_task, get_last_update

load_dotenv()

JIRA_BASE_URL  = os.getenv("JIRA_BASE_URL")
JIRA_AUTH      = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
HEADERS        = {"Accept": "application/json"}


# ── Jira API ──────────────────────────────────────────────────────────────────

def jira_get(path: str, params: dict = None) -> dict:
    url = f"{JIRA_BASE_URL}/rest/api/3/{path}"
    r = requests.get(url, auth=JIRA_AUTH, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def get_all_projects() -> list[dict]:
    data = jira_get("project/search", {"maxResults": 100})
    return data.get("values", [])


def get_done_issues(project_key: str, since_date: str | None) -> list[dict]:
    """Fetch all Done issues in a project, optionally filtered by date."""
    date_filter = f' AND updated >= "{since_date}"' if since_date else ""
    jql = f'project = "{project_key}" AND statusCategory = Done{date_filter} ORDER BY updated ASC'

    issues, start = [], 0
    while True:
        data = jira_get("search/jql", {
            "jql":        jql,
            "startAt":    start,
            "maxResults": 100,
            "fields":     "summary,description,assignee,customfield_10016,labels,updated,issuetype",
        })
        batch = data.get("issues", [])
        issues.extend(batch)
        start += len(batch)
        if start >= data.get("total", 0):
            break

    return issues


# ── Email resolver (Jira hides emails, must resolve via accountId) ────────────

_email_cache: dict[str, str] = {}  # accountId → email, avoids repeated API calls

def get_email_by_account_id(account_id: str) -> str:
    if account_id in _email_cache:
        return _email_cache[account_id]
    try:
        data  = jira_get("user", {"accountId": account_id})
        email = data.get("emailAddress", "").strip()
    except Exception:
        email = ""
    _email_cache[account_id] = email
    return email


# ── Issue parsing ─────────────────────────────────────────────────────────────

def parse_issue(issue: dict) -> dict | None:
    """Extract relevant fields from a raw Jira issue. Returns None if unassigned."""
    fields     = issue["fields"]
    assignee   = fields.get("assignee") or {}
    account_id = assignee.get("accountId", "").strip()

    if not account_id:
        return None  # skip unassigned tickets

    email = get_email_by_account_id(account_id)
    if not email:
        print(f"  [!] Could not resolve email for accountId '{account_id}', skipping.")
        return None

    story_pts = int(fields.get("customfield_10016") or 0)

    if story_pts >= 8:
        difficulty = "hard"
    elif story_pts >= 3:
        difficulty = "medium"
    else:
        difficulty = "easy"

    # Extract plain text from Atlassian Document Format description
    desc_text = ""
    for block in (fields.get("description") or {}).get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                desc_text += inline.get("text", "")

    return {
        "email":        email,
        "name":         assignee.get("displayName", ""),
        "jira_id":      issue["key"],
        "title":        fields.get("summary", ""),
        "description":  desc_text.strip(),
        "technologies": fields.get("labels", []),   # labels used as technologies
        "story_points": story_pts,
        "difficulty":   difficulty,
        "task_type":    (fields.get("issuetype") or {}).get("name", "task").lower(),
        "date":         (fields.get("updated") or "")[:10],
    }


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync(date: str | None = None):
    print("=== Jira sync started ===\n")
    if date:
        print(f"Filtering tickets updated on or after: {date}\n")

    projects = get_all_projects()
    print(f"Found {len(projects)} project(s).\n")

    for project in projects:
        key  = project["key"]
        name = project["name"]

        print(f"[{key}] Fetching done issues …")
        issues = get_done_issues(key, since_date=date)
        print(f"[{key}] {len(issues)} done issue(s) found.")

        for issue in issues:
            parsed = parse_issue(issue)
            if not parsed:
                continue  # unassigned

            # Skip tickets already covered by the employee's last sync date
            last_update = get_last_update(parsed["email"])
            if last_update and parsed["date"] and parsed["date"] <= last_update:
                continue

            add_jira_task(
                email          = parsed["email"],
                project_id     = key,
                project_name   = name,
                jira_id        = parsed["jira_id"],
                title          = parsed["title"],
                description    = parsed["description"],
                technologies   = parsed["technologies"],
                story_points   = parsed["story_points"],
                difficulty     = parsed["difficulty"],
                task_type      = parsed["task_type"],
                responsibility = "implementation",
                date           = parsed["date"],
            )

    print("\n=== Sync complete ===")


if __name__ == "__main__":
    import sys
    cli_date = sys.argv[1] if len(sys.argv) > 1 else None
    sync(date=cli_date)