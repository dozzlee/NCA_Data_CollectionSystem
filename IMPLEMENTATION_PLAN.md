# NCA Data Collection System — Implementation Plan
**Version:** 1.0 | **Date:** 2026-06-03 | **Status:** Handoff-ready

This document is a self-contained build specification. It is the single source of truth for any developer or AI coding platform (Codex, Cursor, etc.) picking up this project. Read it fully before writing any code.

---

## 1. Project Overview

**What it is:** A secure regulatory data collection and compliance workflow portal for the National Communications Authority (NCA) of Ghana.

**What it replaces:** Email-first data collection from licensed telecom providers.

**Two user types:**
- **NCA Officers** — internal staff who manage periods, review submissions, follow up on compliance, and export data
- **Licensed Providers** — external companies (MNOs, ISPs, Pay-TV, Tower operators, Fibre companies) who fill out and submit structured web forms

**Core workflow:**
```
Period opens → Expected submissions generated → Provider fills form (draft) →
Provider approver submits → NCA reviews → Approve / Request Correction / Reject →
Provider resubmits if corrected → Approved = read-only, eligible for export
```

**MVP scope (build this, nothing else):**
- Manual web-form data entry with draft saving
- Section-by-section grouped form layout matching source forms
- KMZ upload ONLY for fibre forms (DC-DBS05, DC-SUB03)
- Excel backup upload for source control only (never analyzed)
- NCA review workflow with correction targeting specific fields/sections
- Compliance dashboard with status counts and filters
- CSV and PDF export
- Audit trail for all actions
- Email draft generation and storage (no direct Outlook send in MVP)

**Out of scope for MVP:**
Excel import/parsing, CSV import, GIS/map exploration, AI anomaly detection, direct Outlook sync, advanced analytics, custom report builders, document intake (DOCX/PDF/image).

---

## 2. Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| Frontend | Next.js 14 (App Router) | Server components for data-heavy views; RSC eliminates client-side data fetching boilerplate |
| Backend | Django 5 + Django REST Framework | Built-in admin, ORM maps 1:1 to PRD data model, batteries-included auth and RBAC |
| Database | PostgreSQL 16 | Complex relational queries for compliance dashboard; JSONB for form value storage |
| Auth | Django built-in + `djangorestframework-simplejwt` + `django-two-factor-auth` | Fully open source, no vendor lock-in, MFA-ready |
| API shape | REST (DRF) | Simple to build solo; Django admin uses same models |
| Client state | TanStack Query (React Query) | Caching, optimistic updates for form drafts |
| Styling | Tailwind CSS v4 + CSS variables from DESIGN.md | Design tokens already defined; utility classes match 8px grid |
| Deployment | Docker Compose | Single command for IT team; runs on local VM, no cloud required |
| Reverse proxy | Nginx | Serves Next.js static/SSR + proxies `/api/` to Django |
| File storage | Local filesystem (Docker volume) | KMZ and Excel backup files stored on the VM; no S3 dependency |
| Design skills | impeccable + design-taste-frontend + emilkowal-animations | Applied to all frontend work |

---

## 3. Design System

Sourced from `DESIGN.md`. All CSS variables and Tailwind tokens must follow these exactly.

### Colors
```css
:root {
  --primary:              #001836;
  --primary-container:    #002d5b;
  --secondary:            #275fa5;
  --surface:              #f7f9fb;
  --surface-container:    #eceef0;
  --surface-glass:        rgba(255, 255, 255, 0.70);
  --on-surface:           #191c1e;
  --on-surface-variant:   #43474f;
  --outline:              #737780;
  --outline-variant:      #c3c6d0;
  --data-blue:            #0066cc;
  --nca-red:              #e31937;
  --nca-gold:             #ffd100;
  --success:              #1f7a4d;
  --success-soft:         #e5f4eb;
  --warning-soft:         #fff3bf;
  --critical-soft:        #ffe8e8;
  --shadow:               0 16px 42px rgba(0, 45, 91, 0.10);
  --radius-sm:            8px;
  --radius-lg:            16px;
}
```

### Typography (Inter font — load from Google Fonts or bundle locally)
| Token | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| `display-lg` | 48px | 700 | 56px | Hero headings |
| `headline-lg` | 32px | 600 | 40px | Page titles |
| `headline-md` | 24px | 600 | 32px | Section headings |
| `headline-sm` | 20px | 600 | 28px | Card titles |
| `body-lg` | 18px | 400 | 28px | Intro paragraphs |
| `body-md` | 16px | 400 | 24px | Body copy |
| `body-sm` | 14px | 400 | 20px | Secondary text |
| `label-md` | 12px | 600 | 16px | Table headers, chips (+0.05em tracking, uppercase) |
| `data-mono` | 14px | 500 | 20px | Dashboard metrics, numeric table values |

### Elevation Model
- **Base:** `#f7f9fb` background or deep navy sidebar
- **Glass cards:** `backdrop-filter: blur(12px)` + `background: rgba(255,255,255,0.70)` + `border: 1px solid rgba(255,255,255,0.20)`
- **Shadows:** `0 16px 42px rgba(0, 45, 91, 0.10)` — navy-tinted, never black

### Shapes
- Buttons, inputs, small cards: `border-radius: 8px`
- Large dashboard modules, hero sections: `border-radius: 16px`
- Progress bars, status chips: `border-radius: 9999px`

### Animation Principles (emilkowal-animations)
- Transitions: `spring` easing where possible (Framer Motion), fallback `cubic-bezier(0.34, 1.56, 0.64, 1)`
- Duration: 200ms for micro-interactions, 300ms for layout shifts, 500ms for page transitions
- Form section transitions: slide + fade
- Toast notifications: spring from bottom-right
- Modal/drawer: slide up with spring
- Never animate `width`/`height` — animate `transform` and `opacity` only

---

## 4. Project Structure

```
nca-data-collection/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── users/              # User accounts, roles, permissions
│   │   ├── providers/          # ProviderProfile, ProviderContact
│   │   ├── forms_engine/       # FormTemplate, FormSection, FormField, FormGrid
│   │   ├── submissions/        # ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue
│   │   ├── uploads/            # KMZ uploads (fibre only), Excel backup uploads
│   │   ├── compliance/         # EmailTemplate, EmailLog, compliance status logic
│   │   ├── exports/            # CSV and PDF export logic
│   │   └── audit/              # AuditEvent (immutable log)
│   ├── requirements.txt
│   ├── manage.py
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── mfa/
│   │   ├── (nca)/              # NCA Officer portal
│   │   │   ├── dashboard/
│   │   │   ├── submissions/
│   │   │   │   ├── [id]/
│   │   │   │   └── [id]/review/
│   │   │   ├── providers/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   ├── periods/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   ├── forms/          # Form template management
│   │   │   ├── compliance/
│   │   │   ├── exports/
│   │   │   └── layout.tsx      # NCA shell (sidebar + header)
│   │   ├── (provider)/         # Provider portal
│   │   │   ├── dashboard/
│   │   │   ├── submissions/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx         # Form entry
│   │   │   │       └── [section]/
│   │   │   └── layout.tsx      # Provider shell
│   │   ├── layout.tsx          # Root layout (fonts, providers)
│   │   └── globals.css         # CSS variables from design system
│   ├── components/
│   │   ├── ui/                 # Primitives (Button, Input, Badge, Card, etc.)
│   │   ├── charts/             # Dashboard charts (Recharts)
│   │   ├── forms/              # Form engine renderer components
│   │   ├── layout/             # Sidebar, Header, Shell
│   │   └── compliance/         # Status chips, due-state badges
│   ├── lib/
│   │   ├── api.ts              # Fetch wrapper with auth headers
│   │   ├── types.ts            # TypeScript types mirroring Django models
│   │   └── utils.ts
│   ├── hooks/                  # TanStack Query hooks
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml          # Development
├── docker-compose.prod.yml     # VM deployment
├── .env.example
└── IMPLEMENTATION_PLAN.md      # This file
```

---

## 5. Docker Compose Setup

### `docker-compose.yml` (development)
```yaml
version: "3.9"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: nca_dc
      POSTGRES_USER: nca
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
      - media_files:/app/media
    environment:
      - DATABASE_URL=postgresql://nca:${DB_PASSWORD}@db:5432/nca_dc
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=True
      - ALLOWED_HOSTS=localhost,127.0.0.1
    ports:
      - "8000:8000"
    depends_on:
      - db

  frontend:
    build: ./frontend
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
  media_files:
```

### `docker-compose.prod.yml` (VM deployment — IT team runs this)
```yaml
version: "3.9"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: nca_dc
      POSTGRES_USER: nca
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  backend:
    build: ./backend
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - media_files:/app/media
      - static_files:/app/staticfiles
    environment:
      - DATABASE_URL=postgresql://nca:${DB_PASSWORD}@db:5432/nca_dc
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=False
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
    depends_on:
      - db
    restart: always

  frontend:
    build: ./frontend
    command: node server.js
    environment:
      - NEXT_PUBLIC_API_URL=http://nginx
      - NODE_ENV=production
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - static_files:/var/www/static
      - media_files:/var/www/media
    depends_on:
      - backend
      - frontend
    restart: always

volumes:
  postgres_data:
  static_files:
  media_files:
```

### `.env.example`
```
DB_PASSWORD=changeme
SECRET_KEY=changeme-generate-with-python-secrets
ALLOWED_HOSTS=localhost,192.168.1.100
SUPPORT_EMAIL=support@nca.org.gh
FEEDBACK_EMAIL=feedback@nca.org.gh
```

---

## 6. Backend — Django Models

Every model maps directly from the PRD Section 9.1. Build in this order.

### `apps/users/models.py`
```python
class Organization(models.Model):
    name = models.CharField(max_length=255)
    org_type = models.CharField(choices=[('NCA','NCA'),('PROVIDER','Provider')])

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    role = models.CharField(choices=[
        ('NCA_ADMIN','NCA Admin'),
        ('NCA_OFFICER','NCA Officer'),
        ('PROVIDER_ADMIN','Provider Admin'),
        ('PROVIDER_DATA_ENTRY','Provider Data Entry'),
        ('PROVIDER_APPROVER','Provider Approver'),
    ])
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True)
    mfa_enabled = models.BooleanField(default=False)
```

### `apps/providers/models.py`
```python
class ProviderProfile(models.Model):
    provider_id = models.UUIDField(default=uuid.uuid4, unique=True)
    registered_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(choices=[
        ('MNO','MNO'), ('ISP','ISP'), ('PAY_TV','Pay TV'),
        ('TOWER_OPERATOR','Tower Operator'), ('TOWER_MAIN','Tower Main'),
        ('DOMESTIC_FIBRE','Domestic Fibre'), ('SUBMARINE_FIBRE','Submarine Fibre'),
    ])
    licence_type = models.CharField(max_length=100)
    licence_number = models.CharField(max_length=100)
    licence_issue_date = models.DateField(null=True)
    licence_expiry_date = models.DateField(null=True)
    physical_address = models.TextField(blank=True)
    digital_address = models.CharField(max_length=20, blank=True)
    postal_address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    primary_email = models.EmailField()
    primary_phone = models.CharField(max_length=30)
    status = models.CharField(choices=[
        ('ACTIVE','Active'),('INACTIVE','Inactive'),
        ('SUSPENDED','Suspended'),('ARCHIVED','Archived')
    ], default='ACTIVE')

class ProviderContact(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    notification_role = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    notify_on_period_open = models.BooleanField(default=True)
    notify_on_reminder = models.BooleanField(default=True)
    notify_on_review = models.BooleanField(default=True)
```

### `apps/forms_engine/models.py`
```python
FIELD_TYPES = [
    ('text','Text'), ('number','Number'), ('currency','Currency'),
    ('percentage','Percentage'), ('date','Date'), ('boolean','Boolean'),
    ('select','Select'), ('multiselect','Multi-select'),
    ('textarea','Textarea'), ('coordinate','Coordinate'),
    ('formula','Formula'), ('declaration','Declaration'),
]

class FormTemplate(models.Model):
    form_code = models.CharField(max_length=20, unique=True)
    # Codes: MNO-MONTHLY, DC-ISP06, DC-ITC04, TOWER-MAIN-ANNUAL,
    #        DC-DBS05, DC-SUB03, DC-TB02
    name = models.CharField(max_length=255)
    provider_category = models.CharField(max_length=50)
    frequency = models.CharField(choices=[('MONTHLY','Monthly'),('SEMI_ANNUAL','Semi-Annual'),('ANNUAL','Annual')])
    version = models.CharField(max_length=20)
    effective_from = models.DateField()
    status = models.CharField(choices=[('DRAFT','Draft'),('ACTIVE','Active'),('ARCHIVED','Archived')])
    kmz_required = models.BooleanField(default=False)
    # True ONLY for DC-DBS05 and DC-SUB03

class FormSection(models.Model):
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='sections')
    section_code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField()
    kmz_upload_required = models.BooleanField(default=False)
    # True only for backbone-topology section in DC-DBS05

class FormField(models.Model):
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name='fields')
    field_code = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(choices=FIELD_TYPES)
    unit = models.CharField(max_length=50, blank=True)   # GH₵, Gbps, km, %, etc.
    is_required = models.BooleanField(default=True)
    help_text = models.TextField(blank=True)
    formula = models.TextField(blank=True)               # For calculated fields
    conditional_on_field = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    conditional_on_value = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveIntegerField()
    export_name = models.CharField(max_length=100, blank=True)

class FormGrid(models.Model):
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name='grids')
    grid_code = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    row_mode = models.CharField(choices=[('FIXED','Fixed'),('REPEATABLE','Repeatable')])
    sort_order = models.PositiveIntegerField()

class GridColumn(models.Model):
    grid = models.ForeignKey(FormGrid, on_delete=models.CASCADE, related_name='columns')
    column_code = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(choices=FIELD_TYPES)
    unit = models.CharField(max_length=50, blank=True)
    is_required = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField()

class GridRow(models.Model):
    # For FIXED grids (e.g. Ghana regions), pre-populate row labels
    grid = models.ForeignKey(FormGrid, on_delete=models.CASCADE, related_name='fixed_rows')
    row_label = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField()

# Ghana regions (16) — used as fixed row labels across regional grids:
# Ahafo, Ashanti, Bono, Bono East, Central, Eastern, Greater Accra,
# North East, Northern, Oti, Savannah, Upper East, Upper West,
# Volta, Western, Western North

class SelectOption(models.Model):
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField()

class KMZUploadRequirement(models.Model):
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE)
    section = models.ForeignKey(FormSection, null=True, on_delete=models.SET_NULL)
    category = models.CharField(choices=[
        ('ROUTE','Route'), ('TOPOLOGY','Topology'),
        ('COVERAGE','Coverage'), ('NETWORK_MAP','Network Map'),
    ])
    is_required = models.BooleanField(default=True)
    max_file_size_mb = models.PositiveIntegerField(default=50)
    description = models.TextField(blank=True)
    # Only exists for DC-DBS05 and DC-SUB03
```

### `apps/submissions/models.py`
```python
WORKFLOW_STATUSES = [
    ('NOT_STARTED','Not Started'), ('DRAFT','Draft'),
    ('PENDING_APPROVAL','Pending Provider Approval'),
    ('SUBMITTED','Submitted'), ('UNDER_REVIEW','Under NCA Review'),
    ('CORRECTION_REQUESTED','Correction Requested'),
    ('RESUBMITTED','Resubmitted'), ('APPROVED','Approved'),
    ('REJECTED','Rejected'), ('ARCHIVED','Archived'),
]

DUE_STATES = [
    ('NOT_OPEN','Not Open'), ('OPEN','Open'), ('DUE_SOON','Due Soon'),
    ('DUE_TODAY','Due Today'), ('OVERDUE','Overdue'), ('CLOSED','Closed'),
]

FIELD_STATUSES = [
    ('MISSING','Missing'), ('PROVIDED','Provided'),
    ('OPTIONAL_NOT_PROVIDED','Optional Not Provided'),
    ('NOT_APPLICABLE','Not Applicable'), ('NOT_AVAILABLE','Not Available'),
    ('NOT_REQUIRED','Not Required for Provider'),
    ('PENDING_CLARIFICATION','Pending Clarification'),
    ('WAITING_CORRECTION','Waiting for Correction'),
    ('SYSTEM_CALCULATED','System Calculated'),
]

class ReportingPeriod(models.Model):
    name = models.CharField(max_length=255)
    frequency = models.CharField(choices=[('MONTHLY','Monthly'),('SEMI_ANNUAL','Semi-Annual'),('ANNUAL','Annual')])
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(null=True, blank=True)  # Only for monthly
    opens_at = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(choices=[('DRAFT','Draft'),('ACTIVE','Active'),('CLOSED','Closed')])
    applicable_form_templates = models.ManyToManyField('forms_engine.FormTemplate')
    assigned_providers = models.ManyToManyField('providers.ProviderProfile')

class ExpectedSubmission(models.Model):
    provider = models.ForeignKey('providers.ProviderProfile', on_delete=models.PROTECT)
    form_template = models.ForeignKey('forms_engine.FormTemplate', on_delete=models.PROTECT)
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT)
    workflow_status = models.CharField(choices=WORKFLOW_STATUSES, default='NOT_STARTED')
    due_state = models.CharField(choices=DUE_STATES, default='NOT_OPEN')
    # due_state is COMPUTED — never set manually
    assigned_officer = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL)
    due_at_override = models.DateTimeField(null=True, blank=True)

class Submission(models.Model):
    expected = models.ForeignKey(ExpectedSubmission, on_delete=models.PROTECT, related_name='versions')
    version = models.PositiveIntegerField(default=1)
    completion_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    submitted_by = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL, related_name='submitted')
    submitted_at = models.DateTimeField(null=True)
    reviewed_by = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL, related_name='reviewed')
    reviewed_at = models.DateTimeField(null=True)

class SubmissionValue(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='values')
    field = models.ForeignKey('forms_engine.FormField', null=True, on_delete=models.SET_NULL)
    grid = models.ForeignKey('forms_engine.FormGrid', null=True, blank=True, on_delete=models.SET_NULL)
    grid_row_id = models.CharField(max_length=100, blank=True)   # Fixed row label or repeatable row UUID
    grid_column = models.ForeignKey('forms_engine.GridColumn', null=True, blank=True, on_delete=models.SET_NULL)
    value = models.TextField(blank=True)
    value_status = models.CharField(choices=FIELD_STATUSES, default='MISSING')
    explanation = models.TextField(blank=True)  # For non-filled statuses
    updated_by = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

class ReviewAction(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='review_actions')
    action = models.CharField(choices=[
        ('APPROVE','Approve'), ('REJECT','Reject'),
        ('REQUEST_CORRECTION','Request Correction'),
        ('ADD_NOTE','Add Internal Note'),
        ('ADD_PROVIDER_COMMENT','Add Provider Comment'),
    ])
    target_type = models.CharField(choices=[
        ('SUBMISSION','Submission'), ('SECTION','Section'),
        ('FIELD','Field'), ('GRID_CELL','Grid Cell'),
    ], blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    created_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
```

### `apps/uploads/models.py`
```python
class SubmissionKMZUpload(models.Model):
    # KMZ upload — ONLY for DC-DBS05 (Domestic Fibre) and DC-SUB03 (Submarine Fibre)
    submission = models.ForeignKey('submissions.Submission', on_delete=models.CASCADE)
    requirement = models.ForeignKey('forms_engine.KMZUploadRequirement', on_delete=models.PROTECT)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(choices=[
        ('PENDING','Pending'),('ACCEPTED','Accepted'),('REJECTED','Rejected')
    ], default='PENDING')
    review_note = models.TextField(blank=True)

class SubmissionExcelBackup(models.Model):
    # Excel backup — source control only, never analyzed
    submission = models.ForeignKey('submissions.Submission', on_delete=models.CASCADE)
    section = models.ForeignKey('forms_engine.FormSection', null=True, on_delete=models.SET_NULL)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_control_status = models.CharField(
        choices=[('STORED','Stored'),('SUPERSEDED','Superseded')],
        default='STORED'
    )
    # NOTE: This file is NEVER parsed, imported, or used for calculations
```

### `apps/compliance/models.py`
```python
class EmailTemplate(models.Model):
    template_type = models.CharField(choices=[
        ('PERIOD_OPEN','Period Opening Notice'),
        ('REMINDER','Submission Reminder'),
        ('DRAFT_INCOMPLETE','Draft Incomplete Reminder'),
        ('MISSING_FIELDS','Missing Required Fields'),
        ('CORRECTION_REQUEST','Correction Request'),
        ('OVERDUE','Overdue Notice'),
        ('ESCALATION','Escalation Notice'),
        ('PENALTY_WARNING','Penalty Warning'),
        ('FINAL_NOTICE','Final Compliance Notice'),
    ])
    subject = models.CharField(max_length=500)
    body = models.TextField()
    placeholders = models.JSONField(default=list)

class EmailLog(models.Model):
    template = models.ForeignKey(EmailTemplate, null=True, on_delete=models.SET_NULL)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    recipients = models.JSONField()       # [{"email": "...", "name": "..."}]
    cc = models.JSONField(default=list)
    provider = models.ForeignKey('providers.ProviderProfile', null=True, on_delete=models.SET_NULL)
    expected_submission = models.ForeignKey('submissions.ExpectedSubmission', null=True, on_delete=models.SET_NULL)
    period = models.ForeignKey('submissions.ReportingPeriod', null=True, on_delete=models.SET_NULL)
    generated_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    generated_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL, related_name='sent_emails')
    sent_at = models.DateTimeField(null=True)
    compliance_stage = models.CharField(max_length=100, blank=True)
    status = models.CharField(choices=[('DRAFT','Draft'),('SENT','Sent'),('FAILED','Failed')], default='DRAFT')
```

### `apps/audit/models.py`
```python
class AuditEvent(models.Model):
    # Immutable. Never update or delete rows from this table.
    user = models.ForeignKey('users.User', null=True, on_delete=models.SET_NULL)
    user_email = models.EmailField()          # Denormalized — preserved if user deleted
    role = models.CharField(max_length=50)
    organization = models.CharField(max_length=255)
    action = models.CharField(max_length=100)  # e.g. SUBMISSION_CREATED, FIELD_UPDATED
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    before_value = models.JSONField(null=True)
    after_value = models.JSONField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
```

---

## 7. API Endpoints

All endpoints prefixed with `/api/v1/`. Authentication via JWT (`Authorization: Bearer <token>`).

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/login/` | Email + password → access + refresh tokens |
| POST | `/auth/refresh/` | Refresh token → new access token |
| POST | `/auth/logout/` | Invalidate refresh token |
| POST | `/auth/mfa/verify/` | Verify TOTP code |
| GET | `/auth/me/` | Current user profile + permissions |

### NCA Dashboard
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/summary/` | Counts: expected, not started, draft, submitted, overdue, approved, etc. |
| GET | `/dashboard/charts/status-donut/` | Submission status breakdown |
| GET | `/dashboard/charts/category-completion/` | Completion % by provider category |
| GET | `/dashboard/charts/submission-trend/` | Submissions over time |
| GET | `/dashboard/charts/overdue-by-form/` | Overdue count per form type |

### Providers
| Method | Path | Description |
|---|---|---|
| GET | `/providers/` | List providers (filterable) |
| POST | `/providers/` | Create provider |
| GET | `/providers/{id}/` | Provider detail |
| PATCH | `/providers/{id}/` | Update provider |
| GET | `/providers/{id}/contacts/` | List contacts |
| POST | `/providers/{id}/contacts/` | Add contact |
| PATCH | `/providers/{id}/contacts/{cid}/` | Update contact |

### Form Templates
| Method | Path | Description |
|---|---|---|
| GET | `/form-templates/` | List templates |
| POST | `/form-templates/` | Create template (admin only) |
| GET | `/form-templates/{id}/` | Template detail with sections/fields/grids |
| POST | `/form-templates/{id}/sections/` | Add section |
| POST | `/form-templates/{id}/sections/{sid}/fields/` | Add field |
| POST | `/form-templates/{id}/sections/{sid}/grids/` | Add grid |

### Reporting Periods
| Method | Path | Description |
|---|---|---|
| GET | `/periods/` | List periods |
| POST | `/periods/` | Create period |
| GET | `/periods/{id}/` | Period detail |
| PATCH | `/periods/{id}/` | Update period |
| POST | `/periods/{id}/activate/` | Activate period (generates expected submissions) |
| GET | `/periods/{id}/expected-submissions/` | All expected submissions for period |

### Expected Submissions
| Method | Path | Description |
|---|---|---|
| GET | `/expected-submissions/` | List (filterable by period, provider, status, due-state) |
| GET | `/expected-submissions/{id}/` | Detail with current submission |
| PATCH | `/expected-submissions/{id}/assign/` | Assign NCA officer |
| PATCH | `/expected-submissions/{id}/override-due-date/` | Override due date (audited) |

### Submissions (Form Entry)
| Method | Path | Description |
|---|---|---|
| POST | `/expected-submissions/{id}/start/` | Create first submission version (status → DRAFT) |
| GET | `/submissions/{id}/` | Full submission with values |
| GET | `/submissions/{id}/sections/{section_code}/` | Single section with field values |
| PUT | `/submissions/{id}/sections/{section_code}/values/` | Save section values (draft) |
| POST | `/submissions/{id}/submit-for-approval/` | Provider submits to approver |
| POST | `/submissions/{id}/approve-and-submit/` | Approver officially submits to NCA |
| POST | `/submissions/{id}/return-to-draft/` | Approver returns to data entry |
| GET | `/submissions/{id}/completion/` | Completion percentage + missing fields |

### NCA Review
| Method | Path | Description |
|---|---|---|
| POST | `/submissions/{id}/review/approve/` | Approve submission |
| POST | `/submissions/{id}/review/reject/` | Reject submission |
| POST | `/submissions/{id}/review/request-correction/` | Flag specific fields/sections |
| POST | `/submissions/{id}/review/add-note/` | Internal NCA note |
| POST | `/submissions/{id}/review/add-comment/` | Provider-visible comment |
| GET | `/submissions/{id}/history/` | All versions + review actions |

### KMZ Uploads (fibre forms only)
| Method | Path | Description |
|---|---|---|
| POST | `/submissions/{id}/kmz-uploads/` | Upload KMZ file |
| GET | `/submissions/{id}/kmz-uploads/` | List uploads for submission |
| PATCH | `/submissions/{id}/kmz-uploads/{uid}/review/` | NCA accept/reject upload |
| GET | `/submissions/{id}/kmz-uploads/{uid}/download/` | Download file |

### Excel Backup Uploads
| Method | Path | Description |
|---|---|---|
| POST | `/submissions/{id}/excel-backups/` | Upload Excel backup (source control only) |
| GET | `/submissions/{id}/excel-backups/` | List backups |

### Compliance & Email
| Method | Path | Description |
|---|---|---|
| GET | `/compliance/` | Compliance dashboard — overdue, reminders needed |
| POST | `/compliance/generate-email/` | Generate email draft from template |
| GET | `/compliance/emails/` | Email log |
| PATCH | `/compliance/emails/{id}/mark-sent/` | Mark email as sent |

### Exports
| Method | Path | Description |
|---|---|---|
| POST | `/exports/csv/` | Generate CSV export (long/narrow format) |
| POST | `/exports/pdf/` | Generate PDF export |
| GET | `/exports/` | Export log |

### Feedback & System Issues
| Method | Path | Description |
|---|---|---|
| POST | `/feedback/` | Submit feedback |
| POST | `/issues/` | Report system issue |

---

## 8. Frontend Pages & Components

### Build order (strict — do not skip ahead)

**Phase 1: Foundation**
1. Project setup (Next.js, Tailwind, design tokens, Inter font)
2. `globals.css` with all CSS variables from DESIGN.md
3. Tailwind config mapping design tokens
4. `lib/api.ts` — fetch wrapper with JWT header injection
5. `lib/types.ts` — TypeScript interfaces for all API responses
6. UI primitives: Button, Input, Select, Textarea, Badge, Card, Spinner, Toast

**Phase 2: NCA Officer Shell + Dashboard** ← start here
7. NCA layout: sidebar (deep navy, sticky) + top header
8. Sidebar nav items: Dashboard, Submissions, Providers, Periods, Compliance, Exports
9. Dashboard page: summary stat cards + 4 charts
10. Submission list page with filters

**Phase 3: Provider Entry Shell**
11. Provider layout (lighter shell, provider-branded header)
12. Provider dashboard: my submissions, status, upcoming due
13. Form entry shell: section stepper sidebar + main content area
14. Field renderer: scalar fields, grids (fixed + repeatable), declaration fields
15. Draft save + progress indicator
16. KMZ upload panel (rendered ONLY for DC-DBS05 and DC-SUB03)

**Phase 4: NCA Review**
17. Submission review page: field-by-field with statuses
18. Correction request flow: select sections/fields to flag
19. Review action history timeline

**Phase 5: Compliance + Exports**
20. Compliance dashboard
21. Email draft generation UI
22. Export page (CSV/PDF with filters)

**Phase 6: Auth**
23. Login page
24. MFA verification page
25. Session timeout handling

---

## 9. NCA Dashboard — Component Breakdown

### Stat Cards (build first)
4 cards across the top:

| Card | Value | Color accent |
|---|---|---|
| Expected Submissions | Total count | Data blue |
| Submitted | Count | Success green |
| Overdue | Count | NCA red |
| Approved | Count | Success green |

Each card: glass morphic (`backdrop-filter: blur(12px)`, white/70 background, 1px border), `headline-md` number, `label-md` label.

### Charts (Recharts library)
- **Status donut:** `PieChart` — slice per workflow status, legend below
- **Completion by category:** `BarChart` horizontal — one bar per provider category
- **Submission trend:** `LineChart` — submissions over last 12 months, 2px stroke
- **Overdue by form type:** `BarChart` vertical — one bar per form code

Chart colors: data-blue primary, nca-red for overdue/negative, nca-gold for warning.

### Filters
- Reporting period (select)
- Provider category (multi-select)
- Form type (multi-select)
- Workflow status (multi-select)
- Due state (multi-select)
- Assigned officer (select)
- Date range

---

## 10. Form Engine — Renderer Architecture

The form engine renders any `FormTemplate` dynamically. Never hard-code form-specific UI.

```
FormRenderer
├── SectionStepper (left sidebar — shows sections, completion per section)
└── SectionContent
    ├── SectionHeader (title, instructions)
    ├── FieldRenderer (maps field_type → input component)
    │   ├── ScalarField (text, number, currency, percentage, date, boolean, select, textarea)
    │   ├── FormulaField (computed, read-only, shows formula source)
    │   ├── ConditionalField (renders only when condition met)
    │   └── DeclarationField (checkbox + signature block)
    ├── GridRenderer
    │   ├── FixedGrid (pre-populated rows — e.g. Ghana 16 regions)
    │   └── RepeatableGrid (add/remove rows — e.g. upstream providers)
    ├── KMZUploadPanel (renders ONLY if section.kmz_upload_required AND form is DC-DBS05 or DC-SUB03)
    └── ExcelBackupPanel (renders if form template allows Excel backup)
```

**Field status selector:** Every required field has a dropdown to set status to Not Applicable / Not Available / Not Required / Pending Clarification. This unblocks submission without leaving fields blank.

---

## 11. Form Inventory

| Form Code | Name | Frequency | Provider Category | KMZ | Sections |
|---|---|---|---|---|---|
| MNO-MONTHLY | MNO Monthly Return | Monthly | MNO | No | Industry Subscriptions; Handset & Device; Market Dynamics; Network QoS; SMS Traffic; Pricing & ARPU; Domestic & Roaming Traffic; International Traffic; West Africa Traffic; Top Bilateral Corridors; OTT & Data Apps; Mobile Money |
| DC-TB02 | Pay TV Broadcasting | Annual | Pay TV | No | Company Details; Broadcasting Service Type; Encryption & Streaming; Affiliations; Employment; Financials; Services & Cost; Regional Dealer Counts; Channel Counts by Bouquet; Satellite Services; Checklist; Declaration |
| DC-ISP06 | Internet Service Provider | Annual | ISP | No | Company Details; Employment; Financials; Upstream Transit; IRU Contracts; Local Internet/GIX; Bandwidth Deployment; Subscriber Base; Fixed Broadband; Retail Services; Installation Fees; PoPs; Backhaul; Tower Distribution; VSAT Hub; Tariffs; Comments |
| DC-ITC04 | Infrastructure Tower Operator | Annual | Tower Operator | No | Company Details; Employment; Financials; Site Maintenance; On/Off-Grid Sites; Off-Grid Power Mode; Regional Tower Distribution (Owned); Regional Tower Distribution (Managed); Tenant Groups; Permits; Added Towers; Decommissioned Towers; Acquisitions; Declaration |
| TOWER-MAIN-ANNUAL | Infrastructure Tower Main | Annual | Tower Main | No | Owned Sites; Owned Average Rent; Managed Sites; Managed Average Rent; Decommissioned Towers |
| DC-DBS05 | Domestic/Inland Fibre | Semi-Annual | Domestic Fibre | **YES** | Company Details; Employment; Financials; Capacity; Fibre Lengths; Leased Cables; Microwave Capacity; Backbone Topology (KMZ); Last-Mile Deployment; FTTH Regional Distribution; Regional Fibre Network; Regional Fibre Cuts; Cut Causes; Coverage; Declaration |
| DC-SUB03 | International Submarine Fibre | Annual | Submarine Fibre | **YES** | Company Details; Employment; Financials; Circuit Costs; Cable Metadata; Total/Ghana Capacity; Client Categories; Fibre Cuts; Completion Checklist; Comments; Declaration |

**KMZ restriction:** KMZ upload UI, `KMZUploadRequirement` records, and `SubmissionKMZUpload` API endpoints are ONLY applicable to `DC-DBS05` and `DC-SUB03`. All other forms must not show or accept KMZ files.

---

## 12. Workflow Status & Due-State Logic

These are computed server-side. The frontend displays them but never computes them.

```python
# Due state computation (run on period activation and on a scheduled job)
def compute_due_state(expected_submission):
    if period.status == 'CLOSED' or workflow_status == 'APPROVED':
        return 'CLOSED'
    if period.opens_at > now:
        return 'NOT_OPEN'
    due = expected_submission.due_at_override or period.due_at
    days_until = (due - now).days
    if expected_submission.workflow_status in ['SUBMITTED','UNDER_REVIEW','RESUBMITTED','APPROVED']:
        return 'CLOSED'
    if now > due:
        return 'OVERDUE'
    if days_until <= 7:
        return 'DUE_SOON'
    if days_until == 0:
        return 'DUE_TODAY'
    return 'OPEN'
```

---

## 13. CSV Export Shape

Long/narrow format — one row per field value.

| Column Group | Columns |
|---|---|
| Provider | provider_id, registered_company_name, trade_name, provider_category, licence_type |
| Form & Period | form_code, form_name, form_version, reporting_frequency, reporting_year, reporting_month, period_name, due_date |
| Submission | expected_submission_id, submission_id, submission_version, workflow_status, due_state, submitted_by, submitted_at, reviewed_by, reviewed_at |
| Field | section_code, section_name, field_code, field_name, field_type, unit, grid_name, grid_row_label, grid_column_name |
| Value | submitted_value, value_status, not_applicable_reason, explanation, validation_status, review_status |
| Compliance | last_reminder_sent_at, reminder_count, compliance_stage, missing_field_count |
| Audit | export_generated_by, export_generated_at |

---

## 14. Ghana Regions (Fixed Grid Rows)

These 16 regions are used as pre-populated row labels in all regional grid sections:

```
Ahafo, Ashanti, Bono, Bono East, Central, Eastern, Greater Accra,
North East, Northern, Oti, Savannah, Upper East, Upper West,
Volta, Western, Western North
```

Store as a Django fixture and seed on `manage.py migrate`. Never hard-code in frontend.

---

## 15. Validation Rules

| Type | Behaviour |
|---|---|
| Data type | Reject incompatible values client-side and server-side before submission |
| Required | Block final submission unless field is provided OR has an allowed non-filled status + reason |
| Conditional required | Field becomes required if parent field matches a specific value |
| Calculated totals | Display computed value; store on submission |
| Cross-field | Warn (soft) or block (hard) when totals are inconsistent — NCA override audited |
| Regional grids | Must use the 16-region list, row labels must not be editable |
| Coordinates | Validate lat/lng numeric range; preserve decimal precision |
| Period accuracy | Monthly forms bind to a single month; annual to a single year |
| Non-filled | Blank is not acceptable — every empty required field needs an explicit status |
| KMZ format | Server validates `.kmz` file extension and MIME type; max size per `KMZUploadRequirement.max_file_size_mb` |
| Excel backup | Accept `.xlsx`/`.xls` only; store as-is; never parse or analyze |

---

## 16. Security Requirements

- JWT access tokens: 15-minute expiry; refresh tokens: 7 days
- Session invalidation on logout (blacklist refresh token)
- Account lockout after 5 failed login attempts (configurable)
- MFA: TOTP via `django-two-factor-auth` (enable per policy without blocking launch)
- All file uploads: validate extension + MIME type server-side; store outside web root
- RBAC enforced at API level — provider users cannot access NCA endpoints and vice versa
- All export actions are permission-scoped and create an `ExportLog` record
- AuditEvent table is append-only — no update/delete via ORM
- Passwords hashed with Argon2 (`django[argon2]`)
- HTTPS enforced in production (Nginx terminates TLS)

---

## 17. Build Phases — Status as of 2026-06-03

Repo: **https://github.com/dozzlee/NCA_Data_CollectionSystem** (branch: `main`)
Last commit: `3871a81` — Phase 5: Review, compliance, exports, auth

---

### ✅ Phase 0 — Project scaffold — COMPLETE
- [x] Repo created, directory structure in place
- [x] `docker-compose.yml` — PostgreSQL + Django + Next.js + Nginx
- [x] `docker-compose.prod.yml` — production VM deployment (single `docker-compose up`)
- [x] `.env.example` with all required variables
- [x] `nginx/nginx.conf` — routes `/api/` → Django, `/` → Next.js, `/media/` served directly
- [x] `PRODUCT.md` written for impeccable design skill

---

### ✅ Phase 1 — Backend core — COMPLETE
- [x] All 8 Django apps: `users`, `providers`, `forms_engine`, `submissions`, `uploads`, `compliance`, `exports`, `audit`
- [x] All models matching PRD Section 9.1 (see Section 6 of this document)
- [x] KMZ restriction enforced at model level — `kmz_required` only writable for `DC-DBS05`/`DC-SUB03`
- [x] Django Admin configured for all models with period activation action
- [x] JWT auth — login, logout, refresh, `/me/` (djangorestframework-simplejwt)
- [x] AuditEvent model enforces append-only (raises on `.save()` with existing pk)
- [x] Ghana 16 regions fixture: `backend/fixtures/ghana_regions.json`
- [x] Email template fixtures (4 templates): `backend/fixtures/email_templates.json`
- [x] `requirements.txt` with all dependencies pinned

**Not yet done in Phase 1:**
- [ ] `makemigrations` + `migrate` must be run after cloning (no migrations committed — generate fresh)
- [ ] Providers CRUD API (`apps/providers/views.py` is a stub — serializers and views need writing)
- [ ] User management API beyond login/me (list, create via admin works; REST endpoints are stub)
- [ ] `django-filter` fully wired — `filterset_fields` declared but `django-filter` backend needs verifying end-to-end

---

### ✅ Phase 2 — Dashboard API — COMPLETE
- [x] `GET /api/v1/dashboard/summary/` — all 12 counts + completion %
- [x] `GET /api/v1/dashboard/charts/status-donut/`
- [x] `GET /api/v1/dashboard/charts/category-completion/`
- [x] `GET /api/v1/dashboard/charts/submission-trend/`
- [x] `GET /api/v1/dashboard/charts/overdue-by-form/`
- [x] `GET /api/v1/expected-submissions/` with filterset_fields + search

---

### ✅ Phase 3 — NCA Officer Frontend Dashboard — COMPLETE
- [x] `frontend/app/globals.css` — all CSS variables from `DESIGN.md`
- [x] `frontend/tailwind.config.ts` — full design token mapping
- [x] `lib/api.ts` — JWT fetch wrapper with auto-refresh on 401
- [x] `lib/types.ts` — TypeScript interfaces for all entities
- [x] `lib/utils.ts` — label maps, color helpers, formatters, chart color palette
- [x] `components/ui/Badge.tsx` — WorkflowBadge, DueStateBadge, generic Badge variants
- [x] `components/ui/Skeleton.tsx` — pulse loading placeholder
- [x] `components/layout/Sidebar.tsx` — deep navy, sticky, NCA brand, active states
- [x] `components/layout/TopBar.tsx` — search, period indicator, notifications
- [x] `app/(nca)/layout.tsx` — NCA shell (sidebar + topbar)
- [x] `app/(nca)/dashboard/page.tsx` — 4 stat cards + 4 Recharts charts + filterable submission table with skeletons
- [x] `app/(nca)/submissions/page.tsx` — full submissions list with search, status, category filters
- [x] `hooks/useDashboard.ts` — TanStack Query hooks for all dashboard endpoints

---

### ✅ Phase 4 — Provider Form Entry + Form Engine — COMPLETE
- [x] `apps/forms_engine/serializers.py` — nested detail: template → sections → fields/grids/options
- [x] `apps/forms_engine/views.py` — FormTemplateListView, FormTemplateDetailView, KMZRequirementListView
- [x] `apps/submissions/views.py` — StartSubmission, SectionValues (GET/PUT), SubmissionCompletion, SubmitForApproval, OfficialSubmit
- [x] `apps/uploads/views.py` — KMZUploadView (enforces fibre-only), ExcelBackupUploadView (MIME validation, source-control-only note)
- [x] `components/forms/FieldRenderer.tsx` — all 12 field types + non-filled status selector + explanation field
- [x] `components/forms/GridRenderer.tsx` — fixed rows (Ghana regions) + repeatable rows (add/remove)
- [x] `components/forms/KMZUploadPanel.tsx` — drag-and-drop, `.kmz` validation, 50MB limit, review status display
- [x] `components/forms/SectionStepper.tsx` — progress bar, per-section completion count, active/complete/partial states
- [x] `app/(provider)/layout.tsx` + `components/layout/ProviderTopBar.tsx` — provider shell
- [x] `app/(provider)/submissions/[id]/page.tsx` — full form entry: start flow, section nav, draft save with dirty-state warning, submit for approval
- [x] `hooks/useFormEntry.ts` — TanStack Query hooks for all form entry endpoints

**Not yet done in Phase 4:**
- [ ] `app/(provider)/dashboard/page.tsx` — provider's own submission list with status and upcoming due dates
- [ ] Conditional field rendering in `FieldRenderer` — field only shows when `conditional_on_field` value matches
- [ ] `ExcelBackupPanel` component — UI to upload Excel backup files from provider form entry
- [ ] Form entry: block official submission when required KMZ uploads are missing (enforce client-side gate matching server-side rule)

---

### ✅ Phase 5 — Review, Compliance, Exports, Auth — COMPLETE
- [x] Review API: approve, reject, request-correction (field-level targeting + WAITING_CORRECTION status), add-note, history
- [x] Compliance API: summary counts, email template list, bulk draft generation with placeholder substitution, mark-sent
- [x] Exports API: CSV long/narrow format, ExportLog, AuditEvent on every export
- [x] `app/(nca)/submissions/[id]/review/page.tsx` — section completion panel, 4-action review panel, comment input, history timeline
- [x] `app/(nca)/compliance/page.tsx` — 4 summary cards, overdue list + bulk select, template picker, generate drafts, email log with mark-sent
- [x] `app/(nca)/exports/page.tsx` — CSV builder with filters, download handler, export history
- [x] `app/(auth)/login/page.tsx` — split layout (navy brand panel + form), role-based redirect, password toggle, error handling
- [x] `app/page.tsx` — root redirect to `/login`

---

### 🔲 Phase 6 — Remaining MVP Work

These items are **not yet built**. Pick up from here.

#### Backend

**Providers API** — `apps/providers/` views and URLs are stubs
- [ ] `ProviderProfileSerializer` with nested contacts
- [ ] `GET/POST /api/v1/providers/` — list + create
- [ ] `GET/PATCH /api/v1/providers/{id}/` — detail + update
- [ ] `GET/POST /api/v1/providers/{id}/contacts/` — contact management
- [ ] `PATCH /api/v1/providers/{id}/contacts/{cid}/` — update contact

**Expected submission management**
- [ ] `PATCH /api/v1/expected-submissions/{id}/assign/` — assign officer (update `assigned_officer` field)
- [ ] `PATCH /api/v1/expected-submissions/{id}/override-due-date/` — audited due date override

**Due-state refresh job**
- [ ] Management command `python manage.py refresh_due_states` — loops all open expected submissions and calls `refresh_due_state()`. Run daily via cron or Celery Beat.

**KMZ download endpoint**
- [ ] `GET /api/v1/submissions/{id}/kmz-uploads/{uid}/download/` — serve file from storage path with role-check

**KMZ NCA review**
- [ ] `PATCH /api/v1/submissions/{id}/kmz-uploads/{uid}/review/` — NCA accepts or rejects a KMZ upload

**Feedback & issue reporting**
- [ ] `FeedbackItem` and `SystemIssueTicket` models (see PRD Section 7.13)
- [ ] `POST /api/v1/feedback/` and `POST /api/v1/issues/` — create records, trigger email to configured support address

**Migrations**
- [ ] Run `python manage.py makemigrations` across all apps — migrations are NOT committed to the repo
- [ ] Run `python manage.py migrate` to apply
- [ ] Run `python manage.py loaddata fixtures/ghana_regions.json fixtures/email_templates.json`
- [ ] Create initial NCA admin superuser: `python manage.py createsuperuser`

**Form template data entry**
- [ ] Use Django Admin to create the 7 FormTemplate records (one per form code)
- [ ] Add FormSections, FormFields, FormGrids, GridColumns, GridRows for each form using source PDFs/XLSXs as authority
- [ ] This is data entry work, not code — do it in the Admin UI or via fixtures

#### Frontend

**Provider dashboard** — `app/(provider)/dashboard/page.tsx`
- [ ] List the logged-in provider's expected submissions
- [ ] Group by: not started, draft, submitted, overdue
- [ ] Upcoming due dates prominent
- [ ] Link to form entry for each submission
- [ ] Show completion % for drafts in progress

**Providers management page** — `app/(nca)/providers/page.tsx` + `[id]/page.tsx`
- [ ] Provider list with search by name, filter by category and status
- [ ] Provider detail: profile fields, licence info, contacts list
- [ ] Edit provider profile (NCA Admin only)
- [ ] Add/edit contacts inline

**Periods management page** — `app/(nca)/periods/page.tsx` + `[id]/page.tsx`
- [ ] Period list with status badges (Draft / Active / Closed)
- [ ] Create period form: name, frequency, year, month (if monthly), opens_at, due_at
- [ ] Assign form templates and providers to period
- [ ] Activate period button (calls `POST /periods/{id}/activate/`) with confirmation dialog
- [ ] Period detail: list of all expected submissions for that period with completion stats

**Excel backup upload panel** — `components/forms/ExcelBackupPanel.tsx`
- [ ] Upload `.xlsx`/`.xls` file from inside the provider form entry page
- [ ] Show existing backups with filename, size, upload date
- [ ] Clear label: "Stored for source control only — not used for analysis"

**Conditional field rendering**
- [ ] In `FieldRenderer`, check `field.conditional_on_field` and `field.conditional_on_value`
- [ ] Only render the field if the parent field's current value matches `conditional_on_value`
- [ ] Example: VSAT hub fields only show if "Do you have a VSAT hub?" is "Yes"

**Session timeout**
- [ ] Detect token expiry (JWT `exp` claim) client-side
- [ ] Show a modal warning 2 minutes before expiry with "Stay signed in" (triggers refresh) and "Sign out"
- [ ] Auto-logout and redirect to `/login` on expiry

**MFA verification page** — `app/(auth)/mfa/page.tsx`
- [ ] 6-digit TOTP input after login if `user.mfa_enabled === true`
- [ ] Wire to `POST /api/v1/auth/mfa/verify/` endpoint (not yet built on backend either)

**Toast notifications**
- [ ] Global toast system for save confirmations, errors, and action results
- [ ] Use Framer Motion spring for entrance/exit (emilkowal-animations patterns)

---

### 🔲 Phase 7 — Deployment Package

- [ ] Write `DEPLOYMENT.md` — step-by-step for IT team on a local Ubuntu VM:
  1. Install Docker + Docker Compose
  2. Clone repo
  3. Copy `.env.example` to `.env`, fill in `DB_PASSWORD`, `SECRET_KEY`, `ALLOWED_HOSTS`
  4. `docker-compose -f docker-compose.prod.yml up -d`
  5. Run migrations and seed data (one-time commands)
  6. Create initial superuser
- [ ] Add `Makefile` with shorthand commands: `make migrate`, `make seed`, `make createsuperuser`, `make backup`
- [ ] Backup script: `pg_dump` to a timestamped file + compress media volume
- [ ] Confirm `docker-compose.prod.yml` runs cleanly end-to-end with a smoke test checklist

---

## 18. Key Constraints (Do Not Violate)

1. **No Excel parsing** — Excel files are stored as backup artifacts only. Never read cell values.
2. **KMZ only for fibre** — DC-DBS05 (Domestic Fibre) and DC-SUB03 (Submarine Fibre) only.
3. **Due-state is computed** — never accept due_state as a user input; compute it server-side.
4. **Form versioning** — a submitted 2025 return must continue to render using the 2025 template even after 2026 template is created.
5. **Submission versioning** — each correction resubmission creates a new `Submission` version under the same `ExpectedSubmission`.
6. **Audit log is append-only** — never update or delete `AuditEvent` records.
7. **Provider category drives form access** — an ISP provider can only see and submit ISP forms.
8. **No client-side validation as the only gate** — all validation must be enforced server-side too.
9. **Source forms are authoritative** — the source PDFs and workbooks define sections, field labels, units, and frequencies. The PRD defines system behaviour.
10. **NCA officer sees everything** — providers only see their own submissions and periods relevant to their category.

---

## 19. Existing Prototype

There is a static HTML/CSS prototype in `NCA_Data_CollectionSystem/` (Vite-based). It contains:
- `index.html` — login page
- `provider-dashboard.html` — provider dashboard mockup
- `manual-form-entry.html` — form entry mockup
- `submissions.html` — submissions list mockup
- `src/styles.css` — 863 lines of CSS with correct design tokens

**Do not build on this prototype.** Start the Next.js project fresh. The prototype is useful as a visual reference for layout intent and CSS variable values, which are already extracted into this document and `DESIGN.md`.

---

## 20. Notes for AI Coding Platforms (Codex / Cursor)

### Where the codebase is right now

Repo: **https://github.com/dozzlee/NCA_Data_CollectionSystem**
Branch: `main` — last commit `3871a81`

**Already built — do not rebuild or overwrite:**
- All Django models (Section 6) — live in `backend/apps/*/models.py`
- All backend API views for: auth, dashboard, form templates, submissions (full CRUD), uploads, compliance, exports
- All frontend pages: login, NCA dashboard, NCA submissions list, NCA review, compliance, exports, provider form entry (section stepper + field renderer + grid renderer + KMZ panel)
- Design system: `frontend/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/lib/utils.ts`
- Docker Compose for dev and prod, Nginx config

**Pick up from Phase 6 in Section 17.** Read Section 17 in full before touching any file.

### Rules that must not be broken

- **KMZ upload is restricted to DC-DBS05 and DC-SUB03 only.** The constant `KMZ_ELIGIBLE_FORMS = {"DC-DBS05", "DC-SUB03"}` in `apps/forms_engine/models.py` enforces this at the model level. The API in `apps/uploads/views.py` enforces it at the request level. Never remove either check. Never render `KMZUploadPanel` for any other form code.
- **Migrations are not committed.** Run `python manage.py makemigrations` then `python manage.py migrate` after cloning. Do not commit migration files unless explicitly asked.
- **AuditEvent is append-only.** The `AuditEvent.save()` override raises if `self.pk` is set. Never bypass this.
- **Excel backup files are source control only.** `SubmissionExcelBackup` stores metadata. Never parse, import, or read cell values from uploaded Excel files.
- **Due-state is computed server-side.** The `ExpectedSubmission.compute_due_state()` method owns this logic. The frontend displays it, never computes it.
- **Do not add features outside MVP scope** (Section 1). No Excel import, no GIS, no AI, no direct email send.

### Design system rules

- **Sidebar:** always deep navy (`background: linear-gradient(180deg, #002d5b 0%, #001836 100%)`). Never change this.
- **Font:** Inter throughout. No other typefaces.
- **Radii:** 8px for inputs/buttons/chips, 16px for cards and containers, 9999px for badges/pills.
- **Shadows:** navy-tinted only (`rgba(0, 45, 91, ...)`) — never pure black box shadows.
- **NCA Red `#E31937`:** critical alerts, overdue counts, reject actions only. Not decoration.
- **Data Blue `#0066cc`:** interactive elements, charts, primary actions, focus rings.
- **NCA Gold `#FFD100`:** warnings, due-soon states, pending email drafts only.
- **Apply the three installed design skills** (`impeccable`, `design-taste-frontend`, `emilkowal-animations`) on all new frontend work — invoke them via the Claude Code skill system.

### File paths to know

| What | Path |
|---|---|
| Django settings | `backend/config/settings/base.py` |
| URL root | `backend/config/urls.py` |
| All app models | `backend/apps/{app}/models.py` |
| All app views | `backend/apps/{app}/views.py` |
| All app URLs | `backend/apps/{app}/urls.py` |
| Design tokens | `frontend/app/globals.css` |
| TypeScript types | `frontend/lib/types.ts` |
| API fetch wrapper | `frontend/lib/api.ts` |
| Utility functions + color maps | `frontend/lib/utils.ts` |
| NCA shell layout | `frontend/app/(nca)/layout.tsx` |
| Provider shell layout | `frontend/app/(provider)/layout.tsx` |
| Sidebar component | `frontend/components/layout/Sidebar.tsx` |
| Form field renderer | `frontend/components/forms/FieldRenderer.tsx` |
| Form grid renderer | `frontend/components/forms/GridRenderer.tsx` |
| KMZ upload panel | `frontend/components/forms/KMZUploadPanel.tsx` |
| Section stepper | `frontend/components/forms/SectionStepper.tsx` |

### When in doubt

- Field labels, units, and section names → source PDFs/XLSXs (listed in Section 11 Form Inventory)
- System behaviour → this PRD document and `FINAL_Product Requirements Document - Development Ready.docx`
- Visual decisions → `DESIGN.md` in the parent directory and `PRODUCT.md` in the repo root
