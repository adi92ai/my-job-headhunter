import csv, json, re, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

EXISTING_FILE = "companies.csv"

verified = {}  # (ats, slug.lower()) -> {"company": ..., "ats": ..., "slug": ...}
try:
    with open(EXISTING_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            ats = r.get("ats", "").lower()
            slug = r.get("slug", "")
            comp = r.get("company", slug)
            if ats and slug:
                verified[(ats, slug.lower())] = {"company": comp, "ats": ats, "slug": slug}
except FileNotFoundError:
    pass

print(f"Loaded {len(verified)} existing verified boards from {EXISTING_FILE}.")

# 1. Fetch 4,500+ active companies from Y Combinator OSS API + public job aggregators
def fetch_directory_companies():
    companies = []
    # Y Combinator complete active company directory (4,500+ funded startups & unicorns)
    try:
        r = requests.get("https://yc-oss.github.io/api/companies/all.json", timeout=15)
        if r.status_code == 200:
            for c in r.json():
                if c.get("status") == "Active" and c.get("name"):
                    companies.append(c["name"].strip())
    except Exception:
        pass

    # Remotive & Arbeitnow public company directories
    for api_url, key in [
        ("https://remotive.com/api/remote-jobs?limit=500", "jobs"),
        ("https://www.arbeitnow.com/api/job-board-api", "data")
    ]:
        try:
            r = requests.get(api_url, timeout=12)
            if r.status_code == 200:
                for item in r.json().get(key, []):
                    cname = item.get("company_name") or item.get("company")
                    if cname:
                        companies.append(cname.strip())
        except Exception:
            pass

    return list(dict.fromkeys(companies))

# 2. High-value Indian Enterprises, GCCs, Unicorns, Banks & Global Tech
EXTRA_COMPANIES = [
    # Indian Unicorns, Fintechs, Consumer & SaaS
    "Swiggy", "Zomato", "Eternal", "Razorpay", "PhonePe", "CRED", "Zepto", "Blinkit",
    "Meesho", "Groww", "Zerodha", "Upstox", "Angel One", "Ola", "Ola Electric", "Paytm",
    "Freshworks", "Zoho", "Postman", "BrowserStack", "Chargebee", "Druva", "Icertis",
    "Uniphore", "Hasura", "Appsmith", "Sprinto", "Darwinbox", "LeadSquared", "Whatfix",
    "CleverTap", "MoEngage", "Innovaccer", "Zenoti", "HighRadius", "Keka", "Zeta",
    "Jupiter", "Fi Money", "Slice", "Navi", "Acko", "Digit Insurance", "Policybazaar",
    "PB Fintech", "Delhivery", "Shiprocket", "Udaan", "Lenskart", "Nykaa", "Purplle",
    "Mamaearth", "Honasa", "Urban Company", "Dream11", "Dream Sports", "Games24x7",
    "MPL", "Nazara", "InMobi", "Glance", "ShareChat", "Moj", "Dailyhunt", "VerSe",
    "Gupshup", "Yellow.ai", "Haptik", "Exotel", "Amagi", "Capillary", "Mindtickle",
    "Sirion", "FarEye", "Locus", "Bizongo", "Zetwerk", "OfBusiness", "Infra.Market",
    "Moglix", "Cars24", "Spinny", "CarDekho", "Droom", "upGrad", "Eruditus", "Scaler",
    "PhysicsWallah", "Vedantu", "Unacademy", "Curefit", "Cult.fit", "PharmEasy", "1mg",
    "Tata 1mg", "Pristyn Care", "HealthKart", "Pine Labs", "BharatPe", "Cashfree",
    "Juspay", "Easebuzz", "Setu", "Perfios", "Karza", "Signzy", "HyperVerge", "IDfy",
    "Bureau", "Sardine", "Observe.AI", "Kore.ai", "Moveworks", "Glean", "Sarvam AI",
    "Krutrim", "Pixxel", "Agnikul", "Skyroot", " Ather Energy", "Rapido", "Porter",
    "BlackBuck", "Xpressbees", "Shadowfax", "Dunzo", "BigBasket", "JioMart", "Tata Digital",
    "Tata Neu", "Croma", "Titan", "Reliance Retail", "Ajio", "Myntra", "Flipkart",
    "ClearTax", "Clear", "Khatabook", "OkCredit", "Vyapar", "Tally", "RazorpayX",
    "Open Financial", "Niyo", "FamPay", "Jar", "Smallcase", "INDmoney", "Kuvera",
    "CoinDCX", "CoinSwitch", "Mudrex", "Polygon", "Lumikai", "Peak XV", "Blume",
    "Info Edge", "Naukri", "99acres", "Jeevansathi", "Shiksha", "MakeMyTrip", "Goibibo",
    "EaseMyTrip", "Ixigo", "Yatra", "Cleartrip", "Oyo", "Treebo", "FabHotels",
    "BookMyShow", "District", "Hotstar", "JioCinema", "SonyLIV", "Zee5", "Gaana",
    "Spotify", "Netflix", "Prime Video", "Disney", "Warner Bros Discovery",
    # Major India GCCs, Consulting, BFSI & Enterprise Tech
    "McKinsey", "BCG", "Bain", "Accenture", "Deloitte", "PwC", "EY", "KPMG",
    "ZS Associates", "Mu Sigma", "Fractal", "Tiger Analytics", "LatentView", "Tredence",
    "Sigmoid", "MathCo", "Course5i", "Gramener", "Absolutdata", "Cartesian", "Ganit",
    "Bridgei2i", "Quantzig", "Analytics Vidhya", "Genpact", "EXL", "WNS", "Cognizant",
    "Infosys", "Wipro", "TCS", "HCLTech", "Tech Mahindra", "LTIMindtree", "Mphasis",
    "Persistent", "Coforge", "Birlasoft", "Cyient", "KPIT", "Tata Elxsi", "LTTS",
    "JPMorgan", "Goldman Sachs", "Morgan Stanley", "Bank of America", "Citigroup",
    "Wells Fargo", "Barclays", "HSBC", "Standard Chartered", "UBS", "Deutsche Bank",
    "BNP Paribas", "Societe Generale", "Credit Suisse", "Nomura", "Macquarie",
    "BlackRock", "Vanguard", "Fidelity", "State Street", "BNY Mellon", "Northern Trust",
    "Capital One", "American Express", "Visa", "Mastercard", "PayPal", "Intuit",
    "Block", "Square", "Affirm", "Klarna", "SoFi", "Robinhood", "Coinbase", "Kraken",
    "Chubb", "AIG", "MetLife", "Prudential", "Allianz", "AXA", "Munich Re", "Swiss Re",
    "UnitedHealth", "Optum", "Cigna", "Evernorth", "CVS Health", "Elevance Health",
    "Humana", "Centene", "Kaiser Permanente", "IQVIA", "Syneos Health", "ICON", "Parexel",
    "Novartis", "Roche", "Pfizer", "AstraZeneca", "Sanofi", "GSK", "Eli Lilly",
    "Bristol Myers Squibb", "Amgen", "Gilead", "Regeneron", "Biogen", "Moderna",
    "Medtronic", "Stryker", "Boston Scientific", "Abbott", "GE HealthCare", "Philips",
    "Siemens Healthineers", "Thermo Fisher", "Danaher", "Agilent", "Illumina",
    "Walmart", "Target", "Lowes", "Home Depot", "Best Buy", "Costco", "Kroger",
    "Nike", "Adidas", "Puma", "Lululemon", "Gap", "Levi Strauss", "PVH", "Tapestry",
    "PepsiCo", "Coca-Cola", "Unilever", "Procter & Gamble", "Nestle", "Mondelez",
    "Mars", "Kraft Heinz", "General Mills", "Kellanova", "Diageo", "AB InBev", "Heineken",
    "Shell", "BP", "Chevron", "ExxonMobil", "TotalEnergies", "Schlumberger", "SLB",
    "Halliburton", "Baker Hughes", "Schneider Electric", "Siemens", "ABB", "Honeywell",
    "3M", "Caterpillar", "John Deere", "Boeing", "Airbus", "GE Aerospace", "Rolls-Royce",
    "Eaton", "Emerson", "Rockwell Automation", "Johnson Controls", "Carrier", "Otis",
    "Bosch", "Continental", "ZF", "Valeo", "Aptiv", "Magna", "Cummins", "BorgWarner",
    "Maersk", "DHL", "FedEx", "UPS", "C.H. Robinson", "Flexport", "Expeditors",
    "NVIDIA", "AMD", "Intel", "Qualcomm", "Broadcom", "Texas Instruments", "Micron",
    "Applied Materials", "Lam Research", "KLA", "ASML", "Synopsys", "Cadence", "ARM",
    "NXP", "Infineon", "STMicroelectronics", "Analog Devices", "Marvell", "Western Digital",
    "Seagate", "NetApp", "Pure Storage", "Dell", "HP", "HPE", "Cisco", "Juniper",
    "Arista Networks", "Palo Alto Networks", "CrowdStrike", "Fortinet", "Check Point",
    "Zscaler", "Okta", "Cloudflare", "Akamai", "Fastly", "F5", "Imperva", "Proofpoint",
    "Mimecast", "Rapid7", "Tenable", "Qualys", "SailPoint", "CyberArk", "SentinelOne",
    "Wiz", "Snyk", "Netskope", "Rubrik", "Cohesity", "Veeam", "Commvault", "Nutanix",
    "Snowflake", "Databricks", "Confluent", "MongoDB", "Elastic", "Datadog", "Splunk",
    "Dynatrace", "New Relic", "AppDynamics", "Grafana", "HashiCorp", "GitLab", "GitHub",
    "Atlassian", "Asana", "Monday", "Notion", "Figma", "Canva", "Miro", "Airtable",
    "Smartsheet", "Box", "Dropbox", "DocuSign", "Zoom", "Twilio", "RingCentral",
    "Five9", "Genesys", "Zendesk", "Intercom", "Sprinklr", "HubSpot", "Salesforce",
    "Adobe", "Oracle", "SAP", "Workday", "ServiceNow", "Infor", "Epicor", "IFS",
    "Coupa", "Veeva", "Guidewire", "Duck Creek", "Toast", "Shopify", "Stripe", "Adyen",
    "Airbnb", "Uber", "Lyft", "DoorDash", "Instacart", "Expedia", "Booking", "Marriott",
    "Hilton", "Hyatt", "IHG", "Accor", "S&P Global", "Moodys", "Thomson Reuters",
    "FactSet", "Bloomberg", "MSCI", "Nasdaq", "London Stock Exchange", "Experian",
    "Equifax", "TransUnion", "Nielsen", "NielsenIQ", "Kantar", "Ipsos", "Gartner", "Forrester"
]

def name_to_slugs(name):
    clean = re.sub(r"\(.*?\)", "", name).strip().lower()
    # Remove common corporate suffixes
    clean = re.sub(r"\b(inc|llc|ltd|limited|corp|corporation|technologies|technology|software|india|global|group|holdings|labs|ai)\b", "", clean).strip()
    s1 = re.sub(r"[^a-z0-9]+", "", clean)
    s2 = re.sub(r"[^a-z0-9]+", "-", clean).strip("-")
    raw_full = re.sub(r"[^a-z0-9]+", "", name.lower())
    out = set()
    for s in (s1, s2, raw_full):
        if len(s) >= 2:
            out.add(s)
    return list(out)

dir_companies = fetch_directory_companies()
all_names = list(dict.fromkeys(EXTRA_COMPANIES + dir_companies))
print(f"Collected {len(all_names)} company names ({len(dir_companies)} from YC/public directories + {len(EXTRA_COMPANIES)} curated).")

# Build candidate (company, ats, slug) probes
candidates = []
seen_keys = set(verified.keys())

for comp in all_names:
    slugs = name_to_slugs(comp)
    for slug in slugs:
        for ats in ("greenhouse", "lever", "ashby", "smartrecruiters", "workable"):
            # SmartRecruiters often uses TitleCase slug
            probe_slug = slug.capitalize() if ats == "smartrecruiters" else slug
            k = (ats, probe_slug.lower())
            if k not in seen_keys:
                seen_keys.add(k)
                candidates.append((comp, ats, probe_slug))

# Add multi-tenant Workday probes for major enterprises
WORKDAY_TENANTS = [
    ("Salesforce", "salesforce", ["wd12"], ["External_Career_Site"]),
    ("Adobe", "adobe", ["wd5"], ["external_experienced"]),
    ("NVIDIA", "nvidia", ["wd5"], ["NVIDIAExternalCareerSite"]),
    ("Cisco", "cisco", ["wd5"], ["Cisco_Careers"]),
    ("Intel", "intel", ["wd1"], ["External"]),
    ("Qualcomm", "qualcomm", ["wd5"], ["External"]),
    ("Broadcom", "broadcom", ["wd1"], ["External_Career"]),
    ("PayPal", "paypal", ["wd1"], ["jobs"]),
    ("Mastercard", "mastercard", ["wd1"], ["CorporateCareers"]),
    ("Visa", "visa", ["wd5"], ["Visa_Careers"]),
    ("American Express", "aexp", ["wd5"], ["American_Express_Careers"]),
    ("Goldman Sachs", "gs", ["wd5"], ["GS_Careers"]),
    ("Morgan Stanley", "ms", ["wd5"], ["External"]),
    ("Wells Fargo", "wf", ["wd1"], ["WellsFargoJobs"]),
    ("Target", "target", ["wd5"], ["targetcareers"]),
    ("Walmart", "walmart", ["wd5"], ["WalmartExternal"]),
    ("Lowes", "lowes", ["wd5"], ["LWS_External_Site"]),
    ("AstraZeneca", "astrazeneca", ["wd3"], ["Careers"]),
    ("Novartis", "novartis", ["wd3"], ["Novartis_Careers"]),
    ("Sanofi", "sanofi", ["wd3"], ["SanofiCareers"]),
    ("Schneider Electric", "schneiderelectric", ["wd3"], ["External"]),
    ("Siemens", "siemens", ["wd3"], ["External"]),
    ("Micron", "micron", ["wd1"], ["External"]),
    ("Applied Materials", "amat", ["wd1"], ["External"]),
    ("Palo Alto Networks", "paloaltonetworks", ["wd1"], ["External"]),
    ("CrowdStrike", "crowdstrikecareers", ["wd5"], ["crowdstrikecareers"]),
    ("Intuit", "intuit", ["wd1"], ["Intuit_Careers"]),
    ("Autodesk", "autodesk", ["wd1"], ["Ext"]),
    ("Dell", "dell", ["wd1"], ["External"]),
    ("HP", "hp", ["wd5"], ["ExternalCareerSite"]),
    ("Fidelity", "fmr", ["wd1"], ["FidelityCareers"]),
    ("Standard Chartered", "scb", ["wd3"], ["SCB_Careers"]),
    ("HSBC", "hsbc", ["wd3"], ["HSBC_Careers"]),
    ("Barclays", "barclays", ["wd3"], ["External_Career_Site_Barclays"]),
    ("UBS", "ubs", ["wd3"], ["UBS_Careers"]),
    ("Deloitte", "deloitte", ["wd1"], ["deloitte"]),
    ("PwC", "pwc", ["wd3"], ["Global_Experienced_Careers"]),
    ("EY", "ey", ["wd1"], ["EY_Careers"]),
    ("S&P Global", "spgi", ["wd5"], ["SPGI_Careers"]),
    ("Thomson Reuters", "thomsonreuters", ["wd5"], ["External_Career_Site"]),
    ("FactSet", "factset", ["wd1"], ["FactSetCareers"]),
    ("Uber", "uber", ["wd5"], ["Uber_Careers"]),
    ("Expedia", "expedia", ["wd108"], ["search"]),
    ("Booking", "booking", ["wd3"], ["Booking_Careers"]),
    ("Marriott", "marriott", ["wd5"], ["MarriottCareers"]),
    ("Informatica", "informatica", ["wd1"], ["InformaticaCareers"]),
    ("Zoom", "zoom", ["wd5"], ["Zoom"]),
    ("Genesys", "genesys", ["wd1"], ["Genesys"]),
    ("GoDaddy", "godaddy", ["wd1"], ["GoDaddyCareers"]),
    ("Akamai", "akamai", ["wd1"], ["Ext_Career"]),
    ("Fortinet", "fortinet", ["wd1"], ["Fortinet_Careers"]),
    ("NetApp", "netapp", ["wd1"], ["NetAppCareerSite"]),
    ("AMD", "amd", ["wd5"], ["AMD"]),
    ("ARM", "arm", ["wd3"], ["Arm_Careers"]),
    ("Synopsys", "synopsys", ["wd1"], ["Synopsys"]),
    ("Cadence", "cadence", ["wd1"], ["External_Careers"]),
    ("Texas Instruments", "ti", ["wd1"], ["External"]),
    ("Analog Devices", "analogdevices", ["wd1"], ["External"]),
    ("Philips", "philips", ["wd3"], ["jobs-and-careers"]),
    ("GE HealthCare", "gehealthcare", ["wd5"], ["GEHC_ExternalSite"]),
    ("Medtronic", "medtronic", ["wd1"], ["MedtronicCareers"]),
    ("Abbott", "abbott", ["wd5"], ["abbottcareers"]),
    ("Roche", "roche", ["wd3"], ["roche-ext"]),
    ("Pfizer", "pfizer", ["wd1"], ["PfizerCareers"]),
    ("GSK", "gsk", ["wd5"], ["GSKCareers"]),
    ("Eli Lilly", "lilly", ["wd5"], ["Lilly"]),
    ("Optum / UHG", "uhg", ["wd5"], ["UHG"]),
    ("Cigna", "cigna", ["wd5"], ["cignacareers"]),
    ("BlackRock", "blackrock", ["wd1"], ["BlackRock_Professional"]),
    ("Vanguard", "vanguard", ["wd5"], ["vanguard_external"]),
    ("State Street", "statestreet", ["wd1"], ["Global"]),
    ("BNY Mellon", "bnymellon", ["wd1"], ["BNYMellon"]),
    ("Nasdaq", "nasdaq", ["wd1"], ["Global_External_Site"]),
    ("ADP", "adp", ["wd1"], ["ADP"]),
    ("UKG", "ukg", ["wd1"], ["UKG_External"]),
    ("SAP", "sap", ["wd3"], ["SAP_Careers"]),
    ("IQVIA", "iqvia", ["wd1"], ["IQVIACareers"]),
    ("Accenture", "accenture", ["wd3"], ["AccentureCareers"]),
    ("Cognizant", "cognizant", ["wd1"], ["Cognizant_Careers"]),
    ("Infosys", "infosys", ["wd3"], ["Infosys_Careers"]),
    ("Wipro", "wipro", ["wd3"], ["Wipro_Careers"]),
    ("Genpact", "genpact", ["wd1"], ["Genpact"]),
    ("EXL", "exl", ["wd1"], ["EXL"]),
    ("WNS", "wns", ["wd3"], ["WNS"]),
    ("ZS Associates", "zs", ["wd1"], ["ZS_Careers"]),
    ("PepsiCo", "pepsico", ["wd5"], ["PepsiCo_Jobs"]),
    ("Unilever", "unilever", ["wd3"], ["Unilever_Experienced_Professionals"]),
    ("Nestle", "nestle", ["wd3"], ["Nestle"]),
    ("Mondelez", "mdlz", ["wd3"], ["External"]),
    ("Nike", "nike", ["wd1"], ["nke"]),
    ("Adidas", "adidas", ["wd3"], ["adidas"]),
    ("Shell", "shell", ["wd3"], ["ShellCareers"]),
    ("BP", "bp", ["wd3"], ["bpCareers"]),
    ("Honeywell", "honeywell", ["wd5"], ["Honeywell"]),
    ("Caterpillar", "cat", ["wd1"], ["CaterpillarCareers"]),
    ("John Deere", "johndeere", ["wd1"], ["John-Deere-Careers"]),
    ("Boeing", "boeing", ["wd1"], ["EXTERNAL_CAREERS"]),
    ("Airbus", "airbus", ["wd3"], ["Airbus"]),
    ("Eaton", "eaton", ["wd1"], ["EatonCareers"]),
    ("Emerson", "emerson", ["wd5"], ["EmersonCareers"]),
    ("Maersk", "maersk", ["wd3"], ["Maersk_Careers"]),
    ("UPS", "ups", ["wd5"], ["Search"])
]

for comp, tenant, wds, sites in WORKDAY_TENANTS:
    for wd in wds:
        for site in sites:
            slug = f"{tenant}|{wd}|{site}"
            k = ("workday", slug.lower())
            if k not in seen_keys:
                seen_keys.add(k)
                candidates.append((comp, "workday", slug))

def verify_board(item):
    comp, ats, slug = item
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=5)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}?limit=1", timeout=5)
            if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=5)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "smartrecruiters":
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1", timeout=5)
            if r.status_code == 200 and len(r.json().get("content", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=5)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "workday":
            parts = slug.split("|")
            if len(parts) == 3:
                tenant, wd_num, site = parts
                wd_url = f"https://{tenant}.{wd_num}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
                r = requests.post(wd_url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, headers={"Content-Type": "application/json"}, timeout=7)
                if r.status_code == 200 and r.json().get("total", 0) > 0:
                    return {"company": comp, "ats": ats, "slug": slug}
    except Exception:
        pass
    return None

print(f"Probing {len(candidates)} candidate ATS endpoints across 60 parallel workers...")
t0 = time.time()
added_count = 0

with ThreadPoolExecutor(max_workers=60) as pool:
    futures = [pool.submit(verify_board, item) for item in candidates]
    for fut in as_completed(futures):
        res = fut.result()
        if res:
            verified[(res["ats"], res["slug"].lower())] = res
            added_count += 1

final_rows = sorted(verified.values(), key=lambda x: x["company"].lower())
with open(EXISTING_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["company", "ats", "slug"])
    writer.writeheader()
    writer.writerows(final_rows)

print(f"Discovery complete in {time.time() - t0:.1f}s! Added {added_count} new active boards -> Total verified boards: {len(final_rows)}")
