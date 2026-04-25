const ARTICLES = [
  {
    id: 1,
    type: "news",
    title: "EMA launches updated reflection paper on AI and machine learning in drug development",
    excerpt: "The European Medicines Agency releases revised guidance on the use of machine learning algorithms in regulatory submissions, emphasising model explainability, validation requirements, and lifecycle management.",
    source: "EMA",
    date: "2026-04-22",
    tags: ["EMA", "Regulatory", "Machine learning", "Guidance"],
    featured: true,
    readTime: "5 min",
    url: "#",
    badge: "Breaking"
  },
  {
    id: 2,
    type: "paper",
    title: "Graph neural networks for drug–target interaction prediction: a systematic review",
    excerpt: "Comprehensive review of 142 studies evaluating GNN architectures for predicting drug-target binding affinity, with benchmarks across ChEMBL and BindingDB datasets.",
    source: "Nature Drug Discovery",
    date: "2026-04-20",
    tags: ["GNN", "Drug discovery", "Deep learning", "DTI"],
    featured: true,
    readTime: "25 min",
    url: "#",
    badge: "Open Access"
  },
  {
    id: 3,
    type: "webinar",
    title: "AI in clinical trials: adaptive designs and real-world evidence",
    excerpt: "Experts from Roche, Novartis, and the FDA discuss how AI-driven adaptive trial designs are reshaping clinical development timelines and changing regulatory expectations for evidence packages.",
    source: "DIA Europe",
    date: "2026-04-28",
    tags: ["Clinical trials", "RWE", "Adaptive design"],
    featured: false,
    readTime: "90 min",
    url: "#",
    badge: "Live",
    eventDate: "28 April 2026 — 14:00 CET"
  },
  {
    id: 4,
    type: "seminar",
    title: "Regulatory pathways for AI-assisted drug products: PRIME, conditional MA and CHMP expectations",
    excerpt: "Full-day seminar exploring the PRIME scheme, conditional marketing authorisation, and how AI-generated evidence should be structured and presented in CHMP dossier submissions.",
    source: "EMA / Medicines for Europe",
    date: "2026-05-15",
    tags: ["CHMP", "PRIME", "Regulatory", "EU"],
    featured: true,
    readTime: "Full day",
    url: "#",
    badge: "Regulatory",
    eventDate: "15 May 2026 — Brussels"
  },
  {
    id: 5,
    type: "news",
    title: "First AI-designed small molecule reaches Phase II: a regulatory milestone for the field",
    excerpt: "An AI-designed small molecule candidate advances to Phase II clinical trials, marking a significant step in demonstrating that fully AI-driven drug design pipelines can meet regulatory standards for human studies.",
    source: "Nature Biotechnology",
    date: "2026-04-18",
    tags: ["AI drug design", "Phase II", "Clinical development", "Milestone"],
    featured: false,
    readTime: "4 min",
    url: "#",
    badge: "Milestone"
  },
  {
    id: 6,
    type: "paper",
    title: "Federated learning for multi-site pharmacovigilance signal detection",
    excerpt: "Novel federated architecture enabling cross-institutional safety signal analysis without sharing patient-level data, validated across six EU national pharmacovigilance databases.",
    source: "The Lancet Digital Health",
    date: "2026-04-15",
    tags: ["Federated learning", "Pharmacovigilance", "Privacy", "EU"],
    featured: false,
    readTime: "18 min",
    url: "#",
    badge: "Open Access"
  },
  {
    id: 7,
    type: "news",
    title: "EU research network publishes open framework for validating AI models in regulatory dossiers",
    excerpt: "A publicly available validation framework for AI/ML models intended for inclusion in regulatory dossiers across EMA member states, covering explainability requirements, drift detection, and audit trail standards.",
    source: "IMI / IHI network",
    date: "2026-04-12",
    tags: ["Validation", "Framework", "IMI", "Regulatory"],
    featured: false,
    readTime: "6 min",
    url: "#",
    badge: "Policy"
  },
  {
    id: 8,
    type: "webinar",
    title: "Large language models in medical writing: opportunities and regulatory red lines",
    excerpt: "Practical session on integrating LLMs into CTD module preparation, with input from EMA assessors on acceptable use cases and submission standards for AI-assisted regulatory documents.",
    source: "DIA Europe",
    date: "2026-05-06",
    tags: ["LLM", "Medical writing", "CTD", "Regulatory"],
    featured: false,
    readTime: "60 min",
    url: "#",
    badge: "Upcoming",
    eventDate: "6 May 2026 — 15:00 CET"
  },
  {
    id: 9,
    type: "paper",
    title: "AlphaFold3 in structure-based drug design: one year of industrial application",
    excerpt: "Industry-wide retrospective assessing the impact of AlphaFold3 on hit-to-lead optimisation campaigns across 24 pharmaceutical companies, including success rates, practical limitations, and failure modes.",
    source: "Journal of Medicinal Chemistry",
    date: "2026-04-10",
    tags: ["AlphaFold3", "SBDD", "Protein structure", "Lead optimisation"],
    featured: false,
    readTime: "30 min",
    url: "#",
    badge: "High Impact"
  },
  {
    id: 10,
    type: "seminar",
    title: "EUDRACON AI working group: data standards for AI-enabled regulatory submissions",
    excerpt: "Annual gathering of EU drug regulatory agency representatives to align on IDMP, FHIR, and SEND data standards in the context of AI-generated evidence packages.",
    source: "EUDRACON",
    date: "2026-06-03",
    tags: ["EUDRACON", "Data standards", "IDMP", "FHIR"],
    featured: false,
    readTime: "2 days",
    url: "#",
    badge: "Regulatory",
    eventDate: "3–4 June 2026 — Amsterdam"
  },
  {
    id: 11,
    type: "news",
    title: "European Health Data Space (EHDS) enters into force: implications for AI research",
    excerpt: "EHDS provisions now apply across EU member states, enabling secondary use of electronic health record data for AI model training under national health data access body oversight and governance frameworks.",
    source: "European Commission",
    date: "2026-04-08",
    tags: ["EHDS", "EU policy", "Data governance", "EHR"],
    featured: false,
    readTime: "7 min",
    url: "#",
    badge: "Policy"
  },
  {
    id: 12,
    type: "paper",
    title: "Generative chemistry with diffusion models: beyond novelty metrics",
    excerpt: "Critical analysis of 89 generative molecular design papers, arguing that synthesisability, ADMET profile, and target selectivity should replace novelty as the primary evaluation criteria for AI-generated molecules.",
    source: "ACS Medicinal Chemistry Letters",
    date: "2026-04-05",
    tags: ["Generative AI", "Molecular design", "ADMET", "Diffusion models"],
    featured: false,
    readTime: "15 min",
    url: "#",
    badge: "Perspective"
  }
];

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
