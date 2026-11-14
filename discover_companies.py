import csv, json, re, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

EXISTING_FILE = "companies.csv"

# 1. Load any existing verified companies so nothing is ever lost
verified = {}  # key: (ats, slug.lower()) -> {"company": ..., "ats": ..., "slug": ...}
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

# 2. High-value India GCCs, Unicorns, SaaS, Fintech & Global Enterprise Workday/ATS targets
EXPLICIT_TARGETS = [
    # Workday (tenant|wd_num|site)
    ("Salesforce", "workday", "salesforce|wd12|External_Career_Site"),
    ("Adobe", "workday", "adobe|wd5|external_experienced"),
    ("NVIDIA", "workday", "nvidia|wd5|NVIDIAExternalCareerSite"),
    ("Cisco", "workday", "cisco|wd5|Cisco_Careers"),
    ("Intel", "workday", "intel|wd1|External"),
    ("Qualcomm", "workday", "qualcomm|wd5|External"),
    ("VMware / Broadcom", "workday", "broadcom|wd1|External_Career"),
    ("PayPal", "workday", "paypal|wd1|jobs"),
    ("Mastercard", "workday", "mastercard|wd1|CorporateCareers"),
    ("Visa", "workday", "visa|wd5|Visa_Careers"),
    ("American Express", "workday", "aexp|wd5|American_Express_Careers"),
    ("Goldman Sachs", "workday", "gs|wd5|GS_Careers"),
    ("Morgan Stanley", "workday", "ms|wd5|External"),
    ("Wells Fargo", "workday", "wf|wd1|WellsFargoJobs"),
    ("Bank of America", "workday", "ghr|wd1|Lateral-US"),
    ("Target", "workday", "target|wd5|targetcareers"),
    ("Walmart Global Tech", "workday", "walmart|wd5|WalmartExternal"),
    ("Lowes", "workday", "lowes|wd5|LWS_External_Site"),
    ("AstraZeneca", "workday", "astrazeneca|wd3|Careers"),
    ("Novartis", "workday", "novartis|wd3|Novartis_Careers"),
    ("Sanofi", "workday", "sanofi|wd3|SanofiCareers"),
    ("Schneider Electric", "workday", "schneiderelectric|wd3|External"),
    ("Siemens", "workday", "siemens|wd3|External"),
    ("Micron", "workday", "micron|wd1|External"),
    ("Applied Materials", "workday", "amat|wd1|External"),
    ("Palo Alto Networks", "workday", "paloaltonetworks|wd1|External"),
    ("CrowdStrike", "workday", "crowdstrikecareers|wd5|crowdstrikecareers"),
    ("Workday", "workday", "workday|wd5|Workday"),
    ("Intuit", "workday", "intuit|wd1|Intuit_Careers"),
    ("Autodesk", "workday", "autodesk|wd1|Ext"),
    ("HP", "workday", "hp|wd5|ExternalCareerSite"),
    ("Dell", "workday", "dell|wd1|External"),
    ("Equinix", "workday", "equinix|wd1|External"),
    ("Fidelity Investments", "workday", "fmr|wd1|FidelityCareers"),
    ("Standard Chartered", "workday", "scb|wd3|SCB_Careers"),
    ("HSBC", "workday", "hsbc|wd3|HSBC_Careers"),
    ("Barclays", "workday", "barclays|wd3|External_Career_Site_Barclays"),
    ("UBS", "workday", "ubs|wd3|UBS_Careers"),
    ("Deloitte", "workday", "deloitte|wd1|deloitte"),
    ("PwC", "workday", "pwc|wd3|Global_Experienced_Careers"),
    ("EY", "workday", "ey|wd1|EY_Careers"),
    ("S&P Global", "workday", "spgi|wd5|SPGI_Careers"),
    ("Moodys", "workday", "moodys|wd5|Moodys"),
    ("Thomson Reuters", "workday", "thomsonreuters|wd5|External_Career_Site"),
    ("FactSet", "workday", "factset|wd1|FactSetCareers"),
    ("Zebra Technologies", "workday", "zebra|wd1|zebra"),
    ("Expedia", "workday", "expedia|wd108|search"),
    ("Booking Holdings", "workday", "booking|wd3|Booking_Careers"),
    ("Marriott", "workday", "marriott|wd5|MarriottCareers"),
    ("Uber", "workday", "uber|wd5|Uber_Careers"),
    # India Unicorns & High-Growth Tech
    ("Swiggy", "lever", "swiggy"),
    ("Zomato", "lever", "zomato"),
    ("Razorpay", "greenhouse", "razorpay"),
    ("PhonePe", "greenhouse", "phonepe"),
    ("CRED", "lever", "cred"),
    ("Zepto", "lever", "zepto"),
    ("Meesho", "lever", "meesho"),
    ("Groww", "lever", "groww"),
    ("Flipkart", "lever", "flipkart"),
    ("Ola", "lever", "olacabs"),
    ("Paytm", "lever", "paytm"),
    ("Freshworks", "smartrecruiters", "Freshworks"),
    ("Postman", "greenhouse", "postman"),
    ("BrowserStack", "greenhouse", "browserstack"),
    ("Chargebee", "greenhouse", "chargebee"),
    ("Druva", "greenhouse", "druva"),
    ("Icertis", "greenhouse", "icertis"),
    ("Uniphore", "greenhouse", "uniphore"),
    ("Hasura", "ashby", "hasura"),
    ("Appsmith", "ashby", "appsmith"),
    ("Sprinto", "ashby", "sprinto"),
    ("Darwinbox", "lever", "darwinbox"),
    ("LeadSquared", "lever", "leadsquared"),
    ("Whatfix", "greenhouse", "whatfix"),
    ("CleverTap", "lever", "clevertap"),
    ("MoEngage", "lever", "moengage"),
    ("Innovaccer", "lever", "innovaccer"),
    ("Zenoti", "greenhouse", "zenoti"),
    ("HighRadius", "greenhouse", "highradius"),
    ("Keka", "lever", "keka"),
    ("Zeta", "lever", "zeta"),
    ("Jupiter", "lever", "jupiter"),
    ("Fi Money", "lever", "epifi"),
    ("Slice", "lever", "sliceit"),
    ("Navi", "lever", "navi"),
    ("Acko", "lever", "acko"),
    ("Digit Insurance", "lever", "godigit"),
    ("Policybazaar", "lever", "policybazaar"),
    ("Delhivery", "lever", "delhivery"),
    ("Shiprocket", "lever", "shiprocket"),
    ("Udaan", "lever", "udaan"),
    ("Lenskart", "lever", "lenskart"),
    ("Nykaa", "lever", "nykaa"),
    ("Urban Company", "lever", "urbancompany"),
    ("Dream11", "lever", "dream11"),
    ("Games24x7", "lever", "games24x7"),
    ("MPL", "lever", "mpl"),
    ("InMobi", "lever", "inmobi"),
    ("Glance", "lever", "glance"),
    ("ShareChat", "lever", "sharechat"),
    ("Gupshup", "lever", "gupshup"),
    ("Yellow.ai", "lever", "yellowai"),
    ("Haptik", "lever", "haptik"),
    ("Exotel", "lever", "exotel"),
    ("Amagi", "lever", "amagi"),
    ("Capillary", "lever", "capillarytech"),
    ("Mindtickle", "greenhouse", "mindtickle"),
    ("Sirion", "greenhouse", "sirionlabs"),
    ("FarEye", "lever", "fareye"),
    ("Locus", "lever", "locus"),
    ("Bizongo", "lever", "bizongo"),
    ("Zetwerk", "lever", "zetwerk"),
    ("OfBusiness", "lever", "ofbusiness"),
    ("Infra.Market", "lever", "inframarket"),
    ("Cars24", "lever", "cars24"),
    ("Spinny", "lever", "spinny"),
    ("CarDekho", "lever", "cardekho"),
    ("upGrad", "lever", "upgrad"),
    ("Eruditus", "lever", "eruditus"),
    ("Scaler", "lever", "scaler"),
    ("PhysicsWallah", "lever", "physicswallah"),
    ("Curefit", "lever", "curefit"),
    ("PharmEasy", "lever", "pharmeasy"),
    ("1mg", "lever", "1mg"),
    ("Pristyn Care", "lever", "pristyncare"),
    ("Pine Labs", "lever", "pinelabs"),
    ("BharatPe", "lever", "bharatpe"),
    ("Cashfree", "lever", "cashfree"),
    ("Juspay", "lever", "juspay"),
    ("Easebuzz", "lever", "easebuzz"),
    ("Setu", "lever", "setu"),
    ("Perfios", "lever", "perfios"),
    ("Karza", "lever", "karza"),
    ("Signzy", "lever", "signzy"),
    ("HyperVerge", "lever", "hyperverge"),
    ("IDfy", "lever", "idfy"),
    ("Bureau", "ashby", "bureau"),
    ("Sardine", "ashby", "sardine"),
    ("Observe.AI", "greenhouse", "observeai"),
    ("Kore.ai", "greenhouse", "koreai"),
    ("Moveworks", "greenhouse", "moveworks"),
    ("Glean", "greenhouse", "glean"),
    ("Rubrik", "greenhouse", "rubrik"),
    ("Cohesity", "greenhouse", "cohesity"),
    ("Nutanix", "greenhouse", "nutanix"),
    ("Snowflake", "ashby", "snowflake"),
    ("Databricks", "greenhouse", "databricks"),
    ("Confluent", "ashby", "confluent"),
    ("MongoDB", "greenhouse", "mongodb"),
    ("Elastic", "greenhouse", "elastic"),
    ("Datadog", "greenhouse", "datadog"),
    ("Cloudflare", "greenhouse", "cloudflare"),
    ("Okta", "greenhouse", "okta"),
    ("Zscaler", "greenhouse", "zscaler"),
    ("SentinelOne", "greenhouse", "sentinelone"),
    ("Netskop", "greenhouse", "netskope"),
    ("Illumio", "greenhouse", "illumio"),
    ("Wiz", "greenhouse", "wiz"),
    ("Snyk", "greenhouse", "snyk"),
    ("HashiCorp", "greenhouse", "hashicorp"),
    ("GitLab", "greenhouse", "gitlab"),
    ("Atlassian", "lever", "atlassian"),
    ("Asana", "greenhouse", "asana"),
    ("Monday.com", "greenhouse", "mondaydotcom"),
    ("Notion", "ashby", "notion"),
    ("Figma", "greenhouse", "figma"),
    ("Canva", "lever", "canva"),
    ("Miro", "greenhouse", "miro"),
    ("Airtable", "greenhouse", "airtable"),
    ("HubSpot", "greenhouse", "hubspot"),
    ("Amplitude", "greenhouse", "amplitude"),
    ("Mixpanel", "greenhouse", "mixpanel"),
    ("Segment", "greenhouse", "segment"),
    ("Braze", "greenhouse", "braze"),
    ("Contentful", "greenhouse", "contentful"),
    ("Twilio", "greenhouse", "twilio"),
    ("Stripe", "greenhouse", "stripe"),
    ("Adyen", "greenhouse", "adyen"),
    ("Wise", "smartrecruiters", "Wise"),
    ("Revolut", "lever", "revolut"),
    ("Plaid", "lever", "plaid"),
    ("Brex", "greenhouse", "brex"),
    ("Ramp", "ashby", "ramp"),
    ("Deel", "ashby", "deel"),
    ("Rippling", "ashby", "rippling"),
    ("Remote.com", "greenhouse", "remotecom"),
    ("Oyster", "ashby", "oyster"),
    ("Gusto", "greenhouse", "gusto"),
    ("Toast", "greenhouse", "toast"),
    ("DoorDash", "greenhouse", "doordash"),
    ("Instacart", "greenhouse", "instacart"),
    ("Airbnb", "greenhouse", "airbnb"),
    ("Pinterest", "greenhouse", "pinterest"),
    ("Reddit", "greenhouse", "reddit"),
    ("Discord", "greenhouse", "discord"),
    ("Roblox", "greenhouse", "roblox"),
    ("Unity", "greenhouse", "unity3d"),
    ("Epic Games", "greenhouse", "epicgames"),
    ("OpenAI", "ashby", "openai"),
    ("Anthropic", "greenhouse", "anthropic"),
    ("Perplexity", "ashby", "perplexity"),
    ("Cohere", "ashby", "cohere"),
    ("Scale AI", "greenhouse", "scaleai"),
    ("Hugging Face", "ashby", "huggingface"),
    ("Together AI", "ashby", "togetherai"),
    ("ElevenLabs", "ashby", "elevenlabs"),
    ("Cursor / Anysphere", "ashby", "anysphere"),
    ("Vercel", "greenhouse", "vercel"),
    ("Supabase", "ashby", "supabase"),
    ("Linear", "ashby", "linear"),
    ("Retool", "greenhouse", "retool"),
    ("Temporal", "ashby", "temporal"),
    ("ClickHouse", "ashby", "clickhouse"),
    ("Grafana Labs", "greenhouse", "grafanalabs"),
    ("Sentry", "greenhouse", "sentry"),
    ("LaunchDarkly", "greenhouse", "launchdarkly"),
    ("PagerDuty", "greenhouse", "pagerduty"),
    ("New Relic", "greenhouse", "newrelic"),
    ("Dynatrace", "smartrecruiters", "Dynatrace"),
    ("UiPath", "greenhouse", "uipath"),
    ("Automation Anywhere", "greenhouse", "automationanywhere"),
    ("Celonis", "greenhouse", "celonis"),
    ("DataRobot", "greenhouse", "datarobot"),
    ("Dataiku", "greenhouse", "dataiku"),
    ("Alteryx", "greenhouse", "alteryx"),
    ("ThoughtSpot", "greenhouse", "thoughtspot"),
    ("Domo", "greenhouse", "domo"),
    ("Fivetran", "greenhouse", "fivetran"),
    ("dbt Labs", "greenhouse", "dbtlabs"),
    ("Airbyte", "ashby", "airbyte"),
    ("Monte Carlo", "ashby", "montecarlodata"),
    ("Collibra", "greenhouse", "collibra"),
    ("Informatica", "workday", "informatica|wd1|InformaticaCareers"),
    ("Teradata", "workday", "teradata|wd5|Teradata_Careers"),
    ("Cloudera", "greenhouse", "cloudera"),
    ("Couchbase", "greenhouse", "couchbase"),
    ("Redis", "greenhouse", "redis"),
    ("Neo4j", "greenhouse", "neo4j"),
    ("Cockroach Labs", "greenhouse", "cockroachlabs"),
    ("SingleStore", "greenhouse", "singlestore"),
    ("Starburst", "greenhouse", "starburst"),
    ("Dremio", "greenhouse", "dremio"),
    ("Imply", "greenhouse", "imply"),
    ("Cribl", "greenhouse", "cribl"),
    ("Chronosphere", "ashby", "chronosphere"),
    ("Honeycomb", "greenhouse", "honeycomb"),
    ("PostHog", "ashby", "posthog"),
    ("Pendo", "greenhouse", "pendo"),
    ("WalkMe", "greenhouse", "walkme"),
    ("Gainsight", "greenhouse", "gainsight"),
    ("ChurnZero", "greenhouse", "churnzero"),
    ("Totango", "greenhouse", "totango"),
    ("Gong", "greenhouse", "gongio"),
    ("Clari", "greenhouse", "clari"),
    ("6sense", "greenhouse", "6sense"),
    ("Demandbase", "greenhouse", "demandbase"),
    ("ZoomInfo", "greenhouse", "zoominfo"),
    ("Apollo.io", "greenhouse", "apolloio"),
    ("Outreach", "greenhouse", "outreach"),
    ("Salesloft", "greenhouse", "salesloft"),
    ("Highspot", "greenhouse", "highspot"),
    ("Seismic", "greenhouse", "seismic"),
    ("DocuSign", "greenhouse", "docusign"),
    ("PandaDoc", "greenhouse", "pandadoc"),
    ("Box", "greenhouse", "boxinc"),
    ("Dropbox", "greenhouse", "dropbox"),
    ("Zoom", "workday", "zoom|wd5|Zoom"),
    ("RingCentral", "greenhouse", "ringcentral"),
    ("Five9", "greenhouse", "five9"),
    ("Genesys", "workday", "genesys|wd1|Genesys"),
    ("Zendesk", "greenhouse", "zendesk"),
    ("Intercom", "greenhouse", "intercom"),
    ("Sprinklr", "greenhouse", "sprinklr"),
    ("Khoros", "greenhouse", "khoros"),
    ("Hootsuite", "greenhouse", "hootsuite"),
    ("Sprout Social", "greenhouse", "sproutsocial"),
    ("Braze", "greenhouse", "braze"),
    ("Iterable", "greenhouse", "iterable"),
    ("Klaviyo", "greenhouse", "klaviyo"),
    ("Attentive", "greenhouse", "attentive"),
    ("Shopify", "greenhouse", "shopify"),
    ("BigCommerce", "greenhouse", "bigcommerce"),
    ("Algolia", "greenhouse", "algolia"),
    ("Contentstack", "greenhouse", "contentstack"),
    ("Sanity", "ashby", "sanity"),
    ("Webflow", "greenhouse", "webflow"),
    ("Wix", "smartrecruiters", "Wix2"),
    ("Squarespace", "greenhouse", "squarespace"),
    ("GoDaddy", "workday", "godaddy|wd1|GoDaddyCareers"),
    ("CloudBees", "greenhouse", "cloudbees"),
    ("CircleCI", "greenhouse", "circleci"),
    ("Harness", "greenhouse", "harness"),
    ("JFrog", "greenhouse", "jfrog"),
    ("SonarSource", "greenhouse", "sonarsource"),
    ("Docker", "greenhouse", "docker"),
    ("Tailscale", "greenhouse", "tailscale"),
    ("Cloudflare", "greenhouse", "cloudflare"),
    ("Fastly", "greenhouse", "fastly"),
    ("Akamai", "workday", "akamai|wd1|Ext_Career"),
    ("Okta", "greenhouse", "okta"),
    ("Auth0", "greenhouse", "auth0"),
    ("Ping Identity", "workday", "pingidentity|wd1|Ping_Identity_Careers"),
    ("SailPoint", "greenhouse", "sailpoint"),
    ("CyberArk", "greenhouse", "cyberark"),
    ("Tenable", "greenhouse", "tenable"),
    ("Rapid7", "greenhouse", "rapid7"),
    ("Qualys", "smartrecruiters", "Qualys"),
    ("Fortinet", "workday", "fortinet|wd1|Fortinet_Careers"),
    ("Check Point", "workday", "checkpoint|wd3|CheckPoint_Careers"),
    ("Proofpoint", "workday", "proofpoint|wd5|ProofpointCareers"),
    ("Mimecast", "greenhouse", "mimecast"),
    ("Veeam", "smartrecruiters", "VeeamSoftware"),
    ("Commvault", "workday", "commvault|wd1|Commvault"),
    ("Pure Storage", "greenhouse", "purestorage"),
    ("NetApp", "workday", "netapp|wd1|NetAppCareerSite"),
    ("Western Digital", "smartrecruiters", "WesternDigital"),
    ("Seagate", "workday", "seagate|wd1|EXT"),
    ("AMD", "workday", "amd|wd5|AMD"),
    ("ARM", "workday", "arm|wd3|Arm_Careers"),
    ("Synopsys", "workday", "synopsys|wd1|Synopsys"),
    ("Cadence", "workday", "cadence|wd1|External_Careers"),
    ("Texas Instruments", "workday", "ti|wd1|External"),
    ("Analog Devices", "workday", "analogdevices|wd1|External"),
    ("NXP", "workday", "nxp|wd3|careers"),
    ("Infineon", "workday", "infineon|wd3|External"),
    ("Siemens Healthineers", "workday", "siemenshealthineers|wd3|External"),
    ("Philips", "workday", "philips|wd3|jobs-and-careers"),
    ("GE HealthCare", "workday", "gehealthcare|wd5|GEHC_ExternalSite"),
    ("Medtronic", "workday", "medtronic|wd1|MedtronicCareers"),
    ("Stryker", "workday", "stryker|wd1|StrykerCareers"),
    ("Boston Scientific", "workday", "bostonscientific|wd1|BostonScientificCareers"),
    ("Abbott", "workday", "abbott|wd5|abbottcareers"),
    ("Roche", "workday", "roche|wd3|roche-ext"),
    ("Pfizer", "workday", "pfizer|wd1|PfizerCareers"),
    ("GSK", "workday", "gsk|wd5|GSKCareers"),
    ("Bristol Myers Squibb", "workday", "bms|wd5|BMS_External_Career_Site"),
    ("Eli Lilly", "workday", "lilly|wd5|Lilly"),
    ("Amgen", "workday", "amgen|wd1|Careers"),
    ("UnitedHealth Group / Optum", "workday", "uhg|wd5|UHG"),
    ("Cigna / Evernorth", "workday", "cigna|wd5|cignacareers"),
    ("CVS Health", "workday", "cvshealth|wd1|CVS_Health_Careers"),
    ("Elevance Health", "workday", "anthem|wd1|External"),
    ("Chubb", "workday", "chubb|wd1|Chubb_Careers"),
    ("AIG", "workday", "aig|wd1|aig"),
    ("MetLife", "workday", "metlife|wd5|MetLifeCareers"),
    ("Prudential", "workday", "prudential|wd5|Prudential"),
    ("State Street", "workday", "statestreet|wd1|Global"),
    ("BNY Mellon", "workday", "bnymellon|wd1|BNYMellon"),
    ("Northern Trust", "workday", "ntrs|wd1|northerntrust"),
    ("BlackRock", "workday", "blackrock|wd1|BlackRock_Professional"),
    ("Vanguard", "workday", "vanguard|wd5|vanguard_external"),
    ("Nasdaq", "workday", "nasdaq|wd1|Global_External_Site"),
    ("CME Group", "workday", "cmegroup|wd1|CMEGroup"),
    ("ICE", "workday", "ice|wd1|ICE"),
    ("MSCI", "smartrecruiters", "MSCI"),
    ("London Stock Exchange Group", "workday", "lseg|wd3|Careers"),
    ("ADP", "workday", "adp|wd1|ADP"),
    ("Paychex", "workday", "paychex|wd5|Paychex"),
    ("UKG", "workday", "ukg|wd1|UKG_External"),
    ("Ceridian / Dayforce", "workday", "ceridian|wd5|Ceridian"),
    ("Cornerstone OnDemand", "workday", "csod|wd1|CSOD_Careers"),
    ("Coupa", "greenhouse", "coupa"),
    ("Ariba / SAP", "workday", "sap|wd3|SAP_Careers"),
    ("Ivalua", "smartrecruiters", "Ivalua"),
    ("GEP", "smartrecruiters", "GEP"),
    ("Zycus", "lever", "zycus"),
    ("Sirion", "greenhouse", "sirionlabs"),
    ("DocuSign", "greenhouse", "docusign"),
    ("Veeva Systems", "lever", "veeva"),
    ("IQVIA", "workday", "iqvia|wd1|IQVIACareers"),
    ("Syneos Health", "workday", "syneoshealth|wd1|Syneos_Health"),
    ("ICON", "workday", "icon|wd3|ICON"),
    ("Parexel", "workday", "parexel|wd1|Parexel_External_Career_Site"),
    ("McKinsey", "workday", "mckinsey|wd1|McKinsey_Careers"),
    ("BCG", "workday", "bcg|wd1|BCG"),
    ("Bain & Company", "workday", "bain|wd1|Bain"),
    ("Accenture", "workday", "accenture|wd3|AccentureCareers"),
    ("Capgemini", "smartrecruiters", "Capgemini"),
    ("Cognizant", "workday", "cognizant|wd1|Cognizant_Careers"),
    ("Infosys", "workday", "infosys|wd3|Infosys_Careers"),
    ("Wipro", "workday", "wipro|wd3|Wipro_Careers"),
    ("Tech Mahindra", "workday", "techmahindra|wd3|TechMahindra"),
    ("Genpact", "workday", "genpact|wd1|Genpact"),
    ("EXL Service", "workday", "exl|wd1|EXL"),
    ("WNS", "workday", "wns|wd3|WNS"),
    ("Mu Sigma", "lever", "musigma"),
    ("Fractal Analytics", "smartrecruiters", "Fractal"),
    ("Tiger Analytics", "lever", "tigeranalytics"),
    ("LatentView", "lever", "latentview"),
    ("Tredence", "greenhouse", "tredence"),
    ("Sigmoid", "lever", "sigmoid"),
    ("MathCo", "lever", "themathcompany"),
    ("Course5i", "lever", "course5i"),
    ("Gramener", "lever", "gramener"),
    ("absoutdata", "lever", "absolutdata"),
    ("ZS Associates", "workday", "zs|wd1|ZS_Careers"),
    ("Bain Capability Network", "workday", "bain|wd1|Bain"),
    ("PepsiCo", "workday", "pepsico|wd5|PepsiCo_Jobs"),
    ("Coca-Cola", "workday", "coke|wd1|coca-cola-careers"),
    ("Unilever", "workday", "unilever|wd3|Unilever_Experienced_Professionals"),
    ("Procter & Gamble", "workday", "pg|wd5|1000"),
    ("Nestle", "workday", "nestle|wd3|Nestle"),
    ("Mondelez", "workday", "mdlz|wd3|External"),
    ("Diageo", "workday", "diageo|wd3|Diageo_Careers"),
    ("AB InBev", "workday", "abinbev|wd1|ABInBev"),
    ("Nike", "workday", "nike|wd1|nke"),
    ("Adidas", "workday", "adidas|wd3|adidas"),
    ("IKEA", "smartrecruiters", "IKEA"),
    ("H&M", "smartrecruiters", "HMGroup"),
    ("Shell", "workday", "shell|wd3|ShellCareers"),
    ("BP", "workday", "bp|wd3|bpCareers"),
    ("Chevron", "workday", "chevron|wd5|jobs"),
    ("ExxonMobil", "workday", "exxonmobil|wd1|ExxonMobilCareers"),
    ("TotalEnergies", "workday", "totalenergies|wd3|TotalEnergiesCareers"),
    ("Honeywell", "workday", "honeywell|wd5|Honeywell"),
    ("3M", "workday", "3m|wd1|Search"),
    ("Caterpillar", "workday", "cat|wd1|CaterpillarCareers"),
    ("John Deere", "workday", "johndeere|wd1|John-Deere-Careers"),
    ("Boeing", "workday", "boeing|wd1|EXTERNAL_CAREERS"),
    ("Airbus", "workday", "airbus|wd3|Airbus"),
    ("GE Aerospace", "workday", "geaerospace|wd5|GE_ExternalSite"),
    ("Rolls-Royce", "workday", "rollsroyce|wd3|Rolls-Royce"),
    ("Eaton", "workday", "eaton|wd1|EatonCareers"),
    ("Emerson", "workday", "emerson|wd5|EmersonCareers"),
    ("Rockwell Automation", "workday", "rockwellautomation|wd1|External_Rockwell_Automation"),
    ("Johnson Controls", "workday", "jci|wd5|JCI_External"),
    ("Carrier", "workday", "carrier|wd5|carrier"),
    ("Otis", "workday", "otis|wd5|Otis_Careers"),
    ("Bosch", "smartrecruiters", "BoschGroup"),
    ("Continental", "smartrecruiters", "Continental"),
    ("ZF Group", "workday", "zf|wd3|ZF_Careers"),
    ("Valeo", "workday", "valeo|wd3|Valeo_Careers"),
    ("Aptiv", "workday", "aptiv|wd5|APTIV_CAREERS"),
    ("Maersk", "workday", "maersk|wd3|Maersk_Careers"),
    ("DHL", "workday", "dpdhl|wd3|DPDHL"),
    ("FedEx", "workday", "fedex|wd1|FXE-US_External"),
    ("UPS", "workday", "ups|wd5|Search")
]

# 3. Pull open crowd-sourced ATS slugs from elliottdehn/open-jobs (CC0 public registry)
def fetch_community_slugs():
    candidates = []
    urls = [
        "https://raw.githubusercontent.com/elliottdehn/open-jobs/main/contributed-slugs.txt",
        "https://raw.githubusercontent.com/elliottdehn/open-jobs/main/slugs.txt"
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=12)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "," not in line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        ats, slug = parts[0].lower(), parts[1]
                        if ats in {"greenhouse", "lever", "ashby", "smartrecruiters", "workable"} and slug:
                            comp = parts[2] if len(parts) >= 3 and parts[2] else slug.replace("-", " ").title()
                            candidates.append((comp, ats, slug))
        except Exception:
            pass
    return candidates

def verify_board(item):
    comp, ats, slug = item
    key = (ats, slug.lower())
    if key in verified:
        return None
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=6)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}?limit=1", timeout=6)
            if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=6)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "smartrecruiters":
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1", timeout=6)
            if r.status_code == 200 and len(r.json().get("content", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "workable":
            r = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", timeout=6)
            if r.status_code == 200 and len(r.json().get("jobs", [])) > 0:
                return {"company": comp, "ats": ats, "slug": slug}
        elif ats == "workday":
            parts = slug.split("|")
            if len(parts) == 3:
                tenant, wd_num, site = parts
                wd_url = f"https://{tenant}.{wd_num}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
                r = requests.post(wd_url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, headers={"Content-Type": "application/json"}, timeout=8)
                if r.status_code == 200 and r.json().get("total", 0) > 0:
                    return {"company": comp, "ats": ats, "slug": slug}
    except Exception:
        pass
    return None

community_candidates = fetch_community_slugs()
all_candidates = EXPLICIT_TARGETS + community_candidates

# Deduplicate candidates before probing
unique_candidates = []
seen_keys = set(verified.keys())
for comp, ats, slug in all_candidates:
    k = (ats.lower(), slug.lower())
    if k not in seen_keys:
        seen_keys.add(k)
        unique_candidates.append((comp, ats.lower(), slug))

print(f"Probing {len(unique_candidates)} new candidate ATS boards across 40 parallel workers...")
t0 = time.time()
added_count = 0

with ThreadPoolExecutor(max_workers=40) as pool:
    futures = [pool.submit(verify_board, item) for item in unique_candidates]
    for fut in as_completed(futures):
        res = fut.result()
        if res:
            verified[(res["ats"], res["slug"].lower())] = res
            added_count += 1

# Sort alphabetically and save to companies.csv
final_rows = sorted(verified.values(), key=lambda x: x["company"].lower())
with open(EXISTING_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["company", "ats", "slug"])
    writer.writeheader()
    writer.writerows(final_rows)

print(f"Discovery complete in {time.time() - t0:.1f}s! Added {added_count} new active boards -> Total verified boards: {len(final_rows)}")
