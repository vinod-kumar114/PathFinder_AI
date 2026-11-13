# PathFinder AI — Scholarship Assistant for Pakistani Students

PathFinder AI is a chat-based web app that helps Pakistani students find scholarships (in Pakistan and abroad) and check, **in an indicative way**, whether they are eligible.

The student chats normally ("I'm in BS 4th semester, CGPA 3.4, from Sindh, want a Masters abroad"). The app picks up the profile details from the message, searches a database of 147 scholarships, checks eligibility rules, and shows ranked results as cards. A Gemini AI model writes the friendly replies and gives advice (e.g. SOP guidance).

> **Disclaimer:** Results are guidance only, not official advice. Always confirm eligibility, deadlines and requirements on the scholarship's official website before applying.

---

## 1. Purpose

Scholarship information for Pakistani students is scattered across many websites, and eligibility rules are hard to compare. This project puts it in one place:

- one master database of scholarships (local and international)
- an eligibility engine that compares the student's profile with each scholarship
- an AI chat interface so students don't have to fill long forms or read every rule

**Design principle:** the AI does *not* decide eligibility. A deterministic Python engine does. If a rule or a profile value is unclear, it is reported as **"missing / unknown"**, never as a pass. The AI only explains the results, and it is told never to invent deadlines, links or eligibility.

---

## 2. Features

- Chat interface (Streamlit) with quick-action buttons
- Automatic extraction of profile details from chat (education level, CGPA / percentage, province, age, destination, etc.)
- Sidebar to view and edit the student profile, with a list of missing details
- Scholarship cards with status badge: **Eligible**, **Potentially Eligible**, **Needs Information**
- Sidebar filters by eligibility status and location (Pakistan / Abroad)
- Save / unsave scholarships (for the current session)
- Scholarship-only guardrail: unrelated questions (coding, jokes, crypto, etc.) are politely declined
- Works **without** an API key too (basic replies, matching still works)
- Excel workbook import with duplicate detection; database is auto-filled on first run
- 256 automated tests

---

## 3. Tools and technologies

| Tool | Used for |
|---|---|
| **Python 3.9+** | Main language (3.12 recommended) |
| **Streamlit** | Web UI: chat, sidebar, cards |
| **SQLite** (`sqlite3`) | Local database (`data/scholarships.db`) |
| **pandas + openpyxl** | Reading the Excel workbook |
| **Google Gemini API** (`google-genai`) | AI replies and (optionally) web-grounded verification |
| **python-dotenv** | Loading the API key from a `.env` file |
| **pytest** | Automated tests |

---

## 4. How it works

```
Student message
      |
      v
1. Topic guardrail        (scholarship_chat.py)  -> off-topic? polite redirect
2. Profile extraction     (profile.py)           -> update the student profile
3. Matching               (matching.py)          -> read DB, run eligibility, rank
      |                         |
      |                         +--> eligibility.py (rule checks)
      v
4. Gemini AI reply        (ai_agent.py)          -> friendly explanation + advice
5. Streamlit UI           (app.py)               -> chat + scholarship cards
```

### Main files and functions

| File | What it does | Key functions |
|---|---|---|
| `app.py` | Streamlit interface: chat, sidebar profile editor, filters, saved list, scholarship cards | `render_sidebar()`, `display_scholarship_card()`, `main()` |
| `src/ai_agent.py` | Orchestrates one chat turn and talks to Gemini | `process_chat_message()`, `get_gemini_client()` |
| `src/scholarship_chat.py` | Keeps the bot scholarship-only | `is_scholarship_related()`, `classify_user_intent()` |
| `src/profile.py` | Student profile: clean-up, extraction from text, summary, missing fields | `normalize_profile()`, `extract_profile_from_text()`, `summarize_profile()`, `get_missing_profile_fields()` |
| `src/matching.py` | Loads scholarships, checks eligibility, ranks results | `find_matches(profile, limit)` |
| `src/eligibility.py` | Rule engine (nationality, education, marks / CGPA, age, province, income, deadline, status) | `check_eligibility(profile, scholarship)` |
| `src/database.py` | SQLite schema, safe migrations, auto-seeding | `init_db()`, `seed_database_if_empty()`, `get_connection()` |
| `src/data_import.py` | Imports the Excel workbook, detects headers, removes duplicates | `import_workbook(path)` |
| `src/web_verification.py` | Cached "verify this scholarship" helper (24-hour cache; can use Gemini + Google Search) | `verify_scholarship_record()`, `get_cached_verification()` |
| `data/Pakistan_Scholarship_Finder_Master.xlsx` | Master scholarship data (source of the database) | - |
| `tests/` | Automated tests (use temporary databases only) | - |

### Eligibility results

`check_eligibility()` returns one of:

| Status | Meaning |
|---|---|
| `eligible` | All checked criteria pass and nothing is unknown |
| `potentially_eligible` | Nothing fails, but some criteria could not be confirmed |
| `insufficient_information` | Not enough data to judge (shown as "Needs Information") |
| `ineligible` | A clear mismatch (hidden from results) |

Results are ranked: eligible, then potentially eligible, then needs information, then by earliest deadline.

---

## 5. How to use it (step by step)

### Step 1: Install Python
Download Python 3.9 or newer from https://www.python.org/downloads/ (on Windows, tick **"Add Python to PATH"** during installation).

### Step 2: Download the project
```bash
git clone <your-repo-url>
cd PathFinder_AI
```
(Or download the ZIP from GitHub and extract it.)

### Step 3: Create a virtual environment (recommended)
```bash
python -m venv venv
```
Activate it:
- Windows: `venv\Scripts\activate`
- Mac / Linux: `source venv/bin/activate`

### Step 4: Install the dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Add your Gemini API key (optional but recommended)
1. Get a free key from https://aistudio.google.com/app/apikey
2. Copy `.env.example` to a new file named `.env`
3. Open `.env` and put your key in:
   ```
   GEMINI_API_KEY=your_real_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```

Without a key the app still runs and matching still works, but chat replies are basic and not AI-written. Never upload your `.env` file to GitHub (it is already in `.gitignore`).

### Step 6: Run the app
```bash
streamlit run app.py
```
The app opens in your browser (usually http://localhost:8501). On the first run it creates `data/scholarships.db` and fills it from the Excel workbook automatically (147 scholarships).

### Step 7: Use the app
1. Tell the assistant about yourself in the chat, or fill the **Update Profile Details** form in the sidebar.
2. Ask for scholarships, e.g. *"Find undergraduate scholarships in Punjab"* or use the quick-action buttons.
3. Read the cards: check the badge, match reasons and missing information, then open the **Apply / Source** link.
4. Use the sidebar filters and the **Save** button to shortlist scholarships.
5. Fill in missing profile details to get more accurate results.

---

## 6. Running the tests

```bash
python -m pytest -q
```
All 256 tests should pass. Tests use temporary databases and synthetic workbooks, and never touch your real `data/scholarships.db`.

---

## 7. Updating the scholarship data

To use your own or updated data, replace `data/Pakistan_Scholarship_Finder_Master.xlsx`, delete `data/scholarships.db`, and start the app again (it rebuilds the database from the workbook).

To import from code:
```python
from src.database import init_db
from src.data_import import import_workbook

init_db()
result = import_workbook("path/to/workbook.xlsx")
print(result["records_inserted"], result["errors"], result["warnings"])
```
**Always check `errors` and `warnings` after an import.** The importer keeps every original row in a `raw_data` column, skips metadata sheets, and avoids duplicates (by external ID, or by name + provider + deadline).

---

## 8. Project structure

```
PathFinder_AI/
├── app.py                  # Streamlit app (run this)
├── requirements.txt
├── .env.example            # copy to .env and add your API key
├── .gitignore
├── data/
│   └── Pakistan_Scholarship_Finder_Master.xlsx
├── src/
│   ├── ai_agent.py
│   ├── scholarship_chat.py
│   ├── profile.py
│   ├── matching.py
│   ├── eligibility.py
│   ├── database.py
│   ├── data_import.py
│   └── web_verification.py
└── tests/
```

---

## 9. Known limitations

- Narrative rules in the workbook (e.g. `nationality_rule`, `domicile_rule`, `other_eligibility`) are not converted into structured criteria; they are kept in `raw_data`, so those criteria show as "unknown".
- CGPA is accepted on a 4.0 scale only, and marks / percentage and CGPA are never converted into each other.
- Field of study is compared as plain text (no synonyms).
- `web_verification.py` (web-grounded verification and caching) is implemented, but the chat flow does not call it automatically yet.
- Saved scholarships and the chat history live only in the browser session; they are lost when the page is refreshed or closed.
- The scholarship-only guardrail is keyword-based, so a few off-topic questions can slip through (the AI is also instructed to decline them).
- No login system; the app is designed for local use.
- Eligibility results are indicative, not official.
