// Design tokens – single source of truth
export const colors = {
  navy:    '#102B4E',
  orange:  '#F36B21',
  green:   '#138A4B',
  white:   '#FFFFFF',
  black:   '#08090B',
  grey:    '#F1F2F3',
  greyMid: '#6B7280',
}

export const issueCategories = [
  {
    id: 1,
    icon: '🛣️',
    title: 'Road Damage',
    description: 'Potholes, cracks, broken pavements and damaged road surfaces that endanger commuters.',
    accent: '#F36B21',
    emoji: '⚠️',
  },
  {
    id: 2,
    icon: '🗑️',
    title: 'Garbage Accumulation',
    description: 'Uncollected waste, overflowing bins and illegal dumping affecting public health.',
    accent: '#138A4B',
    emoji: '♻️',
  },
  {
    id: 3,
    icon: '💧',
    title: 'Drainage Overflow',
    description: 'Blocked drains, stagnant water and sewage overflow creating health hazards.',
    accent: '#102B4E',
    emoji: '🌊',
  },
  {
    id: 4,
    icon: '🚿',
    title: 'Water Leakage',
    description: 'Burst pipes, leaking mains and water wastage causing infrastructure damage.',
    accent: '#3B82F6',
    emoji: '💦',
  },
  {
    id: 5,
    icon: '💡',
    title: 'Broken Streetlights',
    description: 'Non-functional street lighting that poses safety risks after dark.',
    accent: '#EAB308',
    emoji: '🌙',
  },
]

export const workflowSteps = [
  { id: 1, number: '01', title: 'Citizen Submission', description: 'Citizen reports a public issue with photos, description and location via website or email.', icon: '📱', color: '#F36B21' },
  { id: 2, number: '02', title: 'AI Evidence Verification', description: 'AI analyzes submitted images and videos to verify the reported problem exists.', icon: '🤖', color: '#102B4E' },
  { id: 3, number: '03', title: 'Duplicate Detection', description: 'System checks for physically similar issues already reported nearby to avoid duplication.', icon: '🔍', color: '#138A4B' },
  { id: 4, number: '04', title: 'Priority Assessment', description: 'AI assigns an intelligent priority score based on severity, recurrence and equity factors.', icon: '📊', color: '#F36B21' },
  { id: 5, number: '05', title: 'Authority Action', description: 'Prioritized complaints are routed to the relevant municipal authority for action.', icon: '🏛️', color: '#102B4E' },
  { id: 6, number: '06', title: 'Resolution Verification', description: 'Before-and-after image comparison verifies that the issue has actually been resolved.', icon: '✅', color: '#138A4B' },
]

export const aiCapabilities = [
  { title: 'Image & Video Analysis', description: 'Deep learning models identify and classify infrastructure damage from uploaded media.', icon: '🎯' },
  { title: 'Physical Issue Identification', description: 'Computer vision extracts real-world problem signatures independent of complaint text.', icon: '🔬' },
  { title: 'Duplicate Detection', description: 'Spatial and semantic algorithms identify complaints about the same physical location.', icon: '🗺️' },
  { title: 'Priority Recommendation', description: 'Multi-factor scoring recommends action order based on severity and community impact.', icon: '⚡' },
  { title: 'Equity-Aware Ward Analysis', description: 'Identifies wards with potentially underrepresented reporting for proactive inspections.', icon: '⚖️' },
  { title: 'Resolution Verification', description: 'Before-and-after comparison confirms genuine resolution rather than administrative closure.', icon: '📸' },
]

