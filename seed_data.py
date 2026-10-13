"""
Bizilytics seed data.

Round 1 – Insight Sprint:  25 MCQ questions across business awareness,
           basic analytics concepts, and logical reasoning.
Round 2 – Data Detective:  3 case analysis problems (organizer picks one).
Round 3 – Bizilytics Showdown: 3 business scenario pitches (organizer picks one).
"""

import json, time
import database as D
import auth

# ─────────────────────────────────────────────────────────────────────────────
# ROUND 1 QUESTIONS
# (text, A, B, C, D, correct, marks, neg, category, difficulty)
# ─────────────────────────────────────────────────────────────────────────────
R1_QUESTIONS = [
    # Business Awareness
    ("Which Indian regulator oversees the securities market?",
     "RBI", "SEBI", "IRDAI", "SIDBI",
     "B", 1, 0, "Business Awareness", "Easy"),

    ("What does 'GDP' stand for?",
     "Gross Domestic Product", "General Domestic Profit",
     "Gross Demand Percentage", "General Development Plan",
     "A", 1, 0, "Business Awareness", "Easy"),

    ("A company's balance sheet balances because Assets =",
     "Revenue − Expenses", "Liabilities + Equity",
     "Cash + Inventory", "Profit + Loss",
     "B", 1, 0, "Business Awareness", "Easy"),

    ("Which financial statement shows a company's profitability over a period?",
     "Balance Sheet", "Cash Flow Statement",
     "Income Statement", "Statement of Retained Earnings",
     "C", 1, 0, "Business Awareness", "Easy"),

    ("A 'Bull Market' is characterised by:",
     "Falling prices", "Rising prices",
     "Stagnant prices", "Volatile prices",
     "B", 1, 0, "Business Awareness", "Easy"),

    ("Which metric measures how efficiently a company uses equity to generate profit?",
     "ROA", "ROE", "EBITDA", "P/E ratio",
     "B", 1, 0, "Business Awareness", "Medium"),

    ("If a company's current ratio is below 1, it means:",
     "It has more current assets than liabilities",
     "It has more current liabilities than assets",
     "It is highly profitable",
     "It has zero debt",
     "B", 1, 0, "Business Awareness", "Medium"),

    ("EBITDA stands for:",
     "Earnings Before Interest, Tax, Depreciation and Amortisation",
     "Equity Balance in Total Debt Arrangement",
     "Estimated Budget in Total Direct Assets",
     "Earnings Before International Trade and Domestic Affairs",
     "A", 1, 0, "Business Awareness", "Medium"),

    ("The Reserve Bank of India (RBI) primarily controls which of the following?",
     "Fiscal policy", "Monetary policy", "Trade policy", "Foreign policy",
     "B", 1, 0, "Business Awareness", "Medium"),

    ("Which term describes the practice of spreading investments across asset classes to reduce risk?",
     "Leverage", "Hedging", "Diversification", "Arbitrage",
     "C", 1, 0, "Business Awareness", "Easy"),

    # Basic Analytics
    ("A dataset has values: 4, 8, 6, 10, 2. What is the mean?",
     "4", "6", "8", "10",
     "B", 1, 0, "Basic Analytics", "Easy"),

    ("In a normal distribution, approximately what percentage of data falls within ±1 standard deviation of the mean?",
     "50%", "68%", "95%", "99.7%",
     "B", 1, 0, "Basic Analytics", "Medium"),

    ("A bar chart is best used to:",
     "Show a trend over time", "Compare categories",
     "Show proportions of a whole", "Display a distribution",
     "B", 1, 0, "Basic Analytics", "Easy"),

    ("Which chart type is best suited for showing a part-to-whole relationship?",
     "Bar chart", "Line chart", "Pie chart", "Scatter plot",
     "C", 1, 0, "Basic Analytics", "Easy"),

    ("Correlation between two variables ranges from:",
     "0 to 1", "−1 to 0", "−1 to 1", "0 to 100",
     "C", 1, 0, "Basic Analytics", "Medium"),

    ("If a product's sales increased from ₹10 lakh to ₹15 lakh, what is the percentage growth?",
     "25%", "33%", "50%", "150%",
     "C", 1, 0, "Basic Analytics", "Easy"),

    ("A company has revenue of ₹100 Cr and COGS of ₹60 Cr. What is the gross profit margin?",
     "40%", "60%", "50%", "30%",
     "A", 1, 0, "Basic Analytics", "Medium"),

    ("Which of the following is NOT a measure of central tendency?",
     "Mean", "Median", "Mode", "Variance",
     "D", 1, 0, "Basic Analytics", "Easy"),

    ("A pivot table is used in data analytics to:",
     "Create charts", "Summarise and aggregate data",
     "Delete duplicate rows", "Format spreadsheet cells",
     "B", 1, 0, "Basic Analytics", "Medium"),

    ("A company's net profit margin is 15% on revenue of ₹200 Cr. What is its net profit?",
     "₹15 Cr", "₹20 Cr", "₹30 Cr", "₹25 Cr",
     "C", 1, 0, "Basic Analytics", "Medium"),

    # Logical Reasoning
    ("If all managers are leaders, and some leaders are coaches, which statement must be true?",
     "All managers are coaches",
     "Some managers may be coaches",
     "No managers are coaches",
     "All coaches are managers",
     "B", 1, 0, "Logical Reasoning", "Medium"),

    ("A project team completes 1/4 of a project in 3 days. At this rate, how many days to finish the whole project?",
     "9 days", "12 days", "15 days", "16 days",
     "B", 1, 0, "Logical Reasoning", "Easy"),

    ("Profit last year was ₹80 lakh. This year it is ₹100 lakh. What is the year-on-year increase?",
     "20 lakh", "20%", "25%", "Both B and C are correct",
     "C", 1, 0, "Logical Reasoning", "Medium"),

    ("Which of the following best describes a 'loss leader' pricing strategy?",
     "Pricing a product at maximum possible price",
     "Pricing a product below cost to attract customers",
     "Keeping prices equal to competitors",
     "Adding a fixed margin to production cost",
     "B", 1, 0, "Logical Reasoning", "Medium"),

    ("A firm's fixed costs are ₹5 lakh and variable cost per unit is ₹50. If selling price is ₹100/unit, "
     "what is the break-even quantity?",
     "5,000 units", "10,000 units", "2,500 units", "1,000 units",
     "B", 1, 0, "Logical Reasoning", "Hard"),
]


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 2 CASES
# (title, description, dataset_notes, charts_json, questions_json, rubric_json)
# ─────────────────────────────────────────────────────────────────────────────
R2_CASES = [
    (
        "RetailCo's Declining Sales Mystery",
        """RetailCo is a mid-sized retail chain operating 120 stores across South India. 
Over the last two quarters, total revenue has fallen by 18% year-on-year despite 
the company opening 10 new stores. Online competitors have been growing aggressively 
in the same geography. The management is confused — footfall data shows a 12% drop, 
but basket size has actually grown by 8%.

Your team has been given summarised sales data, customer satisfaction scores, and 
competitor benchmarks. Identify the root cause(s) of the revenue decline and 
recommend actionable solutions.""",

        """Key Data Points:
• Total Revenue Q3 FY25: ₹420 Cr  |  Q3 FY24: ₹512 Cr  (−18%)
• Same-store sales growth: −22%
• New-store contribution: +₹38 Cr
• Footfall (same stores): −12%
• Average basket size: +8%
• Customer Satisfaction Score (CSS): 3.2 / 5 (was 4.1 last year)
• Online competitors' GMV growth: +45% in same region
• RetailCo's own e-commerce: launched 6 months ago; ₹4 Cr GMV only
• Inventory turnover ratio: 3.2x  (industry average 5.8x)
• Top product category decline: Electronics (−35%), Apparel (−20%)
• Staff attrition: 28% (industry 12%)""",

        json.dumps([
            "Bar chart: Revenue by category Q3 FY24 vs Q3 FY25",
            "Line chart: Monthly footfall trend last 12 months",
            "Pie chart: Revenue split by channel (in-store vs online)",
            "Scatter plot: Store size vs revenue per sq ft"
        ]),

        json.dumps([
            "What are the top 3 key problems you identify from the data?",
            "What insights do you derive about the root cause?",
            "What 3 concrete solutions would you recommend to management?"
        ]),

        json.dumps({
            "analytical_thinking": {
                "max": 40,
                "criteria": "Depth of problem identification, use of data points, logical structure"
            },
            "clarity_of_insights": {
                "max": 30,
                "criteria": "Clarity of communication, connection between data and conclusions"
            },
            "relevance_of_solutions": {
                "max": 30,
                "criteria": "Practicality, feasibility, data-backed recommendations"
            }
        })
    ),

    (
        "FinTech Fraud Detection Challenge",
        """PaySwift is a digital payments startup processing 2 million transactions per day. 
In the last month, fraud losses spiked by 340% — from ₹12 lakh/month to ₹53 lakh/month. 
The risk team has flagged that existing rule-based fraud detection is missing patterns. 
The CFO wants a data-driven strategy to reduce fraud losses without hurting genuine 
customer experience (false positives currently block 0.8% of legitimate transactions).

You have been given summary statistics of fraudulent vs legitimate transactions. 
Identify patterns, key risk signals, and propose a detection and prevention strategy.""",

        """Key Data Points:
• Total transactions/day: 2 million
• Avg transaction value: ₹1,850
• Fraudulent transactions (last month): 2,860 cases
• Fraud loss: ₹53 lakh  (was ₹12 lakh prev. month)
• Avg fraud transaction value: ₹18,500 (10x legitimate avg)
• False positive rate: 0.8% of legit transactions blocked
• Fraud by time: 67% between 11 PM – 4 AM
• Fraud by device: 78% new/unregistered devices
• Fraud by location: 45% from states customer never transacted before
• Top merchant categories in fraud: Gift cards (38%), Electronics (27%)
• User behaviour: 92% of fraud accounts created < 7 days before fraud
• Existing model accuracy: 71% detection rate""",

        json.dumps([
            "Bar chart: Fraud count by hour of day",
            "Heatmap: Fraud frequency by state",
            "Bar chart: Fraud vs legit split by merchant category",
            "Line chart: Monthly fraud losses trend"
        ]),

        json.dumps([
            "What are the strongest fraud signals in this data?",
            "What data-driven detection improvements would you prioritise?",
            "How would you balance fraud reduction with customer experience?"
        ]),

        json.dumps({
            "analytical_thinking": {
                "max": 40,
                "criteria": "Pattern recognition, use of specific data signals, statistical thinking"
            },
            "clarity_of_insights": {
                "max": 30,
                "criteria": "Clear articulation of findings, structured analysis"
            },
            "relevance_of_solutions": {
                "max": 30,
                "criteria": "Practicality of detection strategy, customer impact balance"
            }
        })
    ),

    (
        "GreenGrow Expansion Decision",
        """GreenGrow is an agri-tech company that sells organic fertiliser and crop advisory 
services to farmers across Karnataka. They are profitable in their home market and 
are now evaluating expansion into Tamil Nadu and Andhra Pradesh. Two investment firms 
have offered funding: Firm A offers ₹15 Cr at 20% equity; Firm B offers ₹10 Cr at 
12% equity with a revenue royalty of 3%.

You have been given GreenGrow's financial summary and market data for the target states. 
Analyse the expansion opportunity and recommend whether to expand, to which state first, 
and which funding option to choose.""",

        """Key Data Points:
• GreenGrow FY25 revenue: ₹42 Cr  |  Net profit: ₹6.3 Cr (15% margin)
• Karnataka market share: ~18%
• Tamil Nadu total addressable market (TAM): ₹280 Cr  |  Current organic penetration: 11%
• Andhra Pradesh TAM: ₹320 Cr  |  Current organic penetration: 8%
• Estimated cost to enter each state: ₹8–10 Cr (logistics, agri-dealers, local marketing)
• Competitor presence: TN has 3 established players; AP has 1 dominant player
• Farmer adoption curve (historical): 18 months to breakeven in new geography
• Firm A: ₹15 Cr | 20% equity | no royalty
• Firm B: ₹10 Cr | 12% equity | 3% revenue royalty for 5 years
• Projected year-3 revenue in new state: ₹35–50 Cr (base-to-optimistic)
• Working capital cycle: 90 days""",

        json.dumps([
            "Bar chart: Revenue and profit trends FY22–FY25",
            "Comparison table: TN vs AP market attractiveness matrix",
            "Waterfall chart: Projected P&L for first 3 years in new state",
            "Pie chart: Fund utilisation breakdown"
        ]),

        json.dumps([
            "Which state should GreenGrow enter first, and why?",
            "Which funding option is more favourable — justify with numbers?",
            "What are the top 3 risks and how would you mitigate them?"
        ]),

        json.dumps({
            "analytical_thinking": {
                "max": 40,
                "criteria": "Quantitative analysis, market sizing, financial evaluation"
            },
            "clarity_of_insights": {
                "max": 30,
                "criteria": "Structured presentation, clarity of recommendation"
            },
            "relevance_of_solutions": {
                "max": 30,
                "criteria": "Data-backed choices, risk awareness, practical roadmap"
            }
        })
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 3 SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
R3_SCENARIOS = [
    (
        "EduSpark – Scaling a Vernacular EdTech",
        """EduSpark is a 3-year-old EdTech startup offering vernacular-language skill courses (Tamil, Telugu, Kannada) for blue-collar workers aged 18–35. Currently operating in 2 states with 80,000 paid users, the company wants to scale to 5 states and 500,000 users in 18 months.

Your team must present a growth strategy covering: how EduSpark should acquire users at scale, what the monetisation model should look like at higher scale, and how to manage the operational complexity of expanding into 3 new states simultaneously. Your solution must be grounded in data and realistic financial assumptions.

Key Data:
• Current ARR: ₹6.4 Cr (avg ₹800/user/year)
• Blended CAC: ₹420 | LTV: ₹1,600 (LTV:CAC = 3.8x)
• Monthly churn: 4.2%
• Target: 500,000 paid users in 18 months
• Budget available for expansion: ₹18 Cr (Series A just closed)
• Top user acquisition channel: WhatsApp referrals (38%), Google Ads (29%)
• Completion rate of courses: 61% | NPS: 52""",
        json.dumps([
            "Target: 500,000 paid users in 18 months",
            "Budget: ₹18 Cr for expansion",
            "Current ARR: ₹6.4 Cr | CAC: ₹420 | LTV: ₹1,600",
            "Must cover: user acquisition, monetisation, operations"
        ])
    ),

    (
        "UrbanBite – Ghost Kitchen Turnaround",
        """UrbanBite operates 25 ghost kitchens (cloud kitchens) across Chennai, Bengaluru, and Hyderabad. After rapid expansion in FY24, the company is facing a cash crunch — 14 of its 25 kitchens are operating at below 40% capacity, and the average EBITDA margin has fallen to −8%.

You have been called in as strategy consultants. The founder wants a turnaround plan to reach EBITDA break-even within 9 months and prepare the business for a fundraise in month 12. Your pitch must include operational decisions (which kitchens to keep, rationalise, or close), a revenue improvement strategy, and a 12-month financial roadmap.

Key Data:
• Fixed cost per kitchen/month: ₹3.5 lakh
• Variable cost: 42% of revenue
• Avg revenue/kitchen (operating ones): ₹4.8 lakh/month
• Target: EBITDA break-even by month 9, fundraise ready by month 12""",
        json.dumps([
            "Current kitchens: 25 (14 below 40% utilisation)",
            "Current EBITDA margin: −8%",
            "Fixed cost per kitchen/month: ₹3.5 lakh",
            "Avg revenue/kitchen: ₹4.8 lakh/month",
            "Target: EBITDA break-even by month 9"
        ])
    ),

    (
        "CleanDrive – EV Charging Network Strategy",
        """CleanDrive wants to build India's largest EV two-wheeler charging network in Tier 2 and Tier 3 cities over the next 3 years. They have secured ₹50 Cr in Series A funding and are deciding on their go-to-market strategy: whether to own the charging infrastructure (CAPEX-heavy) or pursue an asset-light franchise/partnership model.

Your team must present CleanDrive's market entry strategy — which cities to enter first and why, which business model to adopt, and what the unit economics look like at scale. You must also address the chicken-and-egg problem: how do you grow the charging network when EV adoption is still low?

Key Data:
• EV two-wheeler market growing at 58% YoY
• Cost to install 1 charging point: ₹80,000 (owned) vs ₹25,000 (franchise support)
• Revenue per charge: ₹25–40 depending on city
• Target: 50 Tier-2/3 cities in 3 years""",
        json.dumps([
            "Funding: ₹50 Cr Series A",
            "Target: Cover 50 Tier-2/3 cities in 3 years",
            "EV two-wheeler market growing at 58% YoY",
            "Install cost: ₹80,000 (owned) vs ₹25,000 (franchise)",
            "Revenue per charge: ₹25–40"
        ])
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = dict(
    status="idle",           # idle | r1_open | r1_closed | r2_open | r2_closed | r3_open | r3_closed | ended
    spectator_code="SPECTATE",
    reg_code="",
    r1_timer_sec="1800",     # 30 minutes for quiz
    r1_neg_marking="0",      # 0 = disabled; 1 = enabled
    r2_active_case="1",      # which case ID is active for R2
    r2_timer_sec="900",      # 15 minutes prep
    r2_pres_sec="180",       # 3 minutes presentation
    r3_active_scenario="1",  # which scenario ID is active for R3
    r3_prep_sec="600",       # 10 minutes prep
    r3_pres_sec="180",       # 3 minutes presentation
    r2_top_n="5",            # top N from R1 advance to R2 (0 = all)
    r3_top_n="3",            # top N from R2 advance to R3 (0 = all)
)


def seed(c, force=False):
    """Seed the database with default data. Idempotent."""
    # Default settings
    for k, v in DEFAULTS.items():
        if D.get(c, k) is None:
            D.put(c, k, v)

    # Admin user
    if not c.execute("SELECT 1 FROM users").fetchone():
        h, s = auth.hash_pw("admin123")
        c.execute("INSERT INTO users(username,pw_hash,salt) VALUES(?,?,?)", ("organizer", h, s))

    # R1 questions
    if not c.execute("SELECT 1 FROM r1_questions").fetchone():
        for i, q in enumerate(R1_QUESTIONS):
            text, a, b, cc, d, correct, marks, neg, cat, diff = q
            c.execute(
                "INSERT INTO r1_questions(text,option_a,option_b,option_c,option_d,correct,marks,negative_marks,category,difficulty,ord) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (text, a, b, cc, d, correct, marks, neg, cat, diff, i + 1)
            )

    # R2 cases
    if not c.execute("SELECT 1 FROM r2_cases").fetchone():
        for i, case in enumerate(R2_CASES):
            title, desc, dataset, charts, questions, rubric = case
            c.execute(
                "INSERT INTO r2_cases(title,description,dataset_notes,charts,questions,rubric,ord) VALUES(?,?,?,?,?,?,?)",
                (title, desc, dataset, charts, questions, rubric, i + 1)
            )

    # R3 scenarios
    if not c.execute("SELECT 1 FROM r3_scenarios").fetchone():
        for i, scenario in enumerate(R3_SCENARIOS):
            title, desc, data_points = scenario
            c.execute(
                "INSERT INTO r3_scenarios(title,description,data_points,ord) VALUES(?,?,?,?)",
                (title, desc, data_points, i + 1)
            )
