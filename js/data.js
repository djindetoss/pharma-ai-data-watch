// Articles are now loaded exclusively from articles.json (pipeline-fetched, real sources).
// This fallback is intentionally empty — do not add manual entries here.
const ARTICLES = [];

const UPCOMING_EVENTS = [
  { title: "EMA Innovation Task Force briefing", date: "Apr 29", type: "webinar", location: "Online" },
  { title: "Pharma AI regulatory forum", date: "May 5", type: "seminar", location: "Brussels" },
  { title: "DIA webinar: LLMs in medical writing", date: "May 6", type: "webinar", location: "Online" },
  { title: "AI-assisted drug products seminar", date: "May 15", type: "seminar", location: "Brussels" },
  { title: "FDA CDER AI/ML workshop", date: "May 20", type: "seminar", location: "Hybrid" },
  { title: "EUDRACON AI working group", date: "Jun 3", type: "seminar", location: "Amsterdam" }
];

const STATS = [
  { label: "Resources indexed", value: "1,240+" },
  { label: "Topics covered", value: "18" },
  { label: "Agencies tracked", value: "27" },
  { label: "Updated", value: "Daily" }
];
