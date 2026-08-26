import { useEffect, useState } from "react";

const API = "http://localhost:8000";
const POLL_MS = 2000;

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function fmtRange(iso) {
  const d = parseDate(iso);
  return `${MONTHS[d.getMonth()][0] + MONTHS[d.getMonth()].slice(1).toLowerCase()} ${d.getDate()}`;
}

function fmtTime(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

function DateChip({ iso }) {
  const d = parseDate(iso);
  return (
    <div className="date-chip">
      <span className="date-chip-month">{MONTHS[d.getMonth()]}</span>
      <span className="date-chip-day">{d.getDate()}</span>
    </div>
  );
}

function ProgressRing({ completed }) {
  return (
    <div className={`ring ${completed ? "ring-done" : ""}`}>
      {completed ? "✓" : "0%"}
    </div>
  );
}

function ResourceButton({ res }) {
  if (res.kind === "text") {
    return (
      <span className="res-btn res-text" title={res.text}>
        📄 {res.label}
      </span>
    );
  }
  if (!res.url) {
    return <span className="res-btn res-placeholder">🎥 {res.label} · soon</span>;
  }
  const icon = res.label.toLowerCase().includes("slide") ? "🗂" : "🎥";
  return (
    <a className="res-btn res-link" href={res.url} target="_blank" rel="noreferrer">
      {icon} {res.label}
    </a>
  );
}

function ItemCard({ item }) {
  const isGroup = item.type === "topic_group" || item.type === "reading";
  const dateLine = item.date ? (
    <div className="item-sub">
      {DAYS[parseDate(item.date).getDay()]} {parseDate(item.date).getMonth() + 1}/{parseDate(item.date).getDate()}
      {item.start_time && (
        <>
          {" "}· {fmtTime(item.start_time)}—{fmtTime(item.end_time)} ({item.timezone})
        </>
      )}
      {item.optional && <span className="optional-tag">OPTIONAL</span>}
    </div>
  ) : null;

  return (
    <div className="card">
      <div className="card-left">
        {item.date ? <DateChip iso={item.date} /> : <span className="chevron">›</span>}
        <div>
          <div className="item-title">{item.title}</div>
          {dateLine}
          {isGroup && (
            <div className="item-count">{item.resources.length} ITEMS</div>
          )}
        </div>
      </div>
      <div className="card-right">
        {!isGroup && item.resources.map((res) => <ResourceButton key={res.id} res={res} />)}
        {isGroup && <ProgressRing completed={item.completed} />}
      </div>
      {isGroup && item.resources.length > 0 && (
        <div className="group-resources">
          {item.resources.map((res) => (
            <ResourceButton key={res.id} res={res} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [course, setCourse] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const fetchCourse = async () => {
      try {
        const res = await fetch(`${API}/curriculum`);
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        const data = await res.json();
        if (alive) {
          setCourse(data);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    };
    fetchCourse();
    const id = setInterval(fetchCourse, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (error && !course) {
    return (
      <div className="page">
        <div className="banner-error">
          Can't reach the API at {API} — is the backend running? ({error})
        </div>
      </div>
    );
  }
  if (!course) return <div className="page">Loading…</div>;

  return (
    <div className="page">
      <header className="course-header">
        <h1>{course.title}</h1>
        <p>{course.subtitle}</p>
        {error && <div className="banner-warn">Live updates paused: {error}</div>}
      </header>
      {course.weeks.map((week) => (
        <section key={week.number} className="week">
          <div className="week-header">
            <span className="week-label">Week {week.number}</span>
            <span className="week-dates">
              {fmtRange(week.start_date)}—{fmtRange(week.end_date)}
            </span>
            <span className="week-title">{week.title}</span>
          </div>
          {week.items.map((item) => (
            <ItemCard key={item.id} item={item} />
          ))}
        </section>
      ))}
      <footer className="footer">
        Read-only viewer · polls the API every {POLL_MS / 1000}s · changes made via MCP
        appear automatically
      </footer>
    </div>
  );
}
