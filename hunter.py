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
    "strategy", "planning", "business intelligence", "sales operations",
    "commercial", "chief of staff", "business operations", "bizops"
]
EXCLUDE_KEYWORDS = [
    "intern", "internship", "university grad", "junior", "coordinator",
    "specialist", "representative", "sdr", "bdr", "account executive",
    "counsel", "recruiter", "recruiting", "software engineer", "enablement",
    "developer", "frontend", "backend", "devops", "qa ", "people partner"
]
INDIA_CITIES = [
    "hyderabad", "bengaluru", "bangalore", "mumbai",
    "delhi", "gurgaon", "gurugram", "noida", "pune", "chennai"
]
EXCLUDE_LOCATIONS = [
    "indiana", "remote - us", "remote, us", "united states",
    "amer", "emea", "latam", "uk", "canada", "europe"
]

def is_india_eligible(loc_raw):
    if not loc_raw:
        return False
    loc = loc_raw.lower()
    if any(bad in loc for bad in EXCLUDE_LOCATIONS):
        return False
    if any(city in loc for city in INDIA_CITIES):
        return True
    tokens = loc.replace(",", " ").replace("-", " ").replace("(", " ").replace(")", " ").split()
    if "india" in tokens:
        return True
    if "remote" in loc and ("apac" in loc or "global" in loc or loc.strip() == "remote"):
        return True
    return False

def fetch_jobs(company, ats, slug):
    jobs = []
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"gh_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", {}).get("name", ""),
                    "url": j["absolute_url"], "desc": j.get("content", "")[:4500]
                })
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=12).json()
            if isinstance(r, list):
                for j in r:
                    jobs.append({
                        "id": f"lv_{j['id']}", "company": company, "title": j["text"],
                        "location": j.get("categories", {}).get("location", ""),
                        "url": j["hostedUrl"], "desc": j.get("descriptionPlain", "")[:4500]
                    })
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"ab_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", ""),
                    "url": j["jobUrl"], "desc": j.get("descriptionPlain", "")[:4500]
                })
        elif ats == "smartrecruiters":
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100", timeout=12).json()
            for j in r.get("content", []):
                loc_obj = j.get("location", {})
                loc_str = f"{loc_obj.get('city', '')}, {loc_obj.get('country', '')}"
                jobs.append({
                    "id": f"sr_{j['id']}", "company": company, "title": j["name"],
                    "location": loc_str,
                    "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                    "desc": j.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", j["name"])[:4500]
                })
        elif ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"wk_{j['shortcode']}", "company": company, "title": j["title"],
                    "location": f"{j.get('city', '')}, {j.get('country', '')}",
                    "url": j["url"], "desc": j.get("description", j["title"])[:4500]
                })
    except Exception:
        pass
    return jobs

def research_and_score_job(job):
    prompt = f"""You are an executive headhunter & GTM strategy researcher advising Adit Agarwal (12+ yrs exp: leads Business Analytics for ServiceNow's $10B+ DGTM org, $1.2B+ quantified impact at Amazon, P&L founder).
Analyze this job posting deeply against Adit's resume and preferences.

Return ONLY valid JSON with these exact keys:
- "score": integer 0-100 (be strict: reserve 80+ for true Manager/Senior Manager/Director/Head roles in India/Remote matching Analytics, RevOps, GTM, or Commercial Strategy).
- "strategic_fit": 2 sentences explaining why Adit's ServiceNow/Amazon track record gives him an unfair advantage here.
- "company_intel": 1-2 sentences decoding what business problem or growth bottleneck this team is hiring to solve based on the JD.
- "missing_skills": comma-separated keywords/tools mentioned in the JD that Adit should highlight or address.
- "resume_tweaks": array of 2 short, concrete bullet points Adit can paste into his resume/cover note tailored to this exact JD.
- "outreach_hook": 1 sharp, high-impact sentence Adit can DM to the Hiring Manager or VP on LinkedIn.

CANDIDATE RESUME:
{RESUME}

JOB: {job['title']} at {job['company']} ({job['location']})
DESCRIPTION:
{job['desc']}"""

    # Uses gemini-3.5-flash-lite (500 free requests/day, ultra-fast, zero 503 congestion)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}

    for attempt in range(2):
        res = requests.post(url, json=payload, timeout=45).json()
        if "candidates" in res:
            text = res["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        time.sleep(6)
    raise RuntimeError(f"API Response: {res}")

matches = []
evaluated_count = 0
companies_checked = 0

with open("companies.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        companies_checked += 1
        for job in fetch_jobs(row["company"], row["ats"].strip().lower(), row["slug"].strip()):
            if job["id"] in seen_jobs:
                continue

            title_lower = job["title"].lower()
            if not is_india_eligible(job["location"]):
                seen_jobs.add(job["id"])
                continue
            if not any(k in title_lower for k in INCLUDE_KEYWORDS) or any(k in title_lower for k in EXCLUDE_KEYWORDS):
                seen_jobs.add(job["id"])
                continue

            try:
                evaluated_count += 1
                result = research_and_score_job(job)
                seen_jobs.add(job["id"])  # Only mark seen AFTER AI succeeds!
                print(f"Scored [{result.get('score')}/100]: {job['title']} @ {job['company']}")
                if result.get("score", 0) >= 75:
                    job.update(result)
                    matches.append(job)
                time.sleep(4.5)
            except Exception as e:
                print(f"AI error on {job['title']}: {e}")
                time.sleep(5)

print(f"Scanned {companies_checked} companies | Evaluated {evaluated_count} India/Remote roles | Found {len(matches)} matches >= 75.")

with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(seen_jobs), f)

if matches:
    matches.sort(key=lambda x: x["score"], reverse=True)
    html = f"<h2>🎯 Executive Headhunter Research Brief ({len(matches)} Matches)</h2>"
    for m in matches:
        tweaks_html = "".join(f"<li>{t}</li>" for t in m.get("resume_tweaks", []))
        html += f"""
        <div style='font-family: Arial, sans-serif; border: 1px solid #ddd; padding: 16px; border-radius: 8px; margin-bottom: 18px;'>
            <h3 style='margin:0 0 6px 0; color:#1a73e8;'>[{m['score']}/100] {m['title']} — {m['company']}</h3>
            <p style='margin:0 0 10px 0; color:#555;'>📍 {m['location']} &nbsp;|&nbsp; <a href='{m['url']}'><b>👉 Direct Application Link</b></a></p>
            <p><b>🧠 Strategic Fit:</b> {m.get('strategic_fit', '')}</p>
            <p><b>🔍 Company & Role Intel:</b> {m.get('company_intel', '')}</p>
            <p><b>⚠️ Keywords / Gaps to Watch:</b> {m.get('missing_skills', '')}</p>
            <p><b>✍️ Tailored Resume Bullets for This Role:</b></p>
            <ul>{tweaks_html}</ul>
            <p style='background:#f4f8ff; padding:10px; border-left:4px solid #1a73e8;'><b>💬 LinkedIn DM Hook to Hiring Manager:</b><br><i>"{m.get('outreach_hook', '')}"</i></p>
        </div>
        """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 Executive Research Brief: {len(matches)} High-Fit Roles Today"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Sent {len(matches)} research briefs!")
else:
    print("No new matches >= 75 today.")
