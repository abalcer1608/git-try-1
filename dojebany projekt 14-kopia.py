import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob
from dash import Dash, dcc, html
from datetime import datetime

# Ścieżka do folderu z danymi
data_folder = os.path.join(os.path.dirname(__file__), 'data')

# Pobierz wszystkie pliki z kwietnia 2025
all_files = glob.glob(os.path.join(data_folder, '*EPWA_2025-04-*.csv'))

# Wczytaj i połącz dane z plików
dfs = []
for file in all_files:
    df = pd.read_csv(file)
    df['source'] = os.path.basename(file).split('_')[0]  # 'arrivals' lub 'departures'
    dfs.append(df)

df = pd.concat(dfs, ignore_index=True)

# Konwersja dat i czasów
df['lastSeen'] = pd.to_datetime(df['lastSeen'], errors='coerce')
df = df.dropna(subset=['lastSeen'])

df['hour'] = df['lastSeen'].dt.hour
df['day'] = df['lastSeen'].dt.day
df['day_of_week'] = df['lastSeen'].dt.day_name()

# Mapowanie nazw dni na polski
day_names_pl = {
    'Monday': 'Poniedziałek',
    'Tuesday': 'Wtorek',
    'Wednesday': 'Środa',
    'Thursday': 'Czwartek',
    'Friday': 'Piątek',
    'Saturday': 'Sobota',
    'Sunday': 'Niedziela'
}
df['day_of_week_pl'] = df['day_of_week'].map(day_names_pl)
df['is_weekend'] = df['lastSeen'].dt.dayofweek >= 5

# Grupowanie do animacji
hourly_counts = df.groupby(['day', 'hour', 'day_of_week_pl', 'is_weekend']).size().reset_index(name='count')

# Upewnij się, że mamy wszystkie godziny (0-23) dla każdego dnia
all_hours = pd.DataFrame({'hour': range(24)})
all_days = hourly_counts['day'].unique()
complete_data = []

for day in all_days:
    day_data = hourly_counts[hourly_counts['day'] == day]
    day_name = day_data['day_of_week_pl'].iloc[0]
    is_weekend = day_data['is_weekend'].iloc[0]

    merged = pd.merge(all_hours, day_data, on='hour', how='left')
    merged['day'] = day
    merged['day_of_week_pl'] = day_name
    merged['is_weekend'] = is_weekend
    merged['count'] = merged['count'].fillna(0)

    complete_data.append(merged)

hourly_counts = pd.concat(complete_data).reset_index(drop=True)

# Oblicz godzinę szczytu dla każdego dnia
peak_hours_daily = hourly_counts.loc[hourly_counts.groupby('day')['count'].idxmax()]

# Oblicz średnie godziny szczytu
# Dla każdego dnia tygodnia (zachowując kolejność)
weekday_order = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']
hourly_counts['day_of_week_pl'] = pd.Categorical(hourly_counts['day_of_week_pl'], categories=weekday_order,
                                                 ordered=True)

peak_hours_by_weekday = hourly_counts.groupby(['day_of_week_pl', 'hour'])['count'].mean().reset_index()
peak_hours_by_weekday = peak_hours_by_weekday.loc[peak_hours_by_weekday.groupby('day_of_week_pl')['count'].idxmax()]

# Dla dni roboczych i weekendów
peak_hours_by_weekend = hourly_counts.groupby(['is_weekend', 'hour'])['count'].mean().reset_index()
peak_hours_by_weekend = peak_hours_by_weekend.loc[peak_hours_by_weekend.groupby('is_weekend')['count'].idxmax()]
peak_hours_by_weekend['type'] = peak_hours_by_weekend['is_weekend'].map({True: 'Weekend', False: 'Dzień roboczy'})

# Wykres animowany
fig = px.bar(
    hourly_counts,
    x='hour',
    y='count',
    color='is_weekend',
    animation_frame='day',
    range_x=[-0.5, 23.5],  # Wymuszamy pełny zakres godzin
    range_y=[0, hourly_counts['count'].max() + 10],
    title='<b>⏰ Dzienny rytm ruchu lotniczego EPWA - Kwiecień 2025</b><br><i>Animacja pokazująca zmiany godzinowe dzień po dniu</i>',
    labels={'hour': 'Godzina', 'count': 'Liczba lotów'},
    color_discrete_map={True: '#FF7F0E', False: '#1F77B4'},
    category_orders={'day': sorted(hourly_counts['day'].unique())}
)

# Ukryj legendę i dostosuj układ
fig.update_layout(
    showlegend=False,
    xaxis=dict(
        tickmode='array',
        tickvals=list(range(24)),
        ticktext=[f"{h}:00" for h in range(24)],
        title='Godzina'
    ),
    yaxis=dict(title='Liczba lotów'),
    plot_bgcolor='white',
    hovermode='x unified',
    updatemenus=[{
        'buttons': [
            {
                'args': [None, {'frame': {'duration': 1000, 'redraw': True},
                                'fromcurrent': True,
                                'transition': {'duration': 500, 'easing': 'quadratic-in-out'}}],
                'label': 'Play',
                'method': 'animate'
            },
            {
                'args': [[None], {'frame': {'duration': 0, 'redraw': True},
                                  'mode': 'immediate',
                                  'transition': {'duration': 0}}],
                'label': 'Pause',
                'method': 'animate'
            }
        ],
        'direction': 'left',
        'pad': {'r': 10, 't': 87},
        'showactive': False,
        'type': 'buttons',
        'x': 0.1,
        'xanchor': 'right',
        'y': 0,
        'yanchor': 'top'
    }],
    margin=dict(b=150, t=100)
)

# Dynamiczne adnotacje dla każdego dnia
frames = []
for day in sorted(hourly_counts['day'].unique()):
    frame_data = hourly_counts[hourly_counts['day'] == day]
    day_name = frame_data['day_of_week_pl'].iloc[0]
    peak_hour = peak_hours_daily[peak_hours_daily['day'] == day]['hour'].values[0]
    peak_count = peak_hours_daily[peak_hours_daily['day'] == day]['count'].values[0]

    frames.append(
        go.Frame(
            data=[
                go.Bar(
                    x=frame_data['hour'],
                    y=frame_data['count'],
                    marker_color=['#FF7F0E' if w else '#1F77B4' for w in frame_data['is_weekend']]
                )
            ],
            name=str(day),
            layout=go.Layout(
                annotations=[
                    dict(
                        x=0.5,
                        y=1.1,
                        xref='paper',
                        yref='paper',
                        text=f'Dzień: {day} ({day_name})',
                        showarrow=False,
                        font=dict(size=14),
                        xanchor='center'
                    ),
                    dict(
                        x=0.5,
                        y=1.02,
                        xref='paper',
                        yref='paper',
                        text=f'Godzina największego ruchu: {peak_hour}:00 ({int(peak_count)} lotów)',
                        showarrow=False,
                        font=dict(size=12, color='#D62728'),
                        xanchor='center'
                    )
                ]
            )
        )
    )

fig.frames = frames

# Przygotowanie statystyk w odpowiedniej kolejności
weekday_stats = []
for day in weekday_order:
    row = peak_hours_by_weekday[peak_hours_by_weekday['day_of_week_pl'] == day]
    if not row.empty:
        weekday_stats.append(f"{day}: {int(row['hour'].values[0])}:00")

stats_text = [
    html.H4("Średnie godziny największego ruchu w kwietniu 2025:"),
    html.P("Dla dni tygodnia:", style={'font-weight': 'bold', 'margin-bottom': '5px'}),
    html.Ul([html.Li(stat) for stat in weekday_stats]),
    html.P(
        f"Dla dni roboczych: {int(peak_hours_by_weekend[peak_hours_by_weekend['is_weekend'] == False]['hour'].values[0])}:00",
        style={'font-weight': 'bold', 'margin-top': '10px'}),
    html.P(
        f"Dla weekendów: {int(peak_hours_by_weekend[peak_hours_by_weekend['is_weekend'] == True]['hour'].values[0])}:00",
        style={'font-weight': 'bold'})
]

# Utwórz aplikację Dash
app = Dash(__name__)

app.layout = html.Div([
    html.Div(
        dcc.Graph(figure=fig),
        style={'width': '80%', 'margin': 'auto'}
    ),
    html.Div(
        stats_text,
        style={
            'width': '80%',
            'margin': '20px auto',
            'padding': '15px',
            'border': '1px solid #ddd',
            'border-radius': '5px',
            'background-color': '#f9f9f9'
        }
    )
])
server = app.server
if __name__ == '__main__':
    app.run(debug=True)