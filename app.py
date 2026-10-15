import streamlit as st

st.set_page_config(
    page_title="Smart ICU Guardian",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Smart ICU Guardian")

st.subheader("AI-Assisted Patient Monitoring Simulation")

st.info(
    "Academic software prototype. "
    "All patient readings are simulated."
)

st.success("Project dashboard initialized successfully.")

st.write("Modules to be integrated:")
st.write("- MPMC Processor Simulator")
st.write("- Verilog Safety Controller")
st.write("- SQLite Database")
st.write("- AI Explanation Agent")
st.write("- Emergency Alert System")
