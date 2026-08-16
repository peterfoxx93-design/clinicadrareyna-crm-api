# Project Specification: DentalCare CRM - Dra. Reyna Pimental

## 1. Design System: "Clinical Precision"
**Aesthetic:** Clean, professional, trustworthy, medical-focused.
- **Color Palette:**
  - Primary: `#1976d2` (Clinical Blue)
  - Surface: `#f3faff` (Light blue tint)
  - Background: White (`#ffffff`)
  - Semantic: Success (Green), Warning (Amber), Error/Urgent (Red).
- **Typography:** Inter (Sans-serif). High legibility and modern feel.
- **UI Patterns:** Rounded corners (8px), subtle shadows (elevation-1), and generous whitespace.

## 2. Shared Components
- **Navigation (Desktop):** Sidebar with icons and labels + Top NavBar with global search and profile.
- **Navigation (Mobile):** Fixed Bottom NavBar (Home, Visits, Records, Profile) + Contextual Top Bar.
- **Cards:** White containers with subtle borders and status indicators (badges).

## 3. Core Modules & Screen List
The system is divided into an Administrative view (Clinic Management) and a Patient Portal.

### Administrative / Desktop
1. **Dashboard (SCREEN_18):** Overview of daily appointments, revenue charts, and critical inventory alerts.
2. **Calendar (SCREEN_15):** Appointment scheduling, daily/weekly views, and status management.
3. **Patient Records (SCREEN_17):** Comprehensive patient profile, odontogram (tooth map), and clinical history.
4. **Billing (SCREEN_14):** Invoicing, payment tracking, and financial summaries.
5. **Inventory (SCREEN_12):** Stock tracking for clinical supplies with reorder alerts.
6. **Analytics (SCREEN_9):** Deep-dive reporting on clinic growth and operational efficiency.

### Patient Portal / Mobile
1. **Home/Welcome (SCREEN_8):** Next appointment reminder and quick access to records.
2. **Mobile Dashboard (SCREEN_7):** Condensed admin view for mobile users.
3. **Clinical File (SCREEN_6):** Mobile-optimized odontogram and treatment history.
4. **Mobile Billing (SCREEN_5):** Quick view of outstanding balances and recent invoices.
5. **Mobile Calendar (SCREEN_4):** Agenda view with simplified appointment selection.
6. **Mobile Inventory (SCREEN_2):** Warehouse management and supplier contact list.

## 4. Implementation Details
- **Framework:** HTML5 / Tailwind CSS.
- **Layout:** Fully responsive (Desktop 1440px / Mobile 390px).
- **Icons:** Material Symbols / Lucide (Dentistry themed).
- **Visual Logic:** Uses "Clinical Precision" tokens for all spacing and color variables.