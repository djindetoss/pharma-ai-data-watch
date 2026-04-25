// Articles are now loaded exclusively from articles.json (pipeline-fetched, real sources).
// This fallback is intentionally empty — do not add manual entries here.
const ARTICLES = [];

// Curated upcoming events — shown as sidebar fallback when pipeline has not yet
// fetched webinar/seminar articles. URLs link to the real registration pages.
const UPCOMING_EVENTS = [
  {
    title: "Bio-IT World Expo — AI for drug discovery & development",
    date: "May 18",
    type: "seminar",
    location: "Boston, MA & Virtual",
    url: "https://www.bio-itworldexpo.com/ai-pharma-biotech"
  },
  {
    title: "PD2M AI for pharma conference — AIChE",
    date: "Jun 1",
    type: "seminar",
    location: "Virtual / TBC",
    url: "https://www.aiche.org/conferences/pd2m-ai-pharma/2026"
  },
  {
    title: "AI and data in pharma & healthcare summit",
    date: "Jun 15",
    type: "seminar",
    location: "Virtual",
    url: "https://berryprofessionals.com/ai-and-data-in-pharma-and-healthcare-summit-june-2026/"
  },
  {
    title: "Digi-Tech Pharma & AI 2026 — premier pharma tech conference",
    date: "Sep 1",
    type: "seminar",
    location: "TBC",
    url: "https://corvusglobalevents.com/digi-tech-pharma-ai/overview"
  },
  {
    title: "AI drug discovery & development summit 2026",
    date: "Oct 1",
    type: "seminar",
    location: "TBC",
    url: "https://aidrivendrugdevelopment.com/events/ai-drug-discovery-development-summit"
  },
  {
    title: "Pharma & biotech conference directory 2026 — 189 life sciences events",
    date: "Ongoing",
    type: "seminar",
    location: "Global",
    url: "https://intuitionlabs.ai/conferences"
  },
];

const STATS = [
  { label: "Resources indexed", value: "1,240+" },
  { label: "Topics covered", value: "18" },
  { label: "Agencies tracked", value: "27" },
  { label: "Updated", value: "Daily" }
];
