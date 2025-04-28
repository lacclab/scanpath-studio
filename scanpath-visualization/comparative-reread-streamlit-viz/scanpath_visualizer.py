import os

import streamlit as st
from PIL import Image

# Path to the image folder
image_folder = (
    "/data/home/meiri.yoav/Cognitive-State-Decoding/ln_shared_data/onestop/trial_plots/"
)


# Helper function to parse the filename
def parse_filename(filename):
    parts = filename.split("__")
    return {
        "participant_id": "_".join(parts[0].split("_")[1:]),
        "article_index": int(parts[1]),
        "paragraph_index": int(parts[2]),
        "subj_condition": parts[3],
        "batch": parts[4].split("_")[0],
        "article_id": parts[4].split("_")[1],
        "level": parts[4].split("_")[2],
    }


# Function to find the origin index of article 12
def find_article_12_origin_index(participant_id):
    subj_image_folder = os.path.join(image_folder, participant_id)
    article_12_id = None
    article_12_origin_index = None

    # Find the article_id for article 12
    for filename in os.listdir(subj_image_folder):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            file_info = parse_filename(filename)
            if (
                file_info["participant_id"] == participant_id
                and file_info["article_index"] == 12
            ):
                article_12_id = file_info["article_id"]
                break

    # Find the origin index of article 12 using the article_id
    for filename in os.listdir(subj_image_folder):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            file_info = parse_filename(filename)
            if (
                file_info["participant_id"] == participant_id
                and file_info["article_id"] == article_12_id
                and file_info["article_index"] != 12
            ):
                article_12_origin_index = file_info["article_index"]
                break

    assert article_12_origin_index is not None, (
        f"Article 12 origin not found for subject {participant_id}"
    )
    return article_12_origin_index


# Load and organize images
def load_images(participant_id, article_12_origin_index_subj):
    images = {"10-11": {}, "12-origin": {}}
    subj_image_folder = os.path.join(image_folder, participant_id)

    for filename in os.listdir(subj_image_folder):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            file_info = parse_filename(filename)
            if file_info["participant_id"] == participant_id:
                # Article 10 and 11 pairing
                if file_info["article_index"] in [10, 11]:
                    images["10-11"].setdefault(file_info["paragraph_index"], {}).update(
                        {
                            file_info["article_index"]: os.path.join(
                                subj_image_folder, filename
                            )
                        }
                    )
                # Article 12 pairing with origin
                elif file_info["article_index"] in [article_12_origin_index_subj, 12]:
                    images["12-origin"].setdefault(
                        file_info["paragraph_index"], {}
                    ).update(
                        {
                            file_info["article_index"]: os.path.join(
                                subj_image_folder, filename
                            )
                        }
                    )
    return images


# Streamlit app
st.title("OneStop Eye Movements Reread Scanpath Visualizations")

# participant_ids are the folders in the image_folder
participant_ids = sorted(os.listdir(image_folder), key=lambda x: x.lower())
participant_ids.remove("README.md")
participant_id_dict = {
    i: participant_id for i, participant_id in enumerate(participant_ids)
}
selected_subject = st.select_slider("Select Subject", options=participant_ids)

# Load images for the selected subject
article_12_origin_index = find_article_12_origin_index(selected_subject)
images = load_images(selected_subject, article_12_origin_index)

# Headers for the two comparison sets in a row with CSS for styling
col_header_1, col_header_2, col_header_3, col_header_4, col_header_5 = st.columns(
    [1, 1, 0.05, 1, 1]
)

with col_header_1:
    st.markdown(
        "<h3 style='text-align: center;'>Article 10</h3>", unsafe_allow_html=True
    )
with col_header_2:
    st.markdown(
        "<h3 style='text-align: center;'>Article 11</h3>", unsafe_allow_html=True
    )
with col_header_3:
    st.markdown(
        "<div style='border-left: 2px solid gray; height: 30px;'></div>",
        unsafe_allow_html=True,
    )
with col_header_4:
    st.markdown(
        f"<h3 style='text-align: center;'>12 Original Article ({article_12_origin_index})</h3>",
        unsafe_allow_html=True,
    )
with col_header_5:
    st.markdown(
        "<h3 style='text-align: center;'>Article 12</h3>", unsafe_allow_html=True
    )

# Display images in a five-column layout with a separator between columns 2 and 4
for paragraph_index in sorted(
    set(images["10-11"].keys()).union(images["12-origin"].keys())
):
    col1, col2, col3, col4, col5 = st.columns([1, 1, 0.05, 1, 1])

    # Article 10 and 11 comparison
    with col1:
        if (
            paragraph_index in images["10-11"]
            and 10 in images["10-11"][paragraph_index]
        ):
            st.image(
                Image.open(images["10-11"][paragraph_index][10]),
                caption=f"Article 10, Paragraph {paragraph_index}",
            )
    with col2:
        if (
            paragraph_index in images["10-11"]
            and 11 in images["10-11"][paragraph_index]
        ):
            st.image(
                Image.open(images["10-11"][paragraph_index][11]),
                caption=f"Article 11, Paragraph {paragraph_index}",
            )

    # Vertical line separator
    with col3:
        st.markdown(
            "<div style='border-left: 5px solid gray; height: 100%;'></div>",
            unsafe_allow_html=True,
        )

    # Article 12 and its Origin comparison
    with col4:
        if article_12_origin_index in images["12-origin"].get(paragraph_index, {}):
            st.image(
                Image.open(
                    images["12-origin"][paragraph_index][article_12_origin_index]
                ),
                caption=f"Original Article {article_12_origin_index}, Paragraph {paragraph_index}",
            )

    with col5:
        if 12 in images["12-origin"].get(paragraph_index, {}):
            st.image(
                Image.open(images["12-origin"][paragraph_index][12]),
                caption=f"Article 12, Paragraph {paragraph_index}",
            )
