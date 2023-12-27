from datetime import datetime
import random
import string
from time import sleep

import streamlit as st
import cohere
import pinecone
import boto3

co = cohere.Client(st.secrets["COHERE_API_KEY"])
pinecone.init(api_key=st.secrets["PINECONE_API_KEY"], environment="gcp-starter")
index = pinecone.Index('llm-rec-sys')
dynamodb = boto3.resource(
    'dynamodb',
    region_name="eu-west-1",
    aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
)
dynamodb_feedback = dynamodb.Table('llm-rec-sys-feedback')
dynamodb_text_feedback = dynamodb.Table('llm-rec-sys-text-feedback')
dynamodb_queries = dynamodb.Table('llm-rec-sys-queries')

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

with st.sidebar:
    st.markdown("# Filters")
    st.markdown("Content type")
    contnet_type_col1, contnet_type_col2 = st.columns([0.3,0.7])
    contnet_movie_yes = contnet_type_col1.checkbox("Movie", value=True)
    contnet_series_yes = contnet_type_col2.checkbox("TV Series", value=True)
    if contnet_movie_yes + contnet_series_yes < 1:
        st.error("Select at least one content type")

    genres = st.multiselect(
        "Genres",
        ['Fantasy','Romance','Comedy','Drama','History','Mystery','Horror','Animation','Adventure','Thriller','Talk-Show','Documentary','Sport','News','Sci-Fi','Biography','Music','Film-Noir','Western','Musical','War','Action','Crime','Family'],
        # default="all",
    )
    countries = st.multiselect(
        "Countries",
        ['Argentina','Australia','Austria','Bahamas','Belgium','Brazil','Bulgaria','Canada','Chile','China','Colombia','Croatia','Cyprus','Czechia','Denmark','Finland','France','Germany','Greece','Hong Kong','Hungary','Iceland','India','Indonesia','Iran','Ireland','Israel','Italy','Japan','Jordan','Kenya','Lebanon','Luxembourg','Malta','Mexico','Morocco','Netherlands','New Zealand','North Korea','Norway','Paraguay','Peru','Philippines','Poland','Portugal','Qatar','Romania','Russia','Saudi Arabia','Serbia','Singapore','Slovenia','South Africa','South Korea','Soviet Union','Spain','Sweden','Switzerland','Taiwan','Thailand','Turkey','United Arab Emirates','United Kingdom','United States','Uruguay','West Germany']
    )
    min_avg_rating = st.slider("Min average rating", 0., 10., 0., 0.1)
    min_year = st.slider("Min year of release", 1920, 2023, 1920, 1)

    st.markdown("# Display")
    n_movies_display = st.selectbox('Number of movies per request', (5, 10, 15), index=1)



# st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align: center'>Giff movie</h1>", unsafe_allow_html=True)
for _ in range(2):
    st.markdown("")


# Example request hint
st.text('Example requests: "fun movie with good acting and lots of action", "something to\nboth make me laugh and cry", "character development", "funny superhero movie"')


row2 = False
row3 = False
row3 = False
row4 = False
row5 = False
row6 = False

user_query = st.text_input('Your request', '', key="row1")

if user_query:

    response = dynamodb_queries.put_item(Item = {
        'time': datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
        "hash": generate_random_string(8),
        'query': user_query,
    })

    query_filter = {}
    if not contnet_series_yes:
        query_filter["titleType"] = {"$eq": "movie"}
    if not contnet_movie_yes:
        query_filter["titleType"] = {"$eq": "series"}
    if genres:
        query_filter["genres"] = {"$in":genres}
    if countries:
        query_filter["countries"] = {"$in":countries}
    if min_avg_rating > 0:
        query_filter["averageRating"] = {"$gte": min_avg_rating}
    if min_year > 1920:
        query_filter["startYear"] = {"$gte": min_year}


    query_embed = co.embed(
        model='embed-english-v3.0',
        texts=[user_query],
        input_type='search_query'
    ).embeddings
    
    try:
        candidates = index.query(
            vector=query_embed[0],
            filter=query_filter,
            top_k=n_movies_display+10,
            include_metadata=True
        )
    except:
        pinecone.init(api_key="5628edd7-625d-48ad-982d-d03ca567a06c", environment="gcp-starter")
        index = pinecone.Index('llm-rec-sys')
        candidates = index.query(
            vector=query_embed[0],
            filter=query_filter,
            top_k=n_movies_display+10,
            include_metadata=True
        )

    titles = [x["metadata"]["primaryTitle"] for x in candidates["matches"]]
    ratings = [x["metadata"]["averageRating"] for x in candidates["matches"]]
    image_links = [x["metadata"]["small_cover"] for x in candidates["matches"]]
    tconsts = [x["metadata"]["tconst"] for x in candidates["matches"]]
    contexts = [x["metadata"]["context"] for x in candidates["matches"]]

    rerank_docs = co.rerank(
        query=user_query,
        documents=contexts,
        top_n=n_movies_display,
        model="rerank-english-v2.0"
    )
    relevant_ids = [x.index for x in rerank_docs[:n_movies_display]]

    titles = [titles[x] for x in relevant_ids]
    ratings = [ratings[x] for x in relevant_ids]
    image_links = [image_links[x] for x in relevant_ids]
    tconsts = [tconsts[x] for x in relevant_ids]

    n_rows = round(n_movies_display / 5)
    for row_id in range(n_rows):
        if row_id > 0:
            for _ in range(2):
                st.markdown("")
        for i, col in enumerate(st.columns(5)):
            j = i + (row_id*5)
            col.image(image_links[j], use_column_width="always")
            col.markdown(f"<center>{titles[j]}<br/>\
                        <a href='https://www.imdb.com/title/{tconsts[j]}/'>{ratings[j]}/10</a>\
                        </center>", unsafe_allow_html=True)
            if i == 4:
                row2 = True

    def send_like(query, tconsts, like):
        response = dynamodb_feedback.put_item(
        Item = {
                'time': datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
                "hash": generate_random_string(8),
                'query': query,
                'recommendations': ",".join(tconsts),
                "like": like,
            }
        )
        return response

    st.markdown("""
        <style>
        div[data-testid="stBlock"] > div:nth-child(2) > div > button {
            background-color: green;
            color: white;
            font-size: 20px;
            border: none;
            border-radius: 5px;
            padding: 10px 24px;
            margin: 10px 0;
            cursor: pointer;
        }
        div[data-testid="stBlock"] > div:nth-child(3) > div > button {
            background-color: red;
            color: white;
            font-size: 20px;
            border: none;
            border-radius: 5px;
            padding: 10px 24px;
            margin: 10px 0;
            cursor: pointer;
        }
        </style>""", unsafe_allow_html=True)

    like_col1, like_col2, like_col3, like_col4 = st.columns([0.58, 0.28, 0.07, 0.07])

    with like_col2:
        st.markdown("")
        st.markdown("")
        st.markdown("Rate the recommendations:")    
    with like_col3:
        st.markdown('<div class="greenButton">', unsafe_allow_html=True)
        if st.button("👍"):
            send_like(user_query, tconsts, 1)
        st.markdown('</div>', unsafe_allow_html=True)
    with like_col4:
        st.markdown('<div class="redButton">', unsafe_allow_html=True)
        if st.button("👎"):
            send_like(user_query, tconsts, 0)
        st.markdown('</div>', unsafe_allow_html=True)


# for i in range(3):
#     st.markdown("")
# if row2:
#     user_query2 = st.text_input('Your request', '', key="row2")

#     if user_query2:
#         query_embed = co.embed(
#             model='embed-english-v3.0',
#             texts=[user_query2],
#             input_type='search_query'
#         ).embeddings

#         candidates = index.query(
#             vector=query_embed[0],
#             top_k=n_movies_display,
#             include_metadata=True
#         )
#         titles = [x["metadata"]["primaryTitle"] for x in candidates["matches"]]
#         ratings = [x["metadata"]["averageRating"] for x in candidates["matches"]]
#         image_links = [x["metadata"]["small_cover"] for x in candidates["matches"]]
#         tconsts = [x["metadata"]["tconst"] for x in candidates["matches"]]

#         n_rows = round(n_movies_display / 5)
#         for row_id in range(n_rows):
#             if row_id > 0:
#                 for _ in range(2):
#                     st.markdown("")
#             for i, col in enumerate(st.columns(5)):
#                 j = i + (row_id*5)
#                 col.image(image_links[j], use_column_width="always")
#                 col.markdown(f"<center>{titles[j]}<br/>\
#                             <a href='https://www.imdb.com/title/{tconsts[j]}/'>{ratings[j]}/10</a>\
#                             </center>", unsafe_allow_html=True)
#             if i == 4:
#                 row3 = True


# for i in range(3):
#     st.markdown("")
# if row3:
#     user_query2 = st.text_input('Your request', '', key="row3")

#     if user_query2:
#         query_embed = co.embed(
#             model='embed-english-v3.0',
#             texts=[user_query2],
#             input_type='search_query'
#         ).embeddings

#         candidates = index.query(
#             vector=query_embed[0],
#             top_k=n_movies_display,
#             include_metadata=True
#         )
#         titles = [x["metadata"]["primaryTitle"] for x in candidates["matches"]]
#         ratings = [x["metadata"]["averageRating"] for x in candidates["matches"]]
#         image_links = [x["metadata"]["small_cover"] for x in candidates["matches"]]
#         tconsts = [x["metadata"]["tconst"] for x in candidates["matches"]]

#         n_rows = round(n_movies_display / 5)
#         for row_id in range(n_rows):
#             if row_id > 0:
#                 for _ in range(2):
#                     st.markdown("")
#             for i, col in enumerate(st.columns(5)):
#                 j = i + (row_id*5)
#                 col.image(image_links[j], use_column_width="always")
#                 col.markdown(f"<center>{titles[j]}<br/>\
#                             <a href='https://www.imdb.com/title/{tconsts[j]}/'>{ratings[j]}/10</a>\
#                             </center>", unsafe_allow_html=True)
#             if i == 4:
#                 row4 = True


# for i in range(3):
#     st.markdown("")
# if row4:
#     user_query2 = st.text_input('Your request', '', key="row4")

#     if user_query2:
#         query_embed = co.embed(
#             model='embed-english-v3.0',
#             texts=[user_query2],
#             input_type='search_query'
#         ).embeddings

#         candidates = index.query(
#             vector=query_embed[0],
#             top_k=n_movies_display,
#             include_metadata=True
#         )
#         titles = [x["metadata"]["primaryTitle"] for x in candidates["matches"]]
#         ratings = [x["metadata"]["averageRating"] for x in candidates["matches"]]
#         image_links = [x["metadata"]["small_cover"] for x in candidates["matches"]]
#         tconsts = [x["metadata"]["tconst"] for x in candidates["matches"]]

#         n_rows = round(n_movies_display / 5)
#         for row_id in range(n_rows):
#             if row_id > 0:
#                 for _ in range(2):
#                     st.markdown("")
#             for i, col in enumerate(st.columns(5)):
#                 j = i + (row_id*5)
#                 col.image(image_links[j], use_column_width="always")
#                 col.markdown(f"<center>{titles[j]}<br/>\
#                             <a href='https://www.imdb.com/title/{tconsts[j]}/'>{ratings[j]}/10</a>\
#                             </center>", unsafe_allow_html=True)
#             if i == 4:
#                 row5 = True


# for i in range(3):
#     st.markdown("")
# if row5:
#     user_query2 = st.text_input('Your request', '', key="row5")

#     if user_query2:
#         query_embed = co.embed(
#             model='embed-english-v3.0',
#             texts=[user_query2],
#             input_type='search_query'
#         ).embeddings

#         candidates = index.query(
#             vector=query_embed[0],
#             top_k=n_movies_display,
#             include_metadata=True
#         )
#         titles = [x["metadata"]["primaryTitle"] for x in candidates["matches"]]
#         ratings = [x["metadata"]["averageRating"] for x in candidates["matches"]]
#         image_links = [x["metadata"]["small_cover"] for x in candidates["matches"]]
#         tconsts = [x["metadata"]["tconst"] for x in candidates["matches"]]

#         n_rows = round(n_movies_display / 5)
#         for row_id in range(n_rows):
#             if row_id > 0:
#                 for _ in range(2):
#                     st.markdown("")
#             for i, col in enumerate(st.columns(5)):
#                 j = i + (row_id*5)
#                 col.image(image_links[j], use_column_width="always")
#                 col.markdown(f"<center>{titles[j]}<br/>\
#                             <a href='https://www.imdb.com/title/{tconsts[j]}/'>{ratings[j]}/10</a>\
#                             </center>", unsafe_allow_html=True)
#             if i == 4:
#                 row6 = True

def send_text_feedback(text):
    response = dynamodb_text_feedback.put_item(
    Item = {
            'time': datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
            "hash": generate_random_string(8),
            'text': text,
        }
    )
    return response
    
for _ in range(5):
    st.markdown("")

with st.expander("Feedback"):
    feedback = st.text_area("Share your feedback, even 1 sentence is appreciated :)", key="fb")
    feedback_col1, feedback_col2, feedback_col3 = st.columns([0.2, 0.3, 0.5])
    if feedback_col1.button("Send", use_container_width=True):
        with feedback_col2:
            with st.spinner("Sending..."):
                send_text_feedback(feedback)
                sleep(1)
                st.text("Sent, thank you!")
