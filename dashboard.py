import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
import re
import requests
from io import StringIO

# Настройка страницы
st.set_page_config(layout="wide", page_title="Анализ чата Telegram")

# --- Загрузка данных из релиза на GitHub ---
@st.cache_data
def load_data():
    # ЗАМЕНИТЕ ЭТУ ССЫЛКУ НА ВАШУ!
    url = "https://github.com/yousergtube-rgb/telegram-chat-dashboard/releases/download/v1.0/chat_processed.csv"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"Не удалось загрузить данные. Код ошибки: {response.status_code}")
            return pd.DataFrame()  # возвращаем пустой DataFrame, чтобы приложение не падало
        # Парсим CSV прямо из содержимого ответа
        df = pd.read_csv(StringIO(response.text), parse_dates=['datetime'], low_memory=False)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame()

df = load_data()

# Если данные не загрузились, показываем сообщение и останавливаем выполнение
if df.empty:
    st.stop()

# --- Боковая панель с фильтрами ---
st.sidebar.header("🔍 Фильтры и настройки")

# 1. Выбор участников
participants = sorted(df['from'].unique())
selected_participants = st.sidebar.multiselect(
    "Выберите участников",
    options=participants,
    default=participants
)

# 2. Диапазон дат
min_date = df['datetime'].min().date()
max_date = df['datetime'].max().date()
date_range = st.sidebar.date_input(
    "Диапазон дат",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# 3. Минимальная длина текста
min_len = st.sidebar.slider("Минимальная длина текста (символов)", 0, 500, 0, step=5)

# 4. Тип сообщений (если есть колонка 'type')
if 'type' in df.columns:
    all_types = sorted(df['type'].unique())
    default_types = [t for t in all_types if t != 'service']
    selected_types = st.sidebar.multiselect(
        "Тип сообщений",
        options=all_types,
        default=default_types
    )
else:
    selected_types = None

# 5. Грануляция для динамики
granularity = st.sidebar.selectbox(
    "Грануляция динамики",
    options=['День', 'Неделя', 'Месяц'],
    index=0
)

# 6. Количество топ-слов для отображения
top_n = st.sidebar.slider("Количество топ-слов для отображения", 5, 50, 20, step=5)

# Применяем фильтры
filtered_df = df.copy()
filtered_df = filtered_df[filtered_df['from'].isin(selected_participants)]
filtered_df = filtered_df[
    (filtered_df['datetime'].dt.date >= date_range[0]) &
    (filtered_df['datetime'].dt.date <= date_range[1])
]
filtered_df = filtered_df[filtered_df['text_clean'].str.len() >= min_len]
if selected_types is not None:
    filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]

# --- Основной интерфейс ---
st.title("📊 Анализ чата Telegram")
st.markdown(f"**Отфильтровано:** {len(filtered_df)} сообщений")

# Ключевые метрики
col1, col2, col3, col4 = st.columns(4)
col1.metric("Всего сообщений", len(filtered_df))
if not filtered_df.empty:
    col2.metric("Участников", filtered_df['from'].nunique())
    col3.metric("Средняя длина", round(filtered_df['text_clean'].str.len().mean(), 1))
    top_user = filtered_df['from'].value_counts().index[0]
    col4.metric("Самый активный", top_user)

    sorted_df = filtered_df.sort_values('datetime')
    time_diff = sorted_df['datetime'].diff().dt.total_seconds()
    avg_response = time_diff[(time_diff > 0) & (time_diff < 86400)].mean()
    if not pd.isna(avg_response):
        st.metric("Средний интервал (сек)", round(avg_response, 1))
else:
    col2.metric("Участников", 0)
    col3.metric("Средняя длина", 0)
    col4.metric("Самый активный", "-")
    st.metric("Средний интервал (сек)", "-")

# --- Графики ---

# 1. Динамика с учётом грануляции
st.subheader("📈 Динамика сообщений")
if not filtered_df.empty:
    temp_df = filtered_df.set_index('datetime')
    if granularity == 'День':
        freq = 'D'
        label = 'день'
    elif granularity == 'Неделя':
        freq = 'W'
        label = 'неделя'
    else:
        freq = 'M'
        label = 'месяц'
    grouped = temp_df.resample(freq).size().reset_index(name='count')
    fig1 = px.line(grouped, x='datetime', y='count', title=f'Количество сообщений по {label}м')
    st.plotly_chart(fig1, width='stretch')
else:
    st.info("Нет данных для отображения динамики.")

# 2. Активность по часам
st.subheader("🕒 Активность по часам")
if not filtered_df.empty:
    hourly = filtered_df.groupby('hour').size().reset_index(name='count')
    fig2 = px.bar(hourly, x='hour', y='count', title='Сообщения по часам')
    st.plotly_chart(fig2, width='stretch')
else:
    st.info("Нет данных.")

# 3. Активность по дням недели
st.subheader("📅 Активность по дням недели")
if not filtered_df.empty:
    weekly = filtered_df.groupby('day_of_week').size().reset_index(name='count')
    order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    weekly['day_of_week'] = pd.Categorical(weekly['day_of_week'], categories=order, ordered=True)
    weekly = weekly.sort_values('day_of_week')
    fig3 = px.bar(weekly, x='day_of_week', y='count', title='Сообщения по дням недели')
    st.plotly_chart(fig3, width='stretch')
else:
    st.info("Нет данных.")

# 4. Распределение по участникам
st.subheader("👥 Сообщения по участникам")
if not filtered_df.empty:
    by_user = filtered_df['from'].value_counts().reset_index()
    by_user.columns = ['Участник', 'Количество']
    fig4 = px.bar(by_user, x='Участник', y='Количество', title='Кто сколько написал')
    st.plotly_chart(fig4, width='stretch')
else:
    st.info("Нет данных.")

# 5. Тепловая карта (день недели × час)
st.subheader("🔥 Тепловая карта активности (день недели × час)")
if not filtered_df.empty:
    pivot = filtered_df.pivot_table(index='day_of_week', columns='hour', aggfunc='size', fill_value=0)
    order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    pivot = pivot.reindex(order)
    fig5 = px.imshow(pivot, text_auto=True, aspect="auto", title='Количество сообщений')
    st.plotly_chart(fig5, width='stretch')
else:
    st.info("Нет данных.")

# 6. Топ N слов (столбчатая диаграмма)
st.subheader(f"🏆 Топ {top_n} самых частых слов")
if not filtered_df.empty:
    all_text = ' '.join(filtered_df['text_clean'])
    all_text = re.sub(r'[^\w\s]', '', all_text)
    all_text = re.sub(r'\d+', '', all_text)
    words = all_text.split()
    stopwords = {'и', 'в', 'на', 'с', 'по', 'к', 'у', 'же', 'но', 'а', 'за', 'из', 'от', 'для', 'о', 'не', 'да', 'бы', 'так', 'вот', 'ещё', 'только', 'уже', 'если', 'когда', 'что', 'как', 'это', 'тот', 'этот', 'все', 'всё', 'всю', 'всех', 'про', 'без', 'до', 'при', 'через', 'между', 'среди', 'из-за', 'из-под', 'над', 'под', 'об', 'от', 'перед', 'после', 'ради', 'через', 'со', 'было', 'были', 'будет', 'быть', 'этот', 'эта', 'это', 'эти', 'тот', 'та', 'те', 'свой', 'своя', 'своё', 'свои', 'весь', 'вся', 'всё', 'все', 'какой', 'какая', 'какое', 'какие', 'также', 'вроде', 'типа', 'потому', 'поэтому', 'когда', 'тогда', 'сейчас', 'сегодня', 'завтра', 'вчера'}
    words = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    if words:
        counter = Counter(words)
        top_words = counter.most_common(top_n)
        top_df = pd.DataFrame(top_words, columns=['Слово', 'Частота'])
        fig6 = px.bar(top_df, x='Слово', y='Частота', title=f'Топ {top_n} слов')
        st.plotly_chart(fig6, width='stretch')
    else:
        st.info("Недостаточно слов для отображения топа.")
else:
    st.info("Нет данных.")

# 7. Облако слов
st.subheader("☁️ Облако самых частых слов")
if not filtered_df.empty:
    all_text = ' '.join(filtered_df['text_clean'])
    all_text = re.sub(r'[^\w\s]', '', all_text)
    all_text = re.sub(r'\d+', '', all_text)
    words = all_text.split()
    stopwords = {'и', 'в', 'на', 'с', 'по', 'к', 'у', 'же', 'но', 'а', 'за', 'из', 'от', 'для', 'о', 'не', 'да', 'бы', 'так', 'вот', 'ещё', 'только', 'уже', 'если', 'когда', 'что', 'как', 'это', 'тот', 'этот', 'все', 'всё', 'всю', 'всех', 'про', 'без', 'до', 'при', 'через', 'между', 'среди', 'из-за', 'из-под', 'над', 'под', 'об', 'от', 'перед', 'после', 'ради', 'через', 'со', 'было', 'были', 'будет', 'быть', 'этот', 'эта', 'это', 'эти', 'тот', 'та', 'те', 'свой', 'своя', 'своё', 'свои', 'весь', 'вся', 'всё', 'все', 'какой', 'какая', 'какое', 'какие', 'также', 'вроде', 'типа', 'потому', 'поэтому', 'когда', 'тогда', 'сейчас', 'сегодня', 'завтра', 'вчера'}
    words = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    if words:
        wordcloud = WordCloud(
            width=800,
            height=400,
            background_color='white'
        ).generate(' '.join(words))
        fig7, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig7)
    else:
        st.info("Недостаточно слов для облака.")
else:
    st.info("Нет данных.")

# Таблица с данными
with st.expander("📄 Показать отфильтрованные сообщения"):
    if not filtered_df.empty:
        st.dataframe(filtered_df[['datetime', 'from', 'text_clean']].sort_values('datetime'))
    else:
        st.write("Нет данных для отображения.")
