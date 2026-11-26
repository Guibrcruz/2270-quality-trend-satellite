import streamlit as st


page = st.navigation([
    st.Page("sphq_studio.py", title="SPHQ Studio", default=True),
    st.Page(
        "pages/1_Treasury_Yield_Trend.py",
        title="Treasury Yield Trend",
        url_path="Treasury_Yield_Trend",
    ),
])
page.run()
