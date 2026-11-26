from pathlib import Path

import streamlit.components.v1 as components


quality_chart = components.declare_component(
    "sphq_quality_chart", path=str(Path(__file__).resolve().parent)
)
