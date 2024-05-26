import os
from dotenv import load_dotenv
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
URL = "https://wykop.pl/api/v3"
AUTH_JSON = {"data": {"key": API_KEY, "secret": API_SECRET}}

st.set_page_config(layout="wide")


@st.cache_data
def get_auth_token():
    try:
        auth_data = requests.post(f"{URL}/auth", json=AUTH_JSON).json()
        return auth_data["data"]["token"]
    except Exception as e:
        st.error(f"Error obtaining auth token: {e}")
        return None


def extract_data(user_content):
    keys_to_extract = ["created_at", "tags", "content"]
    return [{k: d[k] for k in keys_to_extract} for d in user_content]


@st.cache_data
def get_user_stats(headers, username):
    user_content = []
    page = 1
    while True:
        response = requests.get(
            f"{URL}/profile/users/{username}/entries/added?limit=100&page={page}",
            headers=headers,
        )
        if response.status_code != 200:
            st.error(f"Error fetching data for user {username}: {response.status_code}")
            break
        user_tmp_content = response.json().get("data", [])
        if not user_tmp_content:
            break
        user_content.extend(user_tmp_content)
        page += 1

    return extract_data(user_content)


def generate_charts(content):
    df = pd.DataFrame(content)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date
    df["hour"] = df["created_at"].dt.hour
    df["day_of_week"] = df["created_at"].dt.day_name(locale="pl_PL")

    # Explode the tags list to count each tag separately
    df_tags = df.explode("tags")

    # Chart 1: Number of posts per tag
    tags_count = df_tags["tags"].value_counts().reset_index()
    tags_count.columns = ["Tag", "Count"]
    fig1 = px.bar(tags_count, x="Tag", y="Count", title="Liczba postów na tag")

    # Chart 2: Number of posts over time
    date_range = pd.date_range(start=df["date"].min(), end=df["date"].max())
    posts_over_time = (
        df["date"]
        .value_counts()
        .sort_index()
        .reindex(date_range, fill_value=0)
        .reset_index()
    )
    posts_over_time.columns = ["Data", "Liczba postów"]
    fig2 = px.line(
        posts_over_time, x="Data", y="Liczba postów", title="Liczba postów w czasie"
    )

    # Form to add highlights
    st.sidebar.header("Zaznacz dni szczególne")
    with st.sidebar.form(key="highlight_form"):
        highlight_date = st.date_input(
            "Wybierz datę",
            min_value=df["date"].min(),
            max_value=df["date"].max(),
        )
        highlight_text = st.text_area("Tekst wyróżnienia")
        submit_button = st.form_submit_button(label="Dodaj wyróżnienie")

    clear_button = st.sidebar.button("Wyczyść wyróżnienia")

    if "highlights" not in st.session_state:
        st.session_state["highlights"] = {}
    if submit_button and highlight_text:
        st.session_state["highlights"][highlight_date] = highlight_text

    if clear_button:
        st.session_state["highlights"] = {}

    for date, highlight in st.session_state["highlights"].items():
        fig2.add_vline(x=date, line_dash="dash", line_color="red")
        fig2.add_annotation(
            x=date,
            y=max(posts_over_time["Liczba postów"]),
            text=highlight,
            showarrow=True,
            arrowhead=1,
        )

    # Group less frequent tags into "Other"
    threshold = 2
    tags_count["Tag"] = tags_count.apply(
        lambda x: x["Tag"] if x["Count"] > threshold else "Inne", axis=1
    )
    tags_count = tags_count.groupby("Tag")["Count"].sum().reset_index()

    # Chart 3: Distribution of Tags (Pie Chart)
    fig3 = px.pie(tags_count, names="Tag", values="Count", title="Rozkład tagów")

    # Chart 4: Frequency of Posts by Day of Week (Unsorted)
    day_of_week_order = [
        "Poniedziałek",
        "Wtorek",
        "Środa",
        "Czwartek",
        "Piątek",
        "Sobota",
        "Niedziela",
    ]
    day_of_week_count = (
        df["day_of_week"].value_counts().reindex(day_of_week_order).reset_index()
    )
    day_of_week_count.columns = ["Dzień", "Liczba postów"]
    fig4 = px.bar(
        day_of_week_count,
        x="Dzień",
        y="Liczba postów",
        title="Częstotliwość postów w dni tygodnia",
    )

    # Chart 5: Frequency of Posts by Hour of Day
    hour_of_day_count = df["hour"].value_counts().sort_index().reset_index()
    hour_of_day_count.columns = ["Godzina", "Liczba postów"]
    fig5 = px.bar(
        hour_of_day_count,
        x="Godzina",
        y="Liczba postów",
        title="Częstotliwość postów wg godzin",
    )

    # Display the charts in a grid layout
    st.plotly_chart(fig2, use_container_width=True)
    st.plotly_chart(fig1, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig4, use_container_width=True)
        st.plotly_chart(fig3, use_container_width=True)
    with col2:
        st.plotly_chart(fig5, use_container_width=True)

    # Add a table at the bottom to browse through all the posts
    st.subheader("Przeglądaj posty")
    st.dataframe(df[["created_at", "tags", "content"]])


def main():
    st.title("Wykop Statystyki")
    token = get_auth_token()
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        query_params = st.query_params
        username = query_params.get("username", "m__b")

        username_input = st.text_input("Wpisz nazwę użytkownika", value=username)
        if username_input:
            stats = get_user_stats(headers, username_input)
            if stats:
                generate_charts(stats)
            else:
                st.write("Nie znaleziono danych dla tego użytkownika.")
    else:
        st.write("Nie udało się uzyskać tokenu autoryzacyjnego.")


if __name__ == "__main__":
    main()
