# Session 06 — Frontend Polish & UX

## Goal
Complete the frontend: navigation, dashboard, visual design, responsive layout, error handling,
loading states, and an overall polished user experience.

## Prerequisite
Sessions 01–05 completed and merged (all API endpoints exist).

## Scope
- Application shell: sidebar navigation, header with user info + logout button
- Dashboard page: summary cards (linked accounts, scheduled analyses, recent runs)
- Spotify page: account cards with avatar, display name, linked date, disconnect button
- AI Config page: provider-branded cards, masked API key display
- Analysis page: analysis list + detail view with run history timeline
- Schedule page: schedule list with next-run countdown, enable/disable toggle
- Run result page: formatted AI response with metadata (model, tokens, duration)
- Global error boundary and toast notifications
- Responsive layout (mobile-friendly)
- Light/dark mode toggle (Tailwind dark mode)
- Loading skeletons for async data
- Empty states with helpful call-to-action

## Acceptance Criteria
- All pages render correctly at 375 px, 768 px, and 1280 px viewport widths
- No unhandled promise rejections in the browser console
- Navigation between pages works without full page reload
- User can complete the full flow: login → link Spotify → add AI config → create analysis →
  run manually → view result → create schedule → logout
- Vitest component tests for all new components

## Key Files to Create / Modify

```
frontend/src/
  components/AppShell.tsx
  components/Sidebar.tsx
  components/Header.tsx
  components/StatCard.tsx
  components/Toast.tsx
  components/LoadingSkeleton.tsx
  components/EmptyState.tsx
  pages/DashboardPage.tsx
  pages/SpotifyAccountsPage.tsx   (polished)
  pages/AIConfigPage.tsx          (polished)
  pages/AnalysisPage.tsx          (polished)
  pages/SchedulesPage.tsx         (polished)
  pages/RunResultPage.tsx
  hooks/useToast.ts
  App.tsx                         (add routes + AppShell)
```
