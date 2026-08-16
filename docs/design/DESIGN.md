---
name: Clinical Precision
colors:
  surface: '#f3faff'
  surface-dim: '#c7dde9'
  surface-bright: '#f3faff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e6f6ff'
  surface-container: '#dbf1fe'
  surface-container-high: '#d5ecf8'
  surface-container-highest: '#cfe6f2'
  on-surface: '#071e27'
  on-surface-variant: '#414752'
  inverse-surface: '#1e333c'
  inverse-on-surface: '#dff4ff'
  outline: '#717783'
  outline-variant: '#c1c6d4'
  surface-tint: '#005faf'
  primary: '#005dac'
  on-primary: '#ffffff'
  primary-container: '#1976d2'
  on-primary-container: '#fffdff'
  inverse-primary: '#a5c8ff'
  secondary: '#526069'
  on-secondary: '#ffffff'
  secondary-container: '#d3e2ed'
  on-secondary-container: '#56656e'
  tertiary: '#944700'
  on-tertiary: '#ffffff'
  tertiary-container: '#ba5b00'
  on-tertiary-container: '#fffeff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d4e3ff'
  primary-fixed-dim: '#a5c8ff'
  on-primary-fixed: '#001c3a'
  on-primary-fixed-variant: '#004786'
  secondary-fixed: '#d6e5ef'
  secondary-fixed-dim: '#bac9d3'
  on-secondary-fixed: '#0f1d25'
  on-secondary-fixed-variant: '#3b4951'
  tertiary-fixed: '#ffdbc7'
  tertiary-fixed-dim: '#ffb688'
  on-tertiary-fixed: '#311300'
  on-tertiary-fixed-variant: '#733600'
  background: '#f3faff'
  on-background: '#071e27'
  surface-variant: '#cfe6f2'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-md-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-margin: 24px
  gutter: 16px
---

## Brand & Style

The design system is engineered for a high-end dental clinical environment, balancing medical authority with patient-centric warmth. The brand personality is professional, meticulous, and calming, aimed at reducing the anxiety often associated with dental procedures.

The visual style follows a **Modern Corporate** approach with a strong emphasis on **Minimalism**. It utilizes expansive white space to denote cleanliness and a structured information hierarchy to ensure administrative efficiency. The interface feels lightweight through the use of soft shadows and subtle transitions, avoiding the "heavy" feel of legacy medical software.

## Colors

This color palette is anchored in a professional "Dental Blue" hierarchy. 
- **Primary Blue (#1976D2)**: Used for primary actions, active navigation states, and brand identifiers. It conveys stability and trust.
- **Secondary Blue (#E3F2FD)**: Used for large surface areas, highlights, and component backgrounds to keep the UI light and airy.
- **Success Green (#2E7D32)**: Specifically reserved for confirmed appointments, paid invoices, and positive health outcomes.
- **Error Red (#D32F2F)**: Reserved for overdue payments, cancelled appointments, and medical alerts.
- **Neutrals**: A range of cool grays are used for secondary text and borders to maintain a crisp, sterile (but not cold) aesthetic.

## Typography

The design system utilizes **Inter** across all levels to ensure maximum legibility and a contemporary technical feel. 

Headlines use tighter letter spacing and heavier weights to establish clear section boundaries. Body text prioritizes comfortable line heights (1.5x) for reading patient records and treatment plans. Labels are set in a medium weight with slight tracking for quick identification in dense data environments like tables and charts.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. On desktop, a fixed sidebar navigation (260px) anchors the experience, while the main content area utilizes a fluid grid with a maximum content width of 1440px.

A 4px baseline grid ensures vertical rhythm. Components like patient cards and data tables should use "Loose" padding (typically `lg` or 24px) to maintain a sense of clinical order and prevent information density from becoming overwhelming.

**Breakpoints:**
- Mobile: < 600px (Single column, 16px margins)
- Tablet: 600px - 1024px (Stacked cards, 24px margins)
- Desktop: > 1024px (Sidebar persistent, 12-column grid)

## Elevation & Depth

To maintain a "Friendly Medical" aesthetic, depth is created through **Tonal Layering** supplemented by soft **Ambient Shadows**.

1.  **Level 0 (Background):** `#F8FAFC` - The base clinical floor.
2.  **Level 1 (Cards/Sidebar):** White surface with a very soft, diffused shadow (`0px 4px 12px rgba(0,0,0,0.05)`).
3.  **Level 2 (Modals/Popovers):** White surface with a more defined shadow (`0px 8px 24px rgba(0,0,0,0.10)`) and a 1px border in a light neutral gray.

Avoid heavy black shadows; instead, use slightly tinted shadows (using the primary blue at very low opacity) to keep the interface vibrant.

## Shapes

The design system uses a consistent **Rounded** radius (12px or 0.75rem) for all primary containers, including patient cards, input fields, and action buttons. 

Smaller elements like checkboxes and tags use a 4px radius to maintain precision. This rounded language is crucial to the brand's "Friendly yet Medical" promise, softening the sharp edges of traditional clinical software without appearing juvenile.

## Components

### Sidebar Navigation
The sidebar should use the secondary blue (`#E3F2FD`) as a subtle background tint or a clean white with a persistent right border. Active states are indicated by a primary blue vertical bar on the left and bolded text.

### Metrics Cards
Used for dashboard stats (e.g., "Daily Appointments," "Monthly Revenue"). These should feature a large `headline-md` value, a `label-sm` title, and a small sparkline or icon in the corner.

### Data Tables
Clean, borderless rows with a subtle hover state (`#F1F5F9`). Headers should be `label-sm` with a light gray background tint. Use success/error chips for status columns.

### Buttons
- **Primary:** Solid `#1976D2` with white text. 12px corner radius.
- **Secondary:** Transparent with a 1px border of the primary color or a light blue background.
- **Alert:** Solid `#D32F2F` for destructive actions (e.g., Delete Record).

### Input Fields
Large, accessible touch targets (44px height minimum). Use a 1px border that turns primary blue on focus. Placeholder text should be a light neutral gray.

### Appointment Chips
Used in calendar views. These are color-coded:
- **Green:** Confirmed/Completed
- **Blue:** Scheduled
- **Gray:** Pending/Tentative