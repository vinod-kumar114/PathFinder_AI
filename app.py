import html
import re
import sys
from pathlib import Path
import streamlit as st

# Add project root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

# Page Configuration
st.set_page_config(
    page_title="Scholarship Finder",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern look
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #1E88E5;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 3rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1565C0;
        color: white;
    }
    .scholarship-card {
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 6px solid #ccc;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        background-color: #f9f9f9;
    }
    .status-eligible {
        border-left-color: #2E7D32 !important;
        background-color: #E8F5E9;
    }
    .status-potential {
        border-left-color: #F57F17 !important;
        background-color: #FFFDE7;
    }
    .status-insufficient {
        border-left-color: #0288D1 !important;
        background-color: #E1F5FE;
    }
    .status-ineligible {
        border-left-color: #C62828 !important;
        background-color: #FFEBEE;
    }
    .badge {
        display: inline-block;
        padding: 0.25em 0.6em;
        font-size: 75%;
        font-weight: 700;
        border-radius: 0.25rem;
        color: white;
    }
    .badge-eligible { background-color: #2E7D32; }
    .badge-potential { background-color: #F57F17; }
    .badge-insufficient { background-color: #0288D1; }
    .badge-ineligible { background-color: #C62828; }
    .badge-unknown { background-color: #616161; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_sidebar():
    with st.sidebar:
        st.title("🎓 About")
        st.info(
            """
            **Scholarship Finder** helps students match their academic and demographic 
            profiles with verified scholarship opportunities in Pakistan and abroad.
            """
        )

        st.warning(
            """
            ⚠️ **Disclaimer**
            
            Eligibility results are **indicative only**. Criteria and deadlines are subject 
            to change by funding agencies. 
            
            Always verify requirements and official details directly on the official source website before applying.
            """
        )

        st.markdown("---")
        st.markdown("### How it works")
        st.markdown(
            """
            1. Fill in your demographic and academic details.
            2. Click **Search Scholarships**.
            3. Review matches categorized by eligibility status:
               - ✅ **Eligible**: Meets all checked criteria.
               - ⚠️ **Potentially Eligible**: Meets core requirements but needs review.
               - ❓ **Insufficient Information**: Profile missing details needed for verification.
               - ❌ **Ineligible**: Does not satisfy required criteria.
            """
        )


def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    # Restrict application and source links strictly to HTTP and HTTPS protocols
    regex = re.compile(
        r"^https?://"  # http:// or https:// only
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return re.match(regex, url) is not None


def safe_text(val, default="N/A"):
    if val is None or str(val).strip() == "":
        return html.escape(default)
    return html.escape(str(val))


def main():
    render_sidebar()

    st.title("🎓 Student Scholarship Finder")
    st.write(
        "Enter your profile information below to search for matching scholarship opportunities."
    )

    # Search Profile Form
    with st.form(key="scholarship_search_form"):
        st.subheader("📋 Student Profile")

        col1, col2, col3 = st.columns(3)

        with col1:
            age = st.number_input(
                "Age", min_value=10, max_value=100, value=20, step=1
            )
            nationality = st.text_input("Nationality", value="Pakistan")
            province = st.selectbox(
                "Province / Region",
                [
                    "Punjab",
                    "Sindh",
                    "Khyber Pakhtunkhwa",
                    "Balochistan",
                    "Islamabad Capital Territory",
                    "Gilgit-Baltistan",
                    "Azad Jammu & Kashmir",
                    "Other",
                ],
            )
            domicile = st.text_input(
                "Domicile District",
                placeholder="e.g., Lahore, Swat, Karachi",
            )

        with col2:
            city = st.text_input("Current City", placeholder="e.g., Islamabad")
            education_level = st.selectbox(
                "Current Education Level",
                [
                    "Matriculation / O-Level",
                    "Intermediate / A-Level",
                    "Undergraduate / Bachelors",
                    "Postgraduate / Masters",
                    "Doctoral / PhD",
                    "Other",
                ],
            )
            qualification = st.text_input(
                "Highest Qualification Completed",
                placeholder="e.g., FSC Pre-Engineering, BS Computer Science",
            )

            grading_system = st.radio(
                "Grading System",
                options=["Percentage (%)", "CGPA"],
                horizontal=True,
            )

            if grading_system == "Percentage (%)":
                marks_input = st.number_input(
                    "Marks (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=None,
                    step=0.1,
                    placeholder="Enter your percentage (e.g. 80.0)",
                )
                cgpa_input = None
            else:
                marks_input = None
                cgpa_input = st.number_input(
                    "CGPA",
                    min_value=0.0,
                    max_value=4.0,
                    value=None,
                    step=0.01,
                    placeholder="Enter your CGPA (e.g. 3.50)",
                )

        with col3:
            field_of_study = st.text_input(
                "Field of Study / Discipline",
                placeholder="e.g., Computer Science, Medicine, Engineering",
            )
            household_income = st.number_input(
                "Monthly Household Income (PKR, Optional)",
                min_value=0,
                value=0,
                step=5000,
                help="Leave as 0 if you prefer not to specify.",
            )
            study_destination = st.selectbox(
                "Desired Study Destination",
                ["Pakistan", "Abroad", "Both"],
            )

        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button(label="🔍 Search Scholarships")

    if submit_button:
        # Require explicit academic grade input
        if grading_system == "Percentage (%)" and marks_input is None:
            st.error("⚠️ Please enter your academic Percentage (%) before searching.")
            return
        if grading_system == "CGPA" and cgpa_input is None:
            st.error("⚠️ Please enter your CGPA before searching.")
            return

        # Build student profile dictionary matching exact backend contract keys
        profile = {
            "age": age,
            "nationality": nationality.strip(),
            "province": province,
            "domicile": domicile.strip(),
            "city": city.strip(),
            "education_level": education_level,
            "qualification": qualification.strip(),
            "marks": marks_input,
            "cgpa": cgpa_input,
            "field_of_study": field_of_study.strip(),
            "household_income": household_income if household_income > 0 else None,
            "study_destination": study_destination,
        }

        # Attempt backend import & execution safely
        try:
            from src.matching import find_matches

            with st.spinner("Searching for scholarship matches..."):
                results = find_matches(profile, limit=50)

        except ImportError:
            st.error(
                "⚠️ **Backend Module Not Found**\n\n"
                "The module `src.matching` could not be imported. "
                "Please ensure the application database and matching modules are properly initialized and available in the `src/` directory."
            )
            return
        except Exception as e:
            st.error(
                f"⚠️ **Error Processing Search**\n\n"
                f"An error occurred while attempting to find scholarship matches: `{str(e)}`\n\n"
                "Please ensure the database is initialized and try again."
            )
            return

        if not isinstance(results, list):
            st.error(
                "⚠️ **Invalid Response Received**\n\n"
                "The backend matching system returned an invalid data format."
            )
            return

        # Filter out non-dictionary items prior to counts or display
        valid_results = [item for item in results if isinstance(item, dict)]
        discarded_count = len(results) - len(valid_results)

        if discarded_count > 0:
            st.warning(
                f"⚠️ {discarded_count} invalid result entry(s) were returned by the backend and excluded from display."
            )

        if len(valid_results) == 0:
            st.info(
                "🔍 **No Matching Scholarships Found**\n\n"
                "No scholarships matched your profile criteria at this time. Try broadening your study destination, field, or updating your qualifications."
            )
            return

        st.markdown("---")
        st.subheader("🎯 Search Results")

        # Categorize results by eligibility status
        eligible_items = []
        potential_items = []
        insufficient_items = []
        ineligible_items = []

        for item in valid_results:
            status = str(item.get("eligibility_status", "")).lower().strip()
            if status == "eligible":
                eligible_items.append(item)
            elif status in ["potentially_eligible", "potentially eligible", "potential"]:
                potential_items.append(item)
            elif status in ["insufficient_information", "insufficient information", "insufficient"]:
                insufficient_items.append(item)
            elif status in ["ineligible", "not_eligible", "not eligible"]:
                ineligible_items.append(item)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                f"All Results ({len(valid_results)})",
                f"✅ Eligible ({len(eligible_items)})",
                f"⚠️ Potentially Eligible ({len(potential_items)})",
                f"❓ Needs Info ({len(insufficient_items)})",
                f"❌ Ineligible ({len(ineligible_items)})",
            ]
        )

        def display_scholarship_list(items):
            if not items:
                st.info("No scholarships match this category.")
                return

            for item in items:
                status_raw = str(item.get("eligibility_status", "Unknown")).strip()
                status_lower = status_raw.lower()

                if status_lower == "eligible":
                    card_class = "status-eligible"
                    badge_class = "badge-eligible"
                    badge_label = "ELIGIBLE"
                elif status_lower in ["potentially_eligible", "potentially eligible", "potential"]:
                    card_class = "status-potential"
                    badge_class = "badge-potential"
                    badge_label = "POTENTIALLY ELIGIBLE"
                elif status_lower in ["insufficient_information", "insufficient information", "insufficient"]:
                    card_class = "status-insufficient"
                    badge_class = "badge-insufficient"
                    badge_label = "NEEDS INFORMATION"
                elif status_lower in ["ineligible", "not_eligible", "not eligible"]:
                    card_class = "status-ineligible"
                    badge_class = "badge-ineligible"
                    badge_label = "INELIGIBLE"
                else:
                    card_class = ""
                    badge_class = "badge-unknown"
                    badge_label = f"UNKNOWN STATUS ({safe_text(status_raw)})"

                name = safe_text(item.get("name") or item.get("scholarship_name"), "Unnamed Scholarship")
                provider = safe_text(item.get("provider"))
                funding = safe_text(item.get("funding"))
                deadline = safe_text(item.get("deadline"))
                location = safe_text(item.get("location"))
                verified_at = safe_text(item.get("verified_at") or item.get("verification_date"), "")

                reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
                missing_info = (
                    item.get("missing_information")
                    if isinstance(item.get("missing_information"), list)
                    else []
                )

                app_link = item.get("application_url") or item.get("application_link")
                src_link = item.get("source_url") or item.get("source_link")

                valid_app_link = app_link.strip() if is_valid_url(app_link) else None
                valid_src_link = src_link.strip() if is_valid_url(src_link) else None

                verified_str = f" | <em>Verified: {verified_at}</em>" if verified_at else ""

                st.markdown(
                    f"""
                    <div class="scholarship-card {card_class}">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <h3 style="margin: 0; color: #1E88E5;">{name}</h3>
                            <span class="badge {badge_class}">{badge_label}</span>
                        </div>
                        <p style="margin-bottom: 8px;"><strong>Provider:</strong> {provider} | <strong>Location:</strong> {location} | <strong>Funding:</strong> {funding}</p>
                        <p style="margin-bottom: 8px;"><strong>Deadline:</strong> {deadline} {verified_str}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                col_left, col_right = st.columns([2, 1])

                with col_left:
                    if reasons:
                        st.markdown("**Eligibility Match Criteria / Reasons:**")
                        for r in reasons:
                            st.markdown(f"- {safe_text(r)}")

                    if missing_info:
                        st.markdown("**Missing Information Required:**")
                        for m in missing_info:
                            st.markdown(f"- ⚠️ {safe_text(m)}")

                with col_right:
                    st.markdown("**Links & Applications:**")
                    if valid_app_link:
                        st.markdown(f"🔗 [Application Link]({valid_app_link})")
                    if valid_src_link:
                        st.markdown(f"🌐 [Official Source Link]({valid_src_link})")
                    if not valid_app_link and not valid_src_link:
                        st.caption("No direct links available.")

                st.markdown("---")

        with tab1:
            display_scholarship_list(valid_results)
        with tab2:
            display_scholarship_list(eligible_items)
        with tab3:
            display_scholarship_list(potential_items)
        with tab4:
            display_scholarship_list(insufficient_items)
        with tab5:
            display_scholarship_list(ineligible_items)


if __name__ == "__main__":
    main()