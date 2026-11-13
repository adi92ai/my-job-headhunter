import os, re, csv, json, time, smtplib, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
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

def sanitize_text(val):
    if not isinstance(val, str):
        return val
    replacements = {
        "\u2011": "-",
        "\u2012": "-",
        "\u2010": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": ""
    }
    for bad, good in replacements.items():
        val = val.replace(bad, good)
    return val

def ensure_list(val):
    if isinstance(val, list):
        return [sanitize_text(str(item)).lstrip("-•* ").strip() for item in val if str(item).strip()]
    if isinstance(val, str):
        lines = [line.lstrip("-•* ").strip() for line in val.splitlines() if line.strip()]
        return [sanitize_text(line) for line in lines] if lines else []
    return []

def normalize_ai_payload(data):
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = sanitize_text(v)
        elif isinstance(v, list):
            data[k] = [sanitize_text(str(x)) for x in v]
    data["touchup_diff"] = ensure_list(data.get("touchup_diff", []))
    for b_key in ["servicenow_mgr_bullets", "servicenow_sr_bullets", "amazon_bullets", "founder_bullets"]:
        data[b_key] = ensure_list(data.get(b_key, []))
    return data

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

def clean_html(raw_html):
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    return re.sub(r"\s+", " ", text).strip()[:14000]

def fetch_jobs(raw_row):
    row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
    company = row.get("company") or row.get("name") or ""
    ats = (row.get("ats") or row.get("platform") or "").lower()
    slug = row.get("slug") or row.get("board") or ""
    jobs = []
    if not ats or not slug or company.lower() == "servicenow":
        return jobs
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"gh_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", {}).get("name", ""),
                    "url": j["absolute_url"], "desc": clean_html(j.get("content", ""))
                })
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=12).json()
            if isinstance(r, list):
                for j in r:
                    jobs.append({
                        "id": f"lv_{j['id']}", "company": company, "title": j["text"],
                        "location": j.get("categories", {}).get("location", ""),
                        "url": j["hostedUrl"], "desc": clean_html(j.get("descriptionPlain", ""))
                    })
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"ab_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", ""),
                    "url": j["jobUrl"], "desc": clean_html(j.get("descriptionPlain", ""))
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
                    "desc": clean_html(j.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", j["name"]))
                })
        elif ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=12).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"wk_{j['shortcode']}", "company": company, "title": j["title"],
                    "location": f"{j.get('city', '')}, {j.get('country', '')}",
                    "url": j["url"], "desc": clean_html(j.get("description", j["title"]))
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

def extract_json_safely(raw_text):
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end+1]
    return json.loads(cleaned)

def call_nvidia(prompt, model="nvidia/nemotron-3-ultra-550b-a55b", timeout=90):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an elite executive career strategist. Return ONLY valid JSON with standard ASCII hyphens (-), never non-breaking hyphens."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }
    res = requests.post(url, headers=headers, json=payload, timeout=timeout).json()
    if "choices" in res:
        content = res["choices"][0]["message"].get("content", "")
        return extract_json_safely(content)
    raise RuntimeError(f"NVIDIA NIM Response: {res}")

def call_groq(prompt, model="openai/gpt-oss-120b", timeout=35):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an executive recruiter. Always respond with valid JSON only using standard ASCII punctuation."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    res = requests.post(url, headers=headers, json=payload, timeout=timeout).json()
    if "choices" in res:
        return extract_json_safely(res["choices"][0]["message"]["content"])
    raise RuntimeError(f"Groq API Response: {res}")

def call_gemini(prompt, model="gemini-3.8-flash", timeout=45):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    res = requests.post(url, json=payload, timeout=timeout).json()
    if "candidates" in res:
        return extract_json_safely(res["candidates"][0]["content"]["parts"][0]["text"])
    raise RuntimeError(f"Gemini API Response: {res}")

def triage_job(job):
    prompt = f"""Score this job 0-100 against Adit Agarwal's resume and preferences (12+ yrs exp: leads Business Analytics for ServiceNow's $10B+ DGTM org, $1.2B+ quantified impact at Amazon, P&L founder).
Reserve 75+ ONLY for true Manager, Senior Manager, Director, or Head roles in India/Remote matching Analytics, RevOps, GTM, or Commercial Strategy.
Return ONLY valid JSON: {{"score": integer, "quick_reason": "1 sentence"}}

RESUME:
{RESUME}

JOB: {job['title']} at {job['company']} ({job['location']})
FULL DESCRIPTION:
{job['desc']}"""
    for attempt_model in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "meta-llama/llama-4-scout-17b-16e-instruct"]:
        try:
            return call_groq(prompt, model=attempt_model, timeout=30)
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                time.sleep(8)
            else:
                time.sleep(2)
    raise RuntimeError("All Groq triage models failed")

def deep_research_and_touchup(job):
    prompt = f"""You are an elite executive career strategist preparing Adit Agarwal for a high-priority application.
Perform deep role research AND a surgical "Touch-Up Mode" tailoring of Adit's resume for this exact job.

STRICT GUARDRAILS FOR TOUCH-UP RESUME:
- NEVER invent metrics, job titles, employers, tools, or degrees. Preserve 100% factual accuracy from the master resume.
- Use ONLY standard ASCII hyphens (-), never non-breaking hyphens.
- DO tailor the headline, 3-line Executive Summary, Core Expertise ordering, and 3-4 key bullets under ServiceNow and Amazon to mirror the JD's strategic priorities and keywords.

Return ONLY valid JSON with these exact keys (ensure all list keys are true JSON arrays of strings):
- "strategic_fit": string (2 sentences on why Adit's ServiceNow $10B+ DGTM & Amazon $1.2B+ impact background gives him an unfair advantage)
- "company_intel": string (2 sentences decoding what commercial or operational bottleneck this company is hiring to solve right now)
- "missing_skills": string (comma-separated JD keywords/tools Adit should emphasize)
- "touchup_diff": JSON array of 3 concise strings summarizing exact surgical changes made to the resume
- "outreach_hook": string (1 sharp LinkedIn DM sentence to send the Hiring Manager / VP)
- "tailored_headline": string (tailored 1-line title banner for the top of the resume)
- "tailored_summary": string (tailored 3-4 sentence Executive Summary paragraph)
- "tailored_skills": string (tailored pipe-separated Core Expertise string prioritizing JD keywords)
- "servicenow_mgr_bullets": JSON array of 5 strong bullet strings for ServiceNow Business Analytics Manager (March 2025 - Present)
- "servicenow_sr_bullets": JSON array of 3 strong bullet strings for ServiceNow Senior Analyst (June 2023 - Feb 2025)
- "amazon_bullets": JSON array of 4 strong bullet strings for Amazon Senior Program Manager (Oct 2013 - June 2021)
- "founder_bullets": JSON array of 2 strong bullet strings for Founder & Owner, ART FOODS (Aug 2021 - June 2023)

MASTER RESUME:
{RESUME}

TARGET JOB: {job['title']} at {job['company']} ({job['location']})
FULL JOB DESCRIPTION:
{job['desc']}"""

    raw_result = None
    if NVIDIA_API_KEY:
        nim_models = [
            "nvidia/nemotron-3-ultra-550b-a55b",
            "deepseek-ai/deepseek-v4.1-flash"
        ]
        for nim_model in nim_models:
            try:
                print(f"  -> Calling NVIDIA NIM ({nim_model})...")
                time.sleep(2)
                raw_result = call_nvidia(prompt, model=nim_model, timeout=90)
                break
            except Exception as e:
                print(f"  -> NVIDIA NIM ({nim_model}) skipped: {e}")

    if raw_result is None:
        print("  -> Failing over to Groq 120B...")
        time.sleep(3)
        raw_result = call_groq(prompt, model="openai/gpt-oss-120b", timeout=50)

    if raw_result is None and GEMINI_API_KEY:
        try:
            print("  -> Failing over to Gemini 3.8 Flash...")
            time.sleep(12.5)
            raw_result = call_gemini(prompt, model="gemini-3.8-flash", timeout=50)
        except Exception as e:
            print(f"  -> Gemini skipped: {e}")

    return normalize_ai_payload(raw_result)

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
    r_contact = p_contact.add_run(sanitize_text(CONTACT_HEADER))
    r_contact.font.size = Pt(9.5)
    r_contact.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    add_heading_line("Executive Profile")
    p_sum = doc.add_paragraph(data.get("tailored_summary", ""))
    p_sum.paragraph_format.space_after = Pt(4)

    add_heading_line("Core Expertise")
    p_sk = doc.add_paragraph(data.get("tailored_skills", ""))
    p_sk.paragraph_format.space_after = Pt(4)

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
    add_role("ServiceNow", "Business Analytics Manager | March 2025 - Present", data.get("servicenow_mgr_bullets", []))
    add_role("ServiceNow", "Senior Analyst | June 2023 - February 2025", data.get("servicenow_sr_bullets", []))
    add_role("Amazon", "Senior Program Manager | October 2013 - June 2021", data.get("amazon_bullets", []))
    add_role("ART FOODS (La Pino'z Pizza Franchise)", "Founder & Owner | August 2021 - June 2023", data.get("founder_bullets", []))

    add_heading_line("Education & Technology")
    p_ed = doc.add_paragraph()
    p_ed.paragraph_format.space_after = Pt(2)
    p_ed.add_run("Education: ").bold = True
    p_ed.add_run("Bachelor of Business Administration (BBA) - University of Mysore")

    p_tc = doc.add_paragraph()
    p_tc.add_run("Technology: ").bold = True
    p_tc.add_run("Microsoft Copilot, Claude, AI-enabled Analytics | Power BI, SQL, DAX, Power Query, Advanced Excel, VBA, SAP BusinessObjects")

    doc.save(filename)
    return filename

# 1. Parallel fetch across all company boards (~16 seconds total)
t0 = time.time()
with open("companies.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    print(f"CSV Headers detected: {reader.fieldnames}")
    company_rows = list(reader)

total_raw_jobs = 0
candidate_jobs = []
with ThreadPoolExecutor(max_workers=12) as pool:
    futures = [pool.submit(fetch_jobs, row) for row in company_rows]
    for fut in as_completed(futures):
        fetched = fut.result()
        total_raw_jobs += len(fetched)
        for job in fetched:
            if job["id"] in seen_jobs:
                continue
            title_lower = job["title"].lower()
            if not is_india_eligible(job["location"]):
                seen_jobs.add(job["id"])
                continue
            if not any(k in title_lower for k in INCLUDE_KEYWORDS) or any(k in title_lower for k in EXCLUDE_KEYWORDS):
                seen_jobs.add(job["id"])
                continue
            candidate_jobs.append(job)

print(f"Fetched {len(company_rows)} companies ({total_raw_jobs} total jobs) in {time.time() - t0:.1f}s | {len(candidate_jobs)} new India/Remote leadership roles to triage.")

# 2. Fast Groq Triage + NVIDIA NIM Executive Touch-Up Resumes
matches = []
attachments = []
evaluated_count = 0

for job in candidate_jobs:
    try:
        evaluated_count += 1
        triage = triage_job(job)
        seen_jobs.add(job["id"])
        score = triage.get("score", 0)
        print(f"Triaged [{score}/100]: {job['title']} @ {job['company']}")

        if score >= 75:
            print(f"  -> Generating Executive Research & Touch-Up .docx Resume for {job['company']}...")
            deep = deep_research_and_touchup(job)
            docx_path = build_docx_resume(job, deep)
            attachments.append(docx_path)
            job["score"] = score
            job.update(deep)
            matches.append(job)
        time.sleep(2.5)
    except Exception as e:
        print(f"AI error on {job['title']}: {e}")
        time.sleep(4)

print(f"Triaged {evaluated_count} roles | Deep-Researched {len(matches)} matches >= 75.")

with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(seen_jobs), f)

if matches:
    matches.sort(key=lambda x: x["score"], reverse=True)
    html = f"<h2>Executive Headhunter Brief + Touch-Up Resumes ({len(matches)} Priority Matches)</h2>"
    html += "<p style='color:#555;'>Tailored <b>.docx resumes</b> (with your private contact header pre-filled) are attached below, ready to review and export to PDF.</p>"
    for m in matches:
        diff_items = ensure_list(m.get("touchup_diff", []))
        diff_html = "".join(f"<li>{d}</li>" for d in diff_items)
        html += f"""
        <div style='font-family: Arial, sans-serif; border: 1px solid #ddd; padding: 16px; border-radius: 8px; margin-bottom: 20px;'>
            <h3 style='margin:0 0 6px 0; color:#1a4e8a;'>[{m['score']}/100] {m['title']} - {m['company']}</h3>
            <p style='margin:0 0 10px 0; color:#555;'>Location: {m['location']} &nbsp;|&nbsp; <a href='{m['url']}'><b>Direct Application Link</b></a></p>
            <p><b>Strategic Fit:</b> {m.get('strategic_fit', '')}</p>
            <p><b>Company & Role Intel:</b> {m.get('company_intel', '')}</p>
            <p><b>Keywords / Gaps to Watch:</b> {m.get('missing_skills', '')}</p>
            <p><b>Resume Touch-Up Summary (Attached .docx):</b></p>
            <ul>{diff_html}</ul>
            <p style='background:#f4f8ff; padding:10px; border-left:4px solid #1a4e8a;'><b>LinkedIn DM Hook to Hiring Manager:</b><br><i>"{m.get('outreach_hook', '')}"</i></p>
        </div>
        """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Executive Brief + {len(matches)} Tailored Resumes Ready"
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
    print("No new matches >= 75 today.")
