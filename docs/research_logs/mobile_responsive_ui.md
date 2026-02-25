# Research: Mobile Responsive UI

## Audit Summary

Audited all 18 source files in `web/src/`. The app uses Vite + React 19 + Tailwind 4 with Framer Motion for animations.

### Current State

| Component | Mobile Ready? | Issues |
|-----------|:---:|---------|
| Login | ✅ | Already `max-w-sm mx-4` |
| Layout (Sidebar) | ❌ | `hidden md:flex` with no hamburger/drawer |
| Layout (Navbar) | ⚠️ | Works but title text too large on mobile |
| Dashboard | ⚠️ | Grid works, but hover-only overlays fail on touch |
| Results (Table) | ❌ | 8-column table unusable on mobile |
| Results (Filters) | ⚠️ | Filter buttons overflow horizontally |
| Results (Status Bar) | ⚠️ | Left offset fixed, but too many elements for mobile |
| VibingPage | ⚠️ | Controls row doesn't stack on small screens |
| VibePlaylistDetail | ❌ | Header flex-row, 3-col stats grid, table |
| JobModal | ✅ | `max-w-lg mx-4` is fine |
| Delete Modal | ✅ | `max-w-md mx-4` is fine |

### Key Decisions

1. **Card layout for tables on mobile** — Instead of making tables scrollable (poor UX), convert to card-based layout below `md` breakpoint
2. **Hamburger drawer** — Standard mobile pattern for sidebar navigation
3. **Touch-friendly overlays** — Dashboard playlist hover-to-reveal buttons need to work on tap too
4. **No framework changes** — Pure CSS/Tailwind responsive utilities, no new dependencies
