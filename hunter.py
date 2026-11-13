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
    # Replace non-breaking hyphens (\u2011), figure dashes (\u2012), minus signs, and non-breaking spaces
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

def fetch_jobs(row):
    company = row["company"].strip()
    ats = row["ats"].strip().lower()
    slug = row["slug"].strip()
    jobs = []
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=8).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"gh_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", {}).get("name", ""),
                    "url": j["absolute_url"], "desc": clean_html(j.get("content", ""))
                })
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}", timeout=8).json()
            if isinstance(r, list):
                for j in r:
                    jobs.append({
                        "id": f"lv_{j['id']}", "company": company, "title": j["text"],
                        "location": j.get("categories", {}).get("location", ""),
                        "url": j["hostedUrl"], "desc": clean_html(j.get("descriptionPlain", ""))
                    })
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=8).json()
            for j in r.get("jobs", []):
                jobs.append({
                    "id": f"ab_{j['id']}", "company": company, "title": j["title"],
                    "location": j.get("location", ""),
                    "url": j["jobUrl"], "desc": clean_html(j.get("descriptionPlain", ""))
                })
        elif ats == "smartrecruiters":
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100", timeout=8).json()
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
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=8).json()
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
                r = requests.post(wd_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10).json()
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

def call_nvidia(prompt, model="mistralai/mistral-large-4-1t-a52b", timeout=90):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an elite executive career strategist. Return ONLY valid JSON with standard ASCII hyphens (-), never non-breaking hyphens."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 8192
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
    raise Runtime
