import os, csv, json, time, smtplib, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

# 1. Load your resume and already-seen jobs
with open("resume.md", "r", encoding="utf-8") as f:
    RESUME = f.read()

SEEN_FILE = "seen_jobs.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_jobs = set(json.load(f))
else:
    seen_jobs = set()

# 2. Pre-filter keywords tailored to Adit's seniority & pan-India preference
INCLUDE_KEYWORDS = [
    "analytics", "revenue operations", "revops", "gtm", "go-to-market",
    "strategy", "planning", "business intelligence", "sales operations", "commercial"
]
EXCLUDE_KEYWORDS = [
    "intern", "internship", "university grad", "junior", "coordinator",
    "specialist", "representative", "sdr", "bdr", "account executive",
    "counsel", "recruiter", "recruiting", "software engineer", "enablement"
]
INDIA_CITIES = [
    "hyderabad", "bengaluru", "bangalore", "mumbai",
    "delhi", "gurgaon", "gurugram", "noida", "pune", "chennai"
]
EXCLUDE_LOCATIONS = ["indiana", "remote - us", "remote, us", "united states", "amer", "emea", "latam", "uk", "canada"]

def is_india_eligible(loc_raw):
    loc = loc_raw.lower()
    if any(bad in loc for bad in EXCLUDE_LOCATIONS):
        return False
    if any(city in loc for city in INDIA_CITIES):
        return True
    # Match "india" as a standalone word (avoids "indiana")
    if "india" in loc.replace(",", " ").replace("-", " ").replace("(", " ").replace(")", " ").split():
        return True
    if "remote" in loc and ("apac" in loc or "global" in loc or loc.strip() == "remote"):
        return True
    return False

def fetch_jobs(company, ats, slug):
    jobs = []
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=15).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"gh_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", {}).get("name", ""),
                    "url": j["absolute_url"], "desc": j.get("content", "")[:4000]
                })
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=15).json()
            if isinstance(r, list):
                for j in r:
                    jobs.append({
                        "id": f"lv_{j['id']}", "company": company, "title": j["text"],
                        "location": j.get("categories", {}).get("location", ""),
                        "url": j["hostedUrl"], "desc": j.get("descriptionPlain", "")[:4000]
                    })
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=15).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"ab_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", ""),
                    "url": j["jobUrl"], "desc": j.get("descriptionPlain", "")[:4000]
                })
    except Exception as e:
        print(f"Skipping {company}: {e}")
    return jobs

def score_job(job):
    prompt = f"""You are an executive recruiter. Compare this candidate's resume and target preferences to the job posting.
Return ONLY valid JSON with keys: "score" (integer 0-100), "reason" (1 sentence why it fits or doesn't), "missing_skills" (comma-separated string).

CANDIDATE RESUME:
{RESUME}

JOB: {job['title']} at {job['company']} ({job['location']})
DESCRIPTION:
{job['desc']}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    res = requests.post(url, json=payload, timeout=30).json()
    if "candidates" not in res:
        raise RuntimeError(f"API Response: {res}")
    text = res["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)

matches = []
evaluated_count = 0

with open("companies.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        for job in fetch_jobs(row["company"], row["ats"].strip(), row["slug"].strip()):
            if job["id"] in seen_jobs:
                continue
            seen_jobs.add(job["id"])

            title_lower = job["title"].lower()
            if not is_india_eligible(job["location"]):
                continue
            if not any(k in title_lower for k in INCLUDE_KEYWORDS) or any(k in title_lower for k in EXCLUDE_KEYWORDS):
                continue

            try:
                evaluated_count += 1
                result = score_job(job)
                print(f"Scored [{result.get('score')}/100]: {job['title']} @ {job['company']}")
                if result.get("score", 0) >= 75:
                    job.update(result)
                    matches.append(job)
                time.sleep(4.5)  # Stays safely under 15 RPM free rate limit
            except Exception as e:
                print(f"AI error on {job['title']}: {e}")
                time.sleep(5)

print(f"Evaluated {evaluated_count} relevant India/Remote roles. Found {len(matches)} matches >= 75.")

with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(seen_jobs), f)

if matches:
    matches.sort(key=lambda x: x["score"], reverse=True)
    html = "<h2>🎯 Today's Top AI Job Matches</h2>"
    for m in matches:
        html += f"<p><b>[{m['score']}/100] {m['title']} — {m['company']}</b> ({m['location']})<br>"
        html += f"<i>Why it fits:</i> {m['reason']}<br><i>Watch out for:</i> {m['missing_skills']}<br>"
        html += f"<a href='{m['url']}'>👉 Apply Here</a></p><hr>"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 {len(matches)} New Job Matches Found Today"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Sent {len(matches)} matches!")
else:
    print("No new matches >= 75 today.")
