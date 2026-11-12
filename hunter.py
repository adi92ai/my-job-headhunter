import os, re, csv, json, time, smtplib, requests
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
CONTACT_HEADER = os.environ.get("RESUME_CONTACT_HEADER", "Hyderabad, India | linkedin.com/in/adit92")

with open("resume.md", "r", encoding="utf-8") as f:
    RESUME = f.read()

SEEN_FILE = "seen_jobs.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen_jobs = set(json.load(f))
else:
    seen_jobs = set()

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
                    "url": j["absolute_url"], "desc": j.get("content", "")[:5000]
                })
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=12).json()
            if isinstance(r, list):
                for j in r:
                    jobs.append({
                        "id": f"lv_{j['id']}", "company": company, "title": j["text"],
                        "location": j.get("categories", {}).get("location", ""),
                        "url": j["hostedUrl"], "desc": j.get("descriptionPlain", "")[:5000]
                    })
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"ab_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", ""),
                    "url": j["jobUrl"], "desc": j.get("descriptionPlain", "")[:5000]
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
                    "desc": j.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", j["name"])[:5000]
                })
        elif ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"wk_{j['shortcode']}", "company": company, "title": j["title"],
                    "location": f"{j.get('city', '')}, {j.get('country', '')}",
                    "url": j["url"], "desc": j.get("description", j["title"])[:5000]
                })
        elif ats == "workday":
            parts = slug.split("|")
            if len(parts) == 3:
                tenant, wd_num, site = parts
                wd_url = f"https://{tenant}.{wd_num}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
                payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "India"}
                r = requests.post(wd_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15).json()
                for j in r.get("jobPostings", []):
                    ext_path = j.get("externalPath", "")
                    jobs.append({
                        "id": f"wd_{tenant}_{ext_path}", "company": company, "title": j.get("title", ""),
                        "location": j.get("locationsText", "India"),
                        "url": f"https://{tenant}.{wd_num}.myworkdayjobs.com/en-US/{site}{ext_path}",
                        "desc": f"{j.get('title', '')} - {j.get('locationsText', '')} - {' '.join(j.get('bulletFields', []))}"
                    })
    except Exception:
        pass
    return jobs

def call_gemini(model, prompt, timeout=45):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    for attempt in range(2):
        res = requests.post(url, json=payload, timeout=timeout).json()
        if "candidates" in res:
            return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
        time.sleep(5)
    raise RuntimeError(f"API Response: {res}")

# STAGE A ($0 Free Tier): Fast Triage with Gemini 2.5 Flash-Lite (500 RPD / 15 RPM)
def triage_job(job):
    prompt = f"""You are an executive recruiter screening roles for Adit Agarwal (12+ yrs exp: leads Business Analytics for ServiceNow's $10B+ DGTM org, $1.2B+ quantified impact at Amazon, P&L founder).
Score this job 0-100 against Adit's resume and preferences. Reserve 80+ ONLY for true Manager, Senior Manager, Director, or Head roles in India/Remote matching Analytics, RevOps, GTM, or Commercial Strategy.
Return ONLY valid JSON: {{"score": integer, "quick_reason": "1 sentence"}}

RESUME:
{RESUME}

JOB: {job['title']} at {job['company']} ({job['location']})
DESCRIPTION:
{job['desc']}"""
    return call_gemini("gemini-3.5-flash-lite", prompt, timeout=35)

# STAGE B ($0 Free Tier): Deep Research + Touch-Up Resume (2.5-Flash with automatic 2.5-Flash-Lite fallback)
def deep_research_and_touchup(job):
    prompt = f"""You are an elite executive career strategist preparing Adit Agarwal for a high-priority application.
Perform deep role research AND a surgical "Touch-Up Mode" tailoring of Adit's resume for this exact job.

STRICT GUARDRAILS FOR TOUCH-UP RESUME:
- NEVER invent metrics, job titles, employers, tools, or degrees. Preserve 100% factual accuracy from the master resume.
- DO tailor the headline, 3-line Executive Summary, Core Expertise ordering, and 3-4 key bullets under ServiceNow and Amazon to mirror the JD's strategic priorities and keywords.

Return ONLY valid JSON with these exact keys:
- "strategic_fit": 2 sentences on why Adit's ServiceNow ($10B+ DGTM) & Amazon ($1.2B+ impact) background gives him an unfair advantage.
- "company_intel": 2 sentences decoding what commercial or operational bottleneck this company is hiring to solve right now.
- "missing_skills": comma-separated JD keywords/tools Adit should emphasize.
- "touchup_diff": 2-3 bullet points summarizing exact surgical changes made to the resume so Adit can review in 15 seconds.
- "outreach_hook": 1 sharp LinkedIn DM sentence to send the Hiring Manager / VP.
- "tailored_headline": tailored 1-line title banner for the top of the resume.
- "tailored_summary": tailored 3-4 sentence Executive Summary paragraph.
- "tailored_skills": tailored comma/pipe-separated Core Expertise string prioritizing JD keywords.
- "servicenow_mgr_bullets": array of 5 strong bullets for ServiceNow Business Analytics Manager (March 2025 - Present).
- "servicenow_sr_bullets": array of 3 strong bullets for ServiceNow Senior Analyst (June 2023 - Feb 2025).
- "amazon_bullets": array of 4 strong bullets for Amazon Senior Program Manager (Oct 2013 - June 2021).
- "founder_bullets": array of 2 strong bullets for Founder & Owner, ART FOODS (Aug 2021 - June 2023).

MASTER RESUME:
{RESUME}

TARGET JOB: {job['title']} at {job['company']} ({job['location']})
JOB DESCRIPTION:
{job['desc']}"""
    try:
        time.sleep(12.5)  # Stays safely under 5 RPM free limit on gemini-3.8-flash
        return call_gemini("gemini-3.8-flash", prompt, timeout=50)
    except Exception:
        print("  -> Falling back to gemini-3.5-flash-lite for Stage B...")
        time.sleep(4.5)
        return call_gemini("gemini-3.5-flash-lite", prompt, timeout=50)

def build_docx_resume(job, data):
    os.makedirs("tailored_resumes", exist_ok=True)
    safe_comp = re.sub(r"[^a-zA-Z0-9]+", "_", job["company"]).strip("_")
    filename = f"tailored_resumes/Adit_Agarwal_{safe_comp}.docx"

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    def add_heading_line(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(text.upper())
        r.bold = True
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0x1A, 0x4E, 0x8A)

    # Header
    p_name = doc.add_paragraph()
    p_name.paragraph_format.space_after = Pt(1)
    r_name = p_name.add_run("ADIT AGARWAL")
    r_name.bold = True
    r_name.font.size = Pt(18)
    r_name.font.color.rgb = RGBColor(0x11, 0x22, 0x33)

    p_head = doc.add_paragraph()
    p_head.paragraph_format.space_after = Pt(2)
    r_head = p_head.add_run(data.get("tailored_headline", "Business Analytics & AI | Digital Go-to-Market (DGTM) Analytics | Revenue Operations"))
    r_head.bold = True
    r_head.font.size = Pt(10.5)
    r_head.font.color.rgb = RGBColor(0x1A, 0x4E, 0x8A)

    p_contact = doc.add_paragraph()
    p_contact.paragraph_format.space_after = Pt(6)
    r_contact = p_contact.add_run(CONTACT_HEADER)
    r_contact.font.size = Pt(9.5)
    r_contact.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # Executive Summary
    add_heading_line("Executive Profile")
    p_sum = doc.add_paragraph(data.get("tailored_summary", ""))
    p_sum.paragraph_format.space_after = Pt(4)

    # Core Expertise
    add_heading_line("Core Expertise")
    p_sk = doc.add_paragraph(data.get("tailored_skills", ""))
    p_sk.paragraph_format.space_after = Pt(4)

    # Experience Helper
    def add_role(company_title, subtitle, bullets):
        p_r = doc.add_paragraph()
        p_r.paragraph_format.space_before = Pt(5)
        p_r.paragraph_format.space_after = Pt(2)
        r1 = p_r.add_run(company_title)
        r1.bold = True
        r2 = p_r.add_run(f"  |  {subtitle}")
        r2.italic = True
        for b in bullets:
            pb = doc.add_paragraph(style="List Bullet")
            pb.paragraph_format.space_after = Pt(2)
            pb.add_run(b)

    add_heading_line("Professional Experience")
    add_role("ServiceNow", "Business Analytics Manager | March 2025 – Present", data.get("servicenow_mgr_bullets", []))
    add_role("ServiceNow", "Senior Analyst | June 2023 – February 2025", data.get("servicenow_sr_bullets", []))
    add_role("Amazon", "Senior Program Manager | October 2013 – June 2021", data.get("amazon_bullets", []))
    add_role("ART FOODS (La Pino'z Pizza Franchise)", "Founder & Owner | August 2021 – June 2023", data.get("founder_bullets", []))

    add_heading_line("Education & Technology")
    p_ed = doc.add_paragraph()
    p_ed.paragraph_format.space_after = Pt(2)
    p_ed.add_run("Education: ").bold = True
    p_ed.add_run("Bachelor of Business Administration (BBA) — University of Mysore")

    p_tc = doc.add_paragraph()
    p_tc.add_run("Technology: ").bold = True
    p_tc.add_run("Microsoft Copilot, Claude, AI-enabled Analytics | Power BI, SQL, DAX, Power Query, Advanced Excel, VBA, SAP BusinessObjects")

    doc.save(filename)
    return filename

matches = []
attachments = []
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
                triage = triage_job(job)
                seen_jobs.add(job["id"])
                score = triage.get("score", 0)
                print(f"Triaged [{score}/100]: {job['title']} @ {job['company']}")

                if score >= 80:
                    print(f"  -> Generating Executive Research & Touch-Up .docx Resume for {job['company']}...")
                    deep = deep_research_and_touchup(job)
                    docx_path = build_docx_resume(job, deep)
                    attachments.append(docx_path)
                    job["score"] = score
                    job.update(deep)
                    matches.append(job)
                time.sleep(4.5)  # Stays safely under 15 RPM free limit on gemini-3.5-flash-lite
            except Exception as e:
                print(f"AI error on {job['title']}: {e}")
                time.sleep(5)

print(f"Scanned {companies_checked} companies | Triaged {evaluated_count} India/Remote roles | Deep-Researched {len(matches)} matches >= 80.")

with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(seen_jobs), f)

if matches:
    matches.sort(key=lambda x: x["score"], reverse=True)
    html = f"<h2>🎯 Executive Headhunter Brief + Touch-Up Resumes ({len(matches)} Priority Matches)</h2>"
    html += "<p style='color:#555;'>Tailored <b>.docx resumes</b> (with your private contact header pre-filled) are attached below—ready to review and export to PDF.</p>"
    for m in matches:
        diff_html = "".join(f"<li>{d}</li>" for d in m.get("touchup_diff", []))
        html += f"""
        <div style='font-family: Arial, sans-serif; border: 1px solid #ddd; padding: 16px; border-radius: 8px; margin-bottom: 20px;'>
            <h3 style='margin:0 0 6px 0; color:#1a4e8a;'>[{m['score']}/100] {m['title']} — {m['company']}</h3>
            <p style='margin:0 0 10px 0; color:#555;'>📍 {m['location']} &nbsp;|&nbsp; <a href='{m['url']}'><b>👉 Direct Application Link</b></a></p>
            <p><b>🧠 Strategic Fit:</b> {m.get('strategic_fit', '')}</p>
            <p><b>🔍 Company & Role Intel:</b> {m.get('company_intel', '')}</p>
            <p><b>⚠️ Keywords / Gaps to Watch:</b> {m.get('missing_skills', '')}</p>
            <p><b>📎 Resume Touch-Up Summary (Attached .docx):</b></p>
            <ul>{diff_html}</ul>
            <p style='background:#f4f8ff; padding:10px; border-left:4px solid #1a4e8a;'><b>💬 LinkedIn DM Hook to Hiring Manager:</b><br><i>"{m.get('outreach_hook', '')}"</i></p>
        </div>
        """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🚀 Executive Brief + {len(matches)} Tailored Resumes Ready"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg.attach(MIMEText(html, "html"))

    for filepath in attachments:
        with open(filepath, "rb") as af:
            part = MIMEApplication(af.read(), Name=os.path.basename(filepath))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(filepath)}"'
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Sent {len(matches)} executive briefs + .docx attachments!")
else:
    print("No new matches >= 80 today.")
