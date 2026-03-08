import React, { useMemo, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';

const styles = {
  app: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #1a2a4a 0%, #2d4a7a 50%, #1e3a5f 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    padding: '24px',
    color: '#fff'
  },
  wrapper: { width: '100%', maxWidth: '680px' },
  header: { textAlign: 'center', marginBottom: '24px' },
  location: { fontSize: 13, color: '#7eb8f7', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 8 },
  icon: { fontSize: 70, lineHeight: 1 },
  temp: { fontSize: 66, lineHeight: 1, fontWeight: 200, marginTop: 6 },
  condition: { fontSize: 20, color: '#a8c8f0', marginTop: 6, fontWeight: 300 },
  date: { fontSize: 12, color: '#5a8abf', marginTop: 6 },
  tabs: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 12 },
  tab: {
    padding: '10px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.2)',
    background: 'rgba(255,255,255,0.08)', color: '#fff', fontWeight: 600, cursor: 'pointer'
  },
  tabActive: { background: 'rgba(126,184,247,0.2)', border: '1px solid rgba(126,184,247,0.45)' },
  metrics: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 },
  metric: {
    background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)',
    borderRadius: 16, padding: '14px 16px', backdropFilter: 'blur(12px)'
  },
  metricIcon: { fontSize: 20 },
  metricValue: { fontSize: 18, fontWeight: 600, marginTop: 4 },
  metricLabel: { fontSize: 12, color: '#7eb8f7', marginTop: 2 },
  panel: {
    background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)', borderRadius: 20,
    padding: 18, backdropFilter: 'blur(12px)'
  },
  panelTitle: { fontSize: 12, color: '#7eb8f7', letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 },
  days: { display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 8 },
  day: { textAlign: 'center', padding: '10px 8px', borderRadius: 12, border: '1px solid transparent', cursor: 'pointer' },
  dayActive: { background: 'rgba(126,184,247,0.2)', border: '1px solid rgba(126,184,247,0.4)' },
  dayName: { fontSize: 11, color: '#7eb8f7', marginBottom: 6 },
  dayIcon: { fontSize: 22, marginBottom: 6 },
  dayMain: { fontSize: 16, fontWeight: 600, marginBottom: 4 },
  daySub: { fontSize: 11, color: '#4a7aa8' },
  footer: { marginTop: 16, textAlign: 'center', fontSize: 12, color: '#3a6080' },
  empty: { border: '1px dashed #6a8cb6', borderRadius: 12, padding: 16, textAlign: 'center', color: '#90a8c8', gridColumn: '1 / -1' }
};

function toIcon(text) {
  const value = String(text || '').toLowerCase();
  if (value.includes('snow')) return '❄️';
  if (value.includes('rain') || value.includes('showers') || value.includes('drizzle')) return '🌧️';
  if (value.includes('sunny') || value.includes('clear')) return '☀️';
  if (value.includes('partly')) return '⛅';
  if (value.includes('cloud')) return '☁️';
  return '🌥️';
}

function firstWord(label) {
  return String(label || 'N/A').split(' ')[0];
}

function readToolResult(raw) {
  if (!raw) return null;
  if (raw.method === 'ui/notifications/tool-result') {
    return raw?.params?.result || raw?.params || raw?.result || null;
  }
  if (raw.type === 'toolResult') {
    return raw.result || null;
  }
  return null;
}

function App() {
  const [forecast, setForecast] = useState([]);
  const [location, setLocation] = useState(null);
  const [view, setView] = useState('temperature');
  const [activeDay, setActiveDay] = useState(0);

  const dayPeriods = useMemo(() => forecast.filter((_, i) => i % 2 === 0).slice(0, 5), [forecast]);
  const selected = dayPeriods[activeDay] || dayPeriods[0] || {};

  useEffect(() => {
    const onMessage = (event) => {
      const result = readToolResult(event.data || {});
      if (!result?._meta?.forecast || !Array.isArray(result._meta.forecast)) return;
      setForecast(result._meta.forecast);
      setLocation(result._meta.location || null);
      setActiveDay(0);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  function notifyViewChange(nextView) {
    const message = {
      method: 'ui/update-model-context',
      params: { content: [{ type: 'text', text: `User switched dashboard view to ${nextView}.` }] }
    };
    window.parent.postMessage(message, '*');
    window.parent.postMessage({ type: 'modelContextUpdate', payload: message.params }, '*');
  }

  function metricCards() {
    const precip = Number(selected.precipitationProbability || 0);
    const wind = Number(String(selected.windSpeed || '0').match(/\d+/)?.[0] || 0);
    const temp = Number(selected.temperature || 0);

    const base = [
      { label: 'Condition', value: selected.shortForecast || 'N/A', icon: toIcon(selected.shortForecast) },
      { label: 'Rain Chance', value: `${precip}%`, icon: '💧' },
      { label: 'Temperature', value: `${temp}°${selected.temperatureUnit || 'F'}`, icon: '🌡️' },
      { label: 'Wind', value: `${wind} mph`, icon: '💨' }
    ];

    if (view === 'precipitation') return [base[0], base[1], base[2], base[3]];
    if (view === 'wind') return [base[0], base[3], base[1], base[2]];
    return [base[0], base[2], base[1], base[3]];
  }

  function dayMain(day) {
    if (view === 'precipitation') return `${Number(day.precipitationProbability || 0)}%`;
    if (view === 'wind') return `${Number(String(day.windSpeed || '0').match(/\d+/)?.[0] || 0)} mph`;
    return `${Number(day.temperature || 0)}°`;
  }

  function daySub(day) {
    if (view === 'precipitation') return `${Number(day.temperature || 0)}°${day.temperatureUnit || 'F'}`;
    return `💧${Number(day.precipitationProbability || 0)}%`;
  }

  function panelTitle() {
    if (view === 'precipitation') return '5-Day Precipitation View';
    if (view === 'wind') return '5-Day Wind View';
    return '5-Day Temperature View';
  }

  const locText = location?.city ? `📍 ${location.city}${location.state ? `, ${location.state}` : ''}` : 'Loading location...';
  const dateText = new Date().toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });

  return (
    <div style={styles.app}>
      <main style={styles.wrapper}>
        <section style={styles.header}>
          <div style={styles.location}>{locText}</div>
          <div style={styles.icon}>{toIcon(selected.shortForecast)}</div>
          <div style={styles.temp}>{selected.temperature ?? '--'}°</div>
          <div style={styles.condition}>{selected.shortForecast || 'Waiting for forecast data...'}</div>
          <div style={styles.date}>{dateText}</div>
        </section>

        <section style={styles.tabs}>
          {['temperature', 'precipitation', 'wind'].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => {
                setView(tab);
                notifyViewChange(tab);
              }}
              style={{ ...styles.tab, ...(view === tab ? styles.tabActive : null) }}
            >
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </section>

        <section style={styles.metrics}>
          {forecast.length === 0 && <div style={styles.empty}>No weather metrics available yet.</div>}
          {forecast.length > 0 && metricCards().map((card) => (
            <article key={card.label} style={styles.metric}>
              <div style={styles.metricIcon}>{card.icon}</div>
              <div style={styles.metricValue}>{card.value}</div>
              <div style={styles.metricLabel}>{card.label}</div>
            </article>
          ))}
        </section>

        <section style={styles.panel}>
          <div style={styles.panelTitle}>{panelTitle()}</div>
          <div style={styles.days}>
            {dayPeriods.length === 0 && <div style={styles.empty}>No forecast cards available yet.</div>}
            {dayPeriods.map((day, idx) => (
              <article
                key={`${day.name}-${idx}`}
                onClick={() => setActiveDay(idx)}
                style={{ ...styles.day, ...(activeDay === idx ? styles.dayActive : null) }}
              >
                <div style={styles.dayName}>{firstWord(day.name)}</div>
                <div style={styles.dayIcon}>{toIcon(day.shortForecast)}</div>
                <div style={styles.dayMain}>{dayMain(day)}</div>
                <div style={styles.daySub}>{daySub(day)}</div>
              </article>
            ))}
          </div>
        </section>

        <div style={styles.footer}>Powered by weather-forecast-mcp-server v1.2.0 · React UI</div>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
