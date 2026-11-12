import csv, re, requests

# Curated high-priority India GCCs, Unicorns & Global SaaS across 6 ATS platforms
CURATED = [
    # --- GREENHOUSE ---
    ("Stripe", "greenhouse", "stripe"), ("Figma", "greenhouse", "figma"),
    ("Databricks", "greenhouse", "databricks"), ("Coinbase", "greenhouse", "coinbase"),
    ("Airbnb", "greenhouse", "airbnb"), ("Cloudflare", "greenhouse", "cloudflare"),
    ("Rubrik", "greenhouse", "rubrik"), ("Cohesity", "greenhouse", "cohesity"),
    ("Nutanix", "greenhouse", "nutanix"), ("Zscaler", "greenhouse", "zscaler"),
    ("Okta", "greenhouse", "okta"), ("Twilio", "greenhouse", "twilio"),
    ("MongoDB", "greenhouse", "mongodb"), ("Elastic", "greenhouse", "elastic"),
    ("GitLab", "greenhouse", "gitlab"), ("HashiCorp", "greenhouse", "hashicorp"),
    ("Confluent", "greenhouse", "confluent"), ("Datadog", "greenhouse", "datadog"),
    ("Toast", "greenhouse", "toast"), ("Brex", "greenhouse", "brex"),
    ("Rippling", "greenhouse", "rippling"), ("Gusto", "greenhouse", "gusto"),
    ("Plaid", "greenhouse", "plaid"), ("Robinhood", "greenhouse", "robinhood"),
    ("Affirm", "greenhouse", "affirm"), ("Chime", "greenhouse", "chime"),
    ("Wise", "greenhouse", "wise"), ("Revolut", "greenhouse", "revolut"),
    ("Adyen", "greenhouse", "adyen"), ("Razorpay", "greenhouse", "razorpay"),
    ("PhonePe", "greenhouse", "phonepe"), ("CRED", "greenhouse", "cred"),
    ("Groww", "greenhouse", "groww"), ("Meesho", "greenhouse", "meesho"),
    ("Swiggy", "greenhouse", "swiggy"), ("Zepto", "greenhouse", "zepto"),
    ("Postman", "greenhouse", "postman"), ("BrowserStack", "greenhouse", "browserstack"),
    ("Druva", "greenhouse", "druva"), ("Icertis", "greenhouse", "icertis"),
    ("Chargebee", "greenhouse", "chargebee"), ("Freshworks", "greenhouse", "freshworks"),
    ("CleverTap", "greenhouse", "clevertap"), ("MoEngage", "greenhouse", "moengage"),
    ("LeadSquared", "greenhouse", "leadsquared"), ("Gupshup", "greenhouse", "gupshup"),
    ("Innovaccer", "greenhouse", "innovaccer"), ("Whatfix", "greenhouse", "whatfix"),
    ("Mindtickle", "greenhouse", "mindtickle"), ("Hasura", "greenhouse", "hasura"),
    ("Apollo.io", "greenhouse", "apolloio"), ("Deel", "greenhouse", "deel"),
    ("Remote", "greenhouse", "remote"), ("Coursera", "greenhouse", "coursera"),
    ("Duolingo", "greenhouse", "duolingo"), ("Pinterest", "greenhouse", "pinterest"),
    ("Reddit", "greenhouse", "reddit"), ("Snap", "greenhouse", "snap"),
    ("DoorDash", "greenhouse", "doordash"), ("Instacart", "greenhouse", "instacart"),
    ("Lyft", "greenhouse", "lyft"), ("Wayfair", "greenhouse", "wayfair"),
    ("Booking.com", "greenhouse", "booking"), ("Tripadvisor", "greenhouse", "tripadvisor"),
    ("Expedia", "greenhouse", "expedia"), ("Agoda", "greenhouse", "agoda"),
    ("Grab", "greenhouse", "grab"), ("GoTo", "greenhouse", "goto"),
    ("Coupang", "greenhouse", "coupang"), ("Sea", "greenhouse", "sea"),
    ("Epic Games", "greenhouse", "epicgames"), ("Unity", "greenhouse", "unity"),
    ("Roblox", "greenhouse", "roblox"), ("Electronic Arts", "greenhouse", "ea"),
    ("Amplitude", "greenhouse", "amplitude"), ("Mixpanel", "greenhouse", "mixpanel"),
    ("Segment", "greenhouse", "segment"), ("Braze", "greenhouse", "braze"),
    ("Klaviyo", "greenhouse", "klaviyo"), ("HubSpot", "greenhouse", "hubspot"),
    ("Asana", "greenhouse", "asana"), ("Monday.com", "greenhouse", "mondaydotcom"),
    ("DocuSign", "greenhouse", "docusign"), ("Dropbox", "greenhouse", "dropbox"),
    ("Box", "greenhouse", "box"), ("Intercom", "greenhouse", "intercom"),
    ("Zendesk", "greenhouse", "zendesk"), ("Grammarly", "greenhouse", "grammarly"),
    ("Canva", "greenhouse", "canva"), ("Discord", "greenhouse", "discord"),
    # --- LEVER ---
    ("Atlassian", "lever", "atlassian"), ("Netflix", "lever", "netflix"),
    ("Spotify", "lever", "spotify"), ("Airtable", "lever", "airtable"),
    ("Miro", "lever", "miro"), ("Wealthfront", "lever", "wealthfront"),
    ("Upstart", "lever", "upstart"), ("Paytm", "lever", "paytm"),
    ("Ola", "lever", "ola"), ("Udaan", "lever", "udaan"),
    ("ShareChat", "lever", "sharechat"), ("Dream11", "lever", "dream11"),
    ("Unacademy", "lever", "unacademy"), ("UpGrad", "lever", "upgrad"),
    ("Licious", "lever", "licious"), ("Urban Company", "lever", "urbancompany"),
    ("Nykaa", "lever", "nykaa"), ("Pluralsight", "lever", "pluralsight"),
    # --- ASHBY ---
    ("OpenAI", "ashby", "openai"), ("Linear", "ashby", "linear"),
    ("Notion", "ashby", "notion"), ("Vercel", "ashby", "vercel"),
    ("Supabase", "ashby", "supabase"), ("Perplexity", "ashby", "perplexity"),
    ("Cohere", "ashby", "cohere"), ("ElevenLabs", "ashby", "elevenlabs"),
    ("Ramp", "ashby", "ramp"), ("Mercury", "ashby", "mercury"),
    ("Vanta", "ashby", "vanta"), ("Drata", "ashby", "drata"),
    # --- SMARTRECRUITERS (Major India GCCs) ---
    ("Visa", "smartrecruiters", "Visa"), ("Bosch", "smartrecruiters", "BoschGroup"),
    ("S&P Global", "smartrecruiters", "SPGlobal"), ("Western Digital", "smartrecruiters", "WesternDigital"),
    ("Publicis Sapient", "smartrecruiters", "PublicisSapient"), ("Ubisoft", "smartrecruiters", "Ubisoft2"),
    ("Avery Dennison", "smartrecruiters", "AveryDennison"), ("Eurofins", "smartrecruiters", "Eurofins"),
    ("Sanofi", "smartrecruiters", "Sanofi"), ("NielsenIQ", "smartrecruiters", "NielsenIQ"),
    ("Experian", "smartrecruiters", "Experian"), ("Alstom", "smartrecruiters", "Alstom"),
    ("KONE", "smartrecruiters", "KONE"), ("Dentsu", "smartrecruiters", "Dentsu"),
    # --- WORKABLE ---
    ("DevRev", "workable", "devrev"), ("Khatabook", "workable", "khatabook"),
    ("Darwinbox", "workable", "darwinbox"), ("Sprinto", "workable", "sprinto"),
    ("Hevo Data", "workable", "hevo-data"),
    # --- WORKDAY (Format: tenant|wd_instance|site_name) ---
    ("Salesforce", "workday", "salesforce|wd12|External_Career_Site"),
    ("Adobe", "workday", "adobe|wd5|external_experienced"),
    ("NVIDIA", "workday", "nvidia|wd5|NVIDIAExternalCareerSite"),
    ("Walmart Global Tech", "workday", "walmart|wd5|WalmartExternal"),
    ("Target India", "workday", "target|wd5|targetcareers"),
    ("Intuit", "workday", "intuit|wd1|Intuit_External"),
    ("VMware / Broadcom", "workday", "broadcom|wd1|External_Career"),
    ("Mastercard", "workday", "mastercard|wd1|CorporateCareers"),
    ("PayPal", "workday", "paypal|wd1|jobs"),
    ("Cisco", "workday", "cisco|wd5|Cisco_Careers"),
    ("Fidelity India", "workday", "fmr|wd1|FidelityCareers"),
    ("Wells Fargo India", "workday", "wf|wd1|WellsFargoJobs"),
    ("Barclays", "workday", "barclays|wd3|External_Career_Site_Barclays"),
    ("Deutsche Bank", "workday", "db|wd3|DBWebsite"),
    ("AstraZeneca", "workday", "astrazeneca|wd3|Careers"),
    ("Novartis", "workday", "novartis|wd3|Novartis_Careers"),
    ("Schneider Electric", "workday", "schneiderelectric|wd3|SE_Careers")
]

# Public open-source ATS directories to auto-harvest up to 1,000 companies
SOURCES = [
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/README.md",
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
    "https://raw.githubusercontent.com/cvrve/Summer2025-Internships/main/README.md"
]

companies = {(ats, slug.lower()): (name.strip(), ats, slug) for name, ats, slug in CURATED}

for url in SOURCES:
    try:
        text = requests.get(url, timeout=15).text
        for slug in re.findall(r"boards\.greenhouse\.io/([a-zA-Z0-9_-]+)", text):
            companies.setdefault(("greenhouse", slug.lower()), (slug.capitalize(), "greenhouse", slug))
        for slug in re.findall(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)", text):
            companies.setdefault(("lever", slug.lower()), (slug.capitalize(), "lever", slug))
        for slug in re.findall(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)", text):
            companies.setdefault(("ashby", slug.lower()), (slug.capitalize(), "ashby", slug))
        for slug in re.findall(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)", text):
            companies.setdefault(("smartrecruiters", slug.lower()), (slug.capitalize(), "smartrecruiters", slug))
    except Exception as e:
        print(f"Source skipped: {e}")

final_list = list(companies.values())[:1000]

with open("companies.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["company", "ats", "slug"])
    writer.writerows(final_list)

print(f"Updated companies.csv with {len(final_list)} unique companies across 6 ATS platforms!")
