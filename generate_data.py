# generate_data.py — builds data/database.sqlite with practice data for Spoonful.
# Seeded so every machine produces the identical database (and the same answers).
import random
import sqlite3
import os

random.seed(42)
DB_PATH = "./data/database.sqlite"

REGIONS = ["North", "South", "East", "West"]
# product: (price per unit, base units per month)
PRODUCTS = {"Classic Box": (55, 300), "Family Box": (85, 150), "Office Lunch": (12, 1500)}
INDUSTRIES = ["Technology", "Healthcare", "Finance", "Education", "Retail"]
# department: (headcount, average satisfaction out of 5)
DEPARTMENTS = {
    "Engineering": (25, 4.1), "Operations": (30, 3.3), "Customer Care": (20, 3.6),
    "Sales": (15, 3.9), "Marketing": (10, 4.0), "Culinary": (12, 4.2), "Finance": (8, 3.8),
}

def build_sales(cur):
    cur.execute("""CREATE TABLE sales (
        id INTEGER PRIMARY KEY, region TEXT, product TEXT,
        revenue REAL, date TEXT, units_sold INTEGER)""")
    for month in range(1, 13):                      # Jan–Dec 2025
        growth = 1 + 0.02 * (month - 1)             # ~2% growth per month
        for region in REGIONS:
            for product, (price, base_units) in PRODUCTS.items():
                units = base_units * growth * random.uniform(0.9, 1.1)
                if product == "Office Lunch":
                    units *= 1 + 0.03 * (month - 1) # strategic product grows faster
                if region == "West" and month >= 10:
                    units *= 0.75                   # West slumps in Q4
                units = int(units)
                cur.execute(
                    "INSERT INTO sales (region, product, revenue, date, units_sold) VALUES (?, ?, ?, ?, ?)",
                    (region, product, round(units * price, 2), f"2025-{month:02d}-01", units))

def build_customers(cur):
    cur.execute("""CREATE TABLE customers (
        id INTEGER PRIMARY KEY, name TEXT, industry TEXT,
        churn_date TEXT, satisfaction_score REAL)""")
    prefixes = ["Apex", "Bright", "Cedar", "Delta", "Evergreen", "Falcon", "Granite",
                "Harbor", "Ion", "Juniper", "Keystone", "Lumen"]
    suffixes = ["Labs", "Health", "Partners", "Systems", "Group"]
    churned_ids = set(random.sample(range(60), 11))  # 11 of 60 = 18.3% churn
    for i in range(60):
        name = f"{prefixes[i % 12]} {suffixes[i // 12]}"
        industry = INDUSTRIES[i % 5]
        if i in churned_ids:
            churn_date = f"2025-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            score = round(random.uniform(2.0, 3.4), 1)   # churned customers were unhappier
        else:
            churn_date = None
            score = round(random.uniform(3.6, 4.8), 1)
        cur.execute(
            "INSERT INTO customers (name, industry, churn_date, satisfaction_score) VALUES (?, ?, ?, ?)",
            (name, industry, churn_date, score))

def build_employees(cur):
    cur.execute("""CREATE TABLE employees (
        id INTEGER PRIMARY KEY, department TEXT,
        satisfaction_score REAL, tenure_years REAL)""")
    for dept, (headcount, avg_score) in DEPARTMENTS.items():
        for _ in range(headcount):
            score = min(5.0, max(1.0, round(random.gauss(avg_score, 0.4), 1)))
            tenure = round(random.uniform(0.3, 9.0), 1)
            cur.execute(
                "INSERT INTO employees (department, satisfaction_score, tenure_years) VALUES (?, ?, ?)",
                (dept, score, tenure))

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)                          # rebuild from scratch every time
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    build_sales(cur)
    build_customers(cur)
    build_employees(cur)
    conn.commit()
    for table in ["sales", "customers", "employees"]:
        print(f"{table}: {cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} rows")
    conn.close()
