# Warehouse Picker V2 Design System

## 1. Visual Theme & Atmosphere

Warehouse Picker V2 is an operational logistics interface for picking, separation, supervision, shortage handling, and warehouse execution. The UI should feel calm, fast, and reliable: more control room than marketing site.

The design language is clean, dense, and task-first. Operators should understand the next action within one glance, especially on mobile devices or scanners. Supervisors need compact tables, filters, counters, and status summaries without visual clutter.

## 2. Color Palette & Roles

- Background: `#f6f7f9` for app surfaces.
- Surface: `#ffffff` for panels and tables.
- Surface muted: `#eef2f6` for grouped controls and inactive regions.
- Text primary: `#111827` for labels, titles, and quantities.
- Text secondary: `#4b5563` for metadata and descriptions.
- Text muted: `#6b7280` for helper text.
- Border: `#d9e0e8` for containers and dividers.
- Primary action: `#0f766e` for proceed/confirm actions.
- Primary hover: `#115e59`.
- Info: `#2563eb` for navigation, links, and neutral highlights.
- Success: `#16a34a` for completed/picked/available.
- Warning: `#d97706` for attention, pending divergence, partial state.
- Danger: `#dc2626` for errors, missing items, destructive actions.
- Purple accent: `#7c3aed` only for special intelligence/automation features.

Use color semantically. Do not use decorative gradients as the main app identity.

## 3. Typography Rules

- Primary font: system UI stack (`Inter` if already available, then `Segoe UI`, `Roboto`, `Arial`, sans-serif).
- Body text: 14-16px.
- Dense table text: 13-14px, but never below 12px.
- Mobile primary action text: 15-17px.
- Screen titles: 20-28px depending on density.
- Quantities, SKUs, barcodes, and item codes may use a monospace font for scanability.
- Use font weight to create hierarchy: 400 body, 500 labels, 600 important values, 700 critical counts.

## 4. Component Styling

Buttons:
- Primary: teal background, white text, 6-8px radius, clear hover/pressed/disabled states.
- Secondary: white or muted surface, visible border, dark text.
- Danger: red only for destructive or blocking actions.
- Icon buttons should use clear icons and tooltips when meaning is not obvious.
- Mobile action buttons should be at least 44px tall.

Cards and panels:
- Use cards for repeated items, summaries, dialogs, and bounded tools.
- Avoid cards inside cards.
- Radius should usually be 6-8px.
- Borders should be subtle but visible.

Tables and lists:
- Support fast scanning with aligned columns, sticky headers where useful, status chips, and compact row actions.
- Empty, loading, error, and filtered-zero states must be explicit.

Dialogs:
- Dialogs should focus on recovery and confirmation.
- Unknown barcode, shortage, divergence, and destructive actions need clear next steps.

## 5. Layout Principles

- First screen should be the working product, not a landing page.
- Prioritize workflow order: identify session, scan/pick, confirm, resolve exception, continue.
- Keep primary action near the operator's thumb on mobile.
- Use constrained content width for forms and full width for operational tables.
- Use spacing in a predictable scale: 4, 8, 12, 16, 24, 32.
- Avoid oversized hero sections in internal tools.

## 6. Depth & Elevation

- Prefer borders and surface contrast over heavy shadows.
- Use shadow only for dialogs, dropdowns, and overlays.
- Status and selected states should be communicated with color, border, and text, not shadow alone.

## 7. Do's and Don'ts

Do:
- Make the next action obvious.
- Show counts, progress, and status persistently during picking.
- Make scan errors recoverable.
- Keep supervisor views dense and sortable/filterable.
- Preserve existing project patterns unless there is a clear reason to improve them.
- Test mobile layouts for text overflow and tap targets.

Don't:
- Build generic SaaS landing pages for operational workflows.
- Hide critical actions behind decorative UI.
- Use color without semantic meaning.
- Use nested cards or visual clutter.
- Make buttons or status chips resize unpredictably.
- Use brand-copy styles from Apple, Linear, Stripe, etc. without adapting to warehouse operations.

## 8. Responsive Behavior

- Mobile: single-column, large actions, barcode/SKU prominence, persistent progress.
- Tablet: two-column layouts are allowed for item details plus action panel.
- Desktop: dense tables, side filters, summary metrics, and keyboard-friendly controls.
- Touch targets should be at least 44px on mobile.
- Text must not overflow buttons, chips, cards, or table cells.

## 9. Agent Prompt Guide

When designing UI for this project:

- "Use the Warehouse Picker V2 DESIGN.md. Build a dense, operational logistics interface with semantic status colors, clear next actions, mobile-safe controls, and no generic marketing layout."
- "For picking screens, prioritize scanability, large confirmation actions, visible progress, and recoverable exception handling."
- "For supervisor screens, prioritize compact data density, filters, status chips, fast comparison, and clear escalation paths."
