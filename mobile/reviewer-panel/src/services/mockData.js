// Mock data simulating the FastAPI backend responses
// In production, replace with actual API calls

const REPORTERS = [
  { id: 'r1', name: 'Jordan Dale', phone: '+91-9876543210', areaName: 'Bhubaneswar', organization: 'Vrittant News', initials: 'JD', color: '#FA6C38' },
  { id: 'r2', name: 'Sarah Weaver', phone: '+91-9876543211', areaName: 'Cuttack', organization: 'Vrittant News', initials: 'SW', color: '#3D3B8E' },
  { id: 'r3', name: 'Marcus King', phone: '+91-9876543212', areaName: 'Puri', organization: 'Vrittant News', initials: 'MK', color: '#14B8A6' },
  { id: 'r4', name: 'Elena Lopez', phone: '+91-9876543213', areaName: 'Rourkela', organization: 'Vrittant News', initials: 'EL', color: '#6366F1' },
  { id: 'r5', name: 'Priya Sharma', phone: '+91-9876543214', areaName: 'Sambalpur', organization: 'Vrittant News', initials: 'PS', color: '#EC4899' },
  { id: 'r6', name: 'Arjun Patel', phone: '+91-9876543215', areaName: 'Berhampur', organization: 'Vrittant News', initials: 'AP', color: '#F59E0B' },
  { id: 'r7', name: 'Deepak Mohanty', phone: '+91-9876543216', areaName: 'Balasore', organization: 'Vrittant News', initials: 'DM', color: '#10B981' },
  { id: 'r8', name: 'Suman Das', phone: '+91-9876543217', areaName: 'Angul', organization: 'Vrittant News', initials: 'SD', color: '#EF4444' },
  { id: 'r9', name: 'Neha Mishra', phone: '+91-9876543218', areaName: 'Koraput', organization: 'Vrittant News', initials: 'NM', color: '#8B5CF6' },
  { id: 'r10', name: 'Ravi Kumar', phone: '+91-9876543219', areaName: 'Jharsuguda', organization: 'Vrittant News', initials: 'RK', color: '#0EA5E9' },
  { id: 'r11', name: 'Anita Behera', phone: '+91-9876543220', areaName: 'Kendrapara', organization: 'Vrittant News', initials: 'AB', color: '#D97706' },
  { id: 'r12', name: 'Bikash Nayak', phone: '+91-9876543221', areaName: 'Jagatsinghpur', organization: 'Vrittant News', initials: 'BN', color: '#059669' },
];

const CATEGORIES = [
  'politics', 'sports', 'crime', 'business',
  'entertainment', 'education', 'health', 'technology',
  'urban_planning', 'sustainability', 'economics', 'lifestyle', 'finance'
];

const STATUSES = ['submitted', 'in_progress', 'approved', 'rejected', 'flagged', 'published'];

const HEADLINES = [
  'The Urban Infrastructure Shift in Metropolitan Areas',
  'Renewable Energy Adoption Trends 2024',
  'The Rise of Remote Tech Hubs in South Asia',
  'Local Market Fluctuations: Impact on Global Trade',
  'Global Summit on Climate Action: Key Takeaways',
  'Quantum Supremacy: Google vs IBM Update',
  'Modern Minimalism in Urban Spaces',
  'The Future of Decentralized Banking',
  'Electoral Reform: The Impact of AI in Polls',
  'The Rise of Generative Video Models',
  'New Education Policy Implementation Across States',
  'Healthcare Infrastructure in Rural Odisha',
  'Cyclone Preparedness: Lessons from Recent Storms',
  'Digital Literacy Program Reaches 10,000 Villages',
  'Sports Academy Opens in Bhubaneswar',
  'Crime Rate Drops 15% in Twin Cities',
  'Local Startup Raises ₹50 Crore Series A',
  'Temple Conservation Project Gains UNESCO Attention',
  'Farmers Protest Against New Irrigation Policy',
  'Smart City Initiative: Phase 2 Launched',
  'Odisha Film Industry: A New Dawn',
  'Coastal Erosion Threatens Fishing Communities',
  'Railway Expansion Plan for Western Odisha',
  'Tribal Art Festival Draws International Crowd',
  'Air Quality Index Improves After Green Drive',
  'New Medical College Approved for Koraput',
  'IT Park Construction Begins in Jatni',
  'Women Self-Help Groups Transform Rural Economy',
  'Flood Relief: Government Announces ₹500 Crore Package',
  'Heritage Walk Initiative in Old Town Bhubaneswar',
];

const BODY_TEXTS = [
  `The urban infrastructure landscape is undergoing a significant transformation as metropolitan areas adapt to post-pandemic realities. City planners are reimagining public spaces, transportation networks, and housing developments to create more resilient and livable environments.\n\nKey developments include the expansion of cycling infrastructure, the integration of green corridors into existing urban fabric, and the adoption of smart city technologies that promise to reduce energy consumption by up to 30% over the next decade.`,
  `Renewable energy adoption has accelerated dramatically across South Asia, with India leading the charge in solar and wind installations. The latest data shows a 40% increase in renewable capacity additions compared to the previous year.\n\nGovernment incentives, declining technology costs, and growing environmental awareness among consumers have all contributed to this surge. Industry experts predict that renewable sources could account for 50% of India's energy mix by 2030.`,
  `The phenomenon of remote tech hubs emerging in smaller cities across South Asia represents a fundamental shift in how technology companies approach talent acquisition and office space. Cities like Bhubaneswar, Jaipur, and Kochi are becoming attractive alternatives to traditional tech centers.\n\nLower cost of living, improved digital infrastructure, and quality of life considerations are driving this trend. Several multinational corporations have already established satellite offices in these emerging hubs.`,
  `Global trade dynamics are being reshaped by local market fluctuations driven by geopolitical tensions, supply chain disruptions, and changing consumer preferences. The ripple effects of these local changes are increasingly felt across international markets.\n\nAnalysts point to the growing interconnectedness of regional economies as a key factor amplifying the impact of local market movements on global trade flows.`,
];

function randomDate(hoursBack) {
  const now = new Date();
  const ms = Math.random() * hoursBack * 60 * 60 * 1000;
  return new Date(now.getTime() - ms);
}

function generateStory(id, isRecent = true) {
  const reporter = REPORTERS[Math.floor(Math.random() * REPORTERS.length)];
  const category = CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)];
  const headline = HEADLINES[id % HEADLINES.length];
  const bodyText = BODY_TEXTS[id % BODY_TEXTS.length];
  const status = isRecent
    ? ['submitted', 'submitted', 'submitted', 'in_progress', 'flagged'][Math.floor(Math.random() * 5)]
    : STATUSES[Math.floor(Math.random() * STATUSES.length)];
  const submittedAt = isRecent ? randomDate(24) : randomDate(720); // 24h vs 30 days

  return {
    id: `story-${id}`,
    reporterId: reporter.id,
    reporter,
    headline,
    category,
    location: reporter.areaName,
    paragraphs: bodyText.split('\n\n').map((text, i) => ({
      id: `p-${id}-${i}`,
      text,
      mediaPath: null,
      mediaType: null,
      mediaName: null,
    })),
    bodyText,
    status,
    priority: ['normal', 'normal', 'normal', 'urgent', 'breaking'][Math.floor(Math.random() * 5)],
    submittedAt: submittedAt.toISOString(),
    createdAt: new Date(submittedAt.getTime() - 3600000).toISOString(),
    updatedAt: submittedAt.toISOString(),
    wordCount: bodyText.split(/\s+/).length,
    aiAccuracy: (85 + Math.random() * 14).toFixed(1),
    mediaFiles: id % 3 === 0 ? [
      { type: 'photo', url: `https://picsum.photos/seed/${id}/800/600`, name: `scene_${id}.jpg` }
    ] : [],
  };
}

// Generate 24 recent stories (last 24h)
export const recentStories = Array.from({ length: 24 }, (_, i) => generateStory(i, true))
  .sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt));

// Generate 120 older stories
export const olderStories = Array.from({ length: 120 }, (_, i) => generateStory(i + 24, false))
  .sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt));

export const allStories = [...recentStories, ...olderStories];

export const reporters = REPORTERS.map(r => ({
  ...r,
  submissionCount: allStories.filter(s => s.reporterId === r.id).length,
  lastActive: allStories
    .filter(s => s.reporterId === r.id)
    .sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt))[0]?.submittedAt || null,
  approvedCount: allStories.filter(s => s.reporterId === r.id && s.status === 'approved').length,
  publishedCount: allStories.filter(s => s.reporterId === r.id && s.status === 'published').length,
}));

export const dashboardStats = {
  pendingReview: recentStories.filter(s => s.status === 'submitted').length,
  reviewedToday: recentStories.filter(s => ['approved', 'rejected', 'published'].includes(s.status)).length,
  aiAccuracy: (recentStories.reduce((sum, s) => sum + parseFloat(s.aiAccuracy), 0) / recentStories.length).toFixed(1),
  totalPublished: allStories.filter(s => s.status === 'published').length,
};

export const CATEGORY_LIST = CATEGORIES;

export function getStoryById(id) {
  return allStories.find(s => s.id === id) || null;
}

export function getStoriesByReporter(reporterId) {
  return allStories.filter(s => s.reporterId === reporterId);
}

export function getReporterById(id) {
  return reporters.find(r => r.id === id) || null;
}
