# Old vs New Vendor Catalog: Feature Comparison & Restoration Plan

**Date:** February 2026  
**Status:** Phase 2 Implementation In Progress  
**Focus:** Django 5 Rebuild with Archived-Route Parity Restoration

---

## Executive Summary

The vendor catalog rebuild is transitioning from basic CRUD operations (10% feature parity) toward full feature restoration. This document compares three implementations:

1. **Legacy System** (Archived) - Full feature set with 50+ database tables
2. **Django 5 Current** - Modern rebuild, 10% feature parity, actively expanding
3. **FastAPI Implementation** (Reference) - 70% feature parity, production-ready alternative

### Recommended Path
Continue Django 5 rebuild with focused phases, using archived route behavior as the parity baseline and shipping in three delivery waves (critical parity, full parity, enhancements).

### Phase 1 Implementation Started (2026-02-22)
Delivered in this implementation wave:

- **Admin RBAC operations (initial parity):** user role assign/revoke, group role assign/revoke, scope grant/revoke APIs under `/api/v1/admin/*`, plus admin portal summary page.
- **Pending approvals queue (initial parity):** queue list, open-next, and decision APIs under `/api/v1/pending-approvals/*`, plus queue UI page.
- **Imports v4 orchestration (initial parity):** explicit preview, mapping, stage, review, and apply endpoints under `/api/v1/imports/jobs/{import_job_id}/*`.
- **Policy snapshot expansion:** group-role inheritance and scope inclusion now flow through identity policy snapshot evaluation.

Validation completed via targeted rebuild tests:

- `tests_rebuild/test_admin_rbac_phase5_rebuild.py`
- `tests_rebuild/test_pending_approvals_phase5_rebuild.py`
- `tests_rebuild/test_imports_phase5_rebuild.py`

### Phase 2 Implementation Progress (2026-02-23)
Delivered in this implementation wave:

- **Global search/typeahead APIs:** `/api/v1/search/vendors`, `/offerings`, `/projects`, `/contracts`, `/users`, `/contacts` with compact result payloads for cross-entity discovery.
- **Merge center APIs:** `/api/v1/vendors/merge/preview` and `/api/v1/vendors/merge/execute` with impact/conflict preview and reassignment semantics.
- **Workflow queue/transition operations:** `/api/v1/workflows/decisions/open-next` and `/api/v1/workflows/decisions/{decision_id}/transition` with guarded state transitions.
- **Project section workflow depth:** `/api/v1/projects/{project_id}/sections` catalog endpoint and `/api/v1/projects/{project_id}/sections/{section_key}/requests` workflow submission endpoint for section-level change requests.
- **Offering operational expansion:** nested APIs for offering contacts, contracts, data flows, service tickets, and documents under `/api/v1/offerings/{offering_id}/*`.
- **Offering detail workspace:** offering detail page now renders operational sections for contacts, contracts, data flows, service tickets, and documents.
- **Offering portfolio analytics (list view):** implemented functional multi-filter search (`q`, `status`, `criticality`, `health`), summary metrics, and needs-attention signals (open tickets + temporary IDs) for triage.
- **Offering program modules:** added governance/compliance profile and license entitlement tracking with APIs and detail-page insights (health score, annual spend rollup, next-renewal countdown).
- **Offering drawer-based operations:** offering detail main sections are display-first, with program profile and entitlement write actions moved into side drawers.
- **Offering operational drawer actions:** contacts, contracts (add), data flows, service tickets, and documents use drawer-based add flows while keeping detail sections read-only.
- **Offering operational edit coverage:** update/delete flows for contacts, data flows, service tickets, and documents remain enforced via scoped mutation endpoints.
- **Section-scoped drawer visibility:** offering detail drawer triggers now render per section permission and offering LOB edit scope (for example, ticket actions can be visible while contract actions remain hidden).
- **Cross-page control parity:** vendor and project detail action controls now use role/scope-gated visibility, including contract section restrictions and edit-button gating.
- **List-page action gating:** vendor/project/offering index pages now gate create/edit controls by role permissions, with offering row-edit visibility additionally enforced by LOB edit scope.
- **Reports/Admin page gating:** reports pages now gate run controls and read visibility by report permissions, and admin portal assignment data is hidden unless access review permission is granted.
- **Operational list CTA gating:** imports and workflows index pages now hide create CTAs (`New Import Job`, `New Workflow`) unless the caller has corresponding mutation permission.
- **Scoped LOB authorization enforcement:** offering-level mutations now enforce LOB scope when user scope grants exist; vendor-level mutations require scoped edit coverage across owner org and all associated offering LOBs.
- **Section-level contract visibility controls:** users without contract read/write permission can access offering pages but contract sections/data are hidden and contract APIs return forbidden.
- **Contact source parity restoration:** vendor/offering contact creation now supports `internal` contacts resolved from active user directory principals (Business Owner/SME/Technical Lead roles) and `external` contacts via existing-contact typeahead reuse with manual entry fallback.

Validation completed via targeted rebuild tests:

- `tests_rebuild/test_search_typeahead_phase5_rebuild.py`
- `tests_rebuild/test_merge_center_phase5_rebuild.py`
- `tests_rebuild/test_imports_phase5_rebuild.py`
- `tests_rebuild/test_workflows_phase5_rebuild.py`
- `tests_rebuild/test_project_workflow_sections_phase5_rebuild.py`
- `tests_rebuild/test_offering_expansion_phase5_rebuild.py`
- `tests_rebuild/test_offering_detail_sections_phase5_rebuild.py`
- `tests_rebuild/test_offering_phase4_rebuild.py` (extended with filter/signal assertions)
- `tests_rebuild/test_offering_program_modules_phase5_rebuild.py`
- `tests_rebuild/test_offering_program_inline_actions_phase5_rebuild.py`
- `tests_rebuild/test_offering_operational_inline_actions_phase5_rebuild.py`
- `tests_rebuild/test_contact_source_parity_rebuild.py`

Additional validation run after parity updates:

- Full rebuild regression suite: `tests_rebuild` (`186 passed`)

---

## System Comparison Matrix

| Feature Category | Legacy | Django Current | FastAPI | Priority |
|---|---|---|---|---|
| **Core CRUD** | ✅ Full | ✅ Complete | ✅ Complete | ✅ DONE |
| Vendor Management | ✅ Advanced | ✅ Basic CRUD | ✅ Advanced | P1 |
| Offering Management | ✅ Advanced | ✅ Basic CRUD | ✅ Advanced | P1 |
| Project Management | ✅ Advanced | ✅ Basic CRUD | ✅ Advanced | P1 |
| Contract Management | ✅ Advanced | ✅ Basic CRUD | ✅ Advanced | P1 |
| **Relationships** | ✅ Full | ⚠️ Partial | ✅ Full | P1 |
| Vendor Contacts | ✅ Yes | ❌ No | ✅ Yes | P2 |
| Vendor Identifiers | ✅ Yes | ❌ No | ✅ Yes | P2 |
| Multi-Source Data | ✅ Yes | ❌ No | ✅ Yes | P3 |
| **Advanced Features** | ✅ Rich | ❌ None | ⚠️ Partial | P2-P3 |
| Onboarding Workflows | ✅ Yes | ❌ No | ❌ No | P2 |
| Change Requests | ✅ Yes | ❌ No | ❌ No | P2 |
| Access Control | ✅ Full | ✅ Partial | ✅ Full | P1 |
| Audit & History | ✅ Full | ❌ Basic | ⚠️ Partial | P2 |
| Import Workflows | ✅ Full | ✅ Basic | ✅ Full | P1 |
| **Governance** | ✅ Complete | ⚠️ Partial | ✅ Complete | P3 |
| Data Quality Rules | ✅ Yes | ❌ No | ⚠️ Partial | P3 |
| Classification | ✅ Yes | ❌ No | ⚠️ Partial | P3 |
| Lineage Tracking | ✅ Yes | ❌ No | ❌ No | P4 |

---

## Feature Gap Analysis

### CRITICAL GAPS (Weeks 1-4)
These must be completed for MVP operational parity:

#### 1. Vendor Relationship Data
**What's Missing:** Contact information, alternative IDs, invoicing details
```
Legacy Tables: vendor_contact, vendor_identifier, vendor_invoice
Django Models: VendorContact, VendorIdentifier ← NEED TO CREATE
FastAPI Reference: /api/vendors/{id}/contacts, /identifiers
```

**Impact:** Cannot manage vendor interactions or billing
**Implementation:** 
- Create Django models (VendorContact, VendorIdentifier, VendorInvoice)
- Add API endpoints for CRUD operations
- Add UI pages for contact/ID management
- Tests: 12+ test cases

**Timeline:** Week 1-2

#### 2. Workflow State Management
**What's Missing:** State transitions for onboarding, change requests, lifecycle management
```
Legacy Tables: workflow_state, onboarding_task, change_request
Django: None — purely CRUD today
FastAPI: Basic workflow structure
```

**Impact:** Cannot manage vendor lifecycle beyond creation
**Implementation:**
- Install `django-fsm` for state machine management
- Create workflow models (OnboardingWorkflow, ChangeRequest)
- Implement state transition validators
- Add workflow APIs with permission control

**Timeline:** Week 2-3

#### 3. Enhanced Access Control
**What's Missing:** Role-based approval workflows, delegation
```
Legacy: Full RBAC + delegation
Django: Basic role checks
FastAPI: Full RBAC
```

**Impact:** All users see all data; no approval workflows
**Implementation:**
- Extend access control to include delegation
- Add approval workflow for requests
- Implement field-level permissions

**Timeline:** Week 4

### HIGH-PRIORITY GAPS (Weeks 5-10)
Features needed for operational excellence:

#### 4. Complete Audit & History
**What's Missing:** SCD Type 2 history tables, change tracking
```
Legacy: Full audit trail with timestamps
Django: None — no historical tracking
FastAPI: Partial audit logging
```

**Impact:** No visibility into what changed or when
**Implementation:**
- Create SCD Type 2 tables for all entities
- Add change tracking middleware
- Build audit log viewer UI
- Tests: 25+ test cases

**Timeline:** Week 5-7

#### 5. Vendor Lifecycle & Classification
**What's Missing:** Detailed status tracking, spending tiers, segmentation
```
Legacy: lifecycle_status, risk_tier, vendor_classification, spend_band
Django: Partial (has lifecycle, risk_tier)
FastAPI: Partial
```

**Impact:** Cannot segment vendors for analysis or management
**Implementation:**
- Add classification models
- Implement spend-band calculation
- Create segmentation logic
- Add reporting APIs

**Timeline:** Week 5-6

#### 6. Invoice & Billing Management
**What's Missing:** Invoice tracking, payment terms, reconciliation
```
Legacy: vendor_invoice, invoice_line_item, payment_term
Django: None
FastAPI: Stub structures
```

**Impact:** Cannot track spend or manage payments
**Implementation:**
- Create Invoice and InvoiceLineItem models
- Add import workflow for invoice data
- Build invoice dashboard
- Tests: 15+ test cases

**Timeline:** Week 7-9

#### 7. Expanded Import Workflows
**What's Missing:** Multi-source ingestion, conflict resolution, enrichment
```
Legacy: import_source, data_flow, ingestion_rule, field_mapping
Django: Basic import support
FastAPI: Basic import support
```

**Impact:** Manual data entry only; no bulk ingestion
**Implementation:**
- Extend import models with source configuration
- Add conflict resolution logic
- Build data enrichment engine
- Create import monitoring UI

**Timeline:** Week 8-10

### MEDIUM-PRIORITY GAPS (Weeks 11-16)
Advanced features for governance and reporting:

#### 8. Data Quality & Validation Rules
**What's Missing:** Custom validation, quality scoring, automated remediation
```
Legacy: quality_rule, quality_metric, validation_log
Django: Basic field validation only
FastAPI: Basic field validation only
```

**Impact:** No proactive data quality monitoring
**Implementation:**
- Create QualityRule and QualityMetric models
- Build rule engine
- Add quality scoring
- Create data quality dashboard

**Timeline:** Week 11-12

#### 9. Comprehensive Search & Discovery
**What's Missing:** Global search across vendors/offerings/contacts/documents
```
Legacy: Full-text search with filtering
Django: Basic vendor search only
FastAPI: Basic vendor search only
```

**Impact:** Difficult to find information across catalog
**Implementation:**
- Add search indexing (Elasticsearch or similar)
- Implement faceted search
- Add advanced filtering
- Build search UI

**Timeline:** Week 11-13

#### 10. Advanced Reporting & Analytics
**What's Missing:** Dashboards, ad-hoc reports, trend analysis
```
Legacy: 15+ predefined reports
Django: Minimal reporting
FastAPI: Minimal reporting
```

**Impact:** Limited visibility into vendor portfolio
**Implementation:**
- Create reporting models and views
- Build dashboard widgets
- Implement report builder
- Add export functionality

**Timeline:** Week 13-16

### LOWER-PRIORITY GAPS (Weeks 17-24)
Advanced governance and enterprise features:

#### 11. Data Lineage & Provenance
**What's Missing:** Track data source, transformations, dependencies
```
Legacy: lineage_graph, data_flow, transformation_log
Django: None
FastAPI: None
```

**Impact:** Cannot trace data origin or transformations
**Timeline:** Week 17-19

#### 12. Contract & SLA Management
**What's Missing:** Extended contract fields, SLA tracking, renewal management
```
Legacy: contract_sla, renewal_schedule, performance_metric
Django: Basic contracts only
```

**Impact:** Limited contract lifecycle management
**Timeline:** Week 19-21

#### 13. Multi-Tenancy Features
**What's Missing:** Department/division segregation, cost center tracking
```
Legacy: tenant_context, cost_center, business_unit
Django: Single tenant only
```

**Impact:** Cannot segment by organizational unit
**Timeline:** Week 21-23

#### 14. Advanced Notifications & Workflow Triggers
**What's Missing:** Event-driven automation, notification rules, integrations
```
Legacy: event_trigger, notification_template, integration_endpoint
Django: Basic email only
```

**Impact:** Limited automation capabilities
**Timeline:** Week 23-24

---

## 24-Week Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
**Goal:** Critical operational features

**Week 1-2: Data Models**
- [ ] Create VendorContact model with relationship to Vendor
- [ ] Create VendorIdentifier model (internal/external IDs)
- [ ] Create APIs for contact/identifier CRUD
- [ ] Add UI pages for contact management
- [ ] Tests: 12+ test cases covering CRUD and validation

**Week 3: State Management**
- [ ] Install django-fsm library
- [ ] Create OnboardingWorkflow model with state machine
- [ ] Create ChangeRequest model with approval flow
- [ ] Add workflow state transition APIs
- [ ] Add workflow status monitoring UI
- [ ] Tests: 10+ test cases for state transitions

**Week 4: Access Control Enhancement**
- [ ] Extend RBAC with approval role
- [ ] Add delegation model
- [ ] Implement approval workflow APIs
- [ ] Test: 8+ test cases for complex permission scenarios

**Deliverables:**
- Contact/identifier management fully operational
- Workflow state machine foundation
- Approval workflow basics
- 30+ new tests, coverage > 80%

**Estimated Effort:** 2 developers × 4 weeks = 8 developer-weeks

---

### Phase 2: Advanced Relationships (Weeks 5-7)
**Goal:** Complete audit trail and vendor data

**Week 5: SCD Type 2 History Tables**
- [ ] Create HistoricalVendor (SCD2) table
- [ ] Create HistoricalOffering, HistoricalProject, HistoricalContract tables
- [ ] Implement audit middleware for all entity changes
- [ ] Add change_reason and changed_by fields
- [ ] Tests: 15+ test cases for history tracking

**Week 6: Complete Vendor Attributes**
- [ ] Add vendor_classification field and choices
- [ ] Add spend_band calculation logic
- [ ] Add risk_assessment model
- [ ] Implement segmentation logic
- [ ] Tests: 10+ test cases

**Week 7: Vendor Detail Enhancement**
- [ ] Extend vendor detail API with nested contacts/identifiers
- [ ] Add vendor timeline view (history)
- [ ] Update vendor detail UI with all new fields
- [ ] Tests: 8+ test cases

**Deliverables:**
- Complete audit trail for all entities
- SCD2 history tables populated on all changes
- Enhanced vendor data model
- 33+ new tests

**Estimated Effort:** 2 developers × 3 weeks = 6 developer-weeks

---

### Phase 3: Billing & Financial (Weeks 8-10)
**Goal:** Invoice and payment tracking

**Week 8: Invoice Models & APIs**
- [ ] Create Invoice model with financial fields (amount, due_date, terms)
- [ ] Create InvoiceLineItem model
- [ ] Create PaymentTerm model
- [ ] Add invoice CRUD APIs
- [ ] Tests: 12+ test cases

**Week 9: Invoice Import & Reconciliation**
- [ ] Extend import workflows for invoice data
- [ ] Add invoice reconciliation logic
- [ ] Create invoice matching algorithms
- [ ] Tests: 10+ test cases

**Week 10: Invoice Dashboard & Reporting**
- [ ] Build invoice dashboard with aging report
- [ ] Add payment status visualization
- [ ] Create invoice export functionality
- [ ] Tests: 8+ test cases

**Deliverables:**
- Complete invoice and payment management
- Invoice import workflows
- Invoice reporting and aging analysis
- 30+ new tests

**Estimated Effort:** 1.5 developers × 3 weeks = 4.5 developer-weeks

---

### Phase 4: Import Enhancements (Weeks 11-13)
**Goal:** Advanced data ingestion capabilities

**Week 11: Multi-Source Configuration**
- [ ] Extend import models with source configuration
- [ ] Add data source registry
- [ ] Create import schedule model
- [ ] Tests: 12+ test cases

**Week 12: Conflict Resolution & Enrichment**
- [ ] Implement conflict detection logic
- [ ] Add user-guided conflict resolution
- [ ] Create data enrichment engine
- [ ] Tests: 10+ test cases

**Week 13: Import Monitoring & Analytics**
- [ ] Build import job dashboard
- [ ] Add import health metrics
- [ ] Create error tracking and retry logic
- [ ] Tests: 8+ test cases

**Deliverables:**
- Advanced import workflow engine
- Multi-source data ingestion
- Conflict resolution UI
- Import monitoring dashboard
- 30+ new tests

**Estimated Effort:** 2 developers × 3 weeks = 6 developer-weeks

---

### Phase 5: Quality & Governance (Weeks 14-16)
**Goal:** Data quality monitoring and advanced search

**Week 14: Quality Rules Engine**
- [ ] Create QualityRule model with rule DSL
- [ ] Create QualityMetric model
- [ ] Implement rule evaluation engine
- [ ] Build quality scoring algorithm
- [ ] Tests: 12+ test cases

**Week 15: Global Search Implementation**
- [ ] Set up search indexing (Elasticsearch or similar)
- [ ] Add full-text search across all entities
- [ ] Implement faceted filtering
- [ ] Build advanced search UI
- [ ] Tests: 12+ test cases

**Week 16: Data Quality Dashboard**
- [ ] Create quality metrics dashboard
- [ ] Add quality alerts and notifications
- [ ] Implement quality trend analysis
- [ ] Tests: 8+ test cases

**Deliverables:**
- Complete data quality framework
- Global search with advanced filters
- Quality monitoring dashboard
- 32+ new tests

**Estimated Effort:** 2 developers × 3 weeks = 6 developer-weeks

---

### Phase 6: Advanced Features (Weeks 17-24)
**Goal:** Enterprise-grade capabilities

**Week 17-19: Data Lineage (3 weeks)**
- [ ] Create lineage graph model
- [ ] Implement lineage tracking in imports
- [ ] Build lineage visualization UI
- Tests: 15+ test cases

**Week 19-21: Contract & SLA Management (3 weeks)**
- [ ] Extend contract model with SLA fields
- [ ] Create SLA tracking model
- [ ] Build SLA compliance dashboard
- [ ] Add renewal management
- Tests: 15+ test cases

**Week 21-23: Multi-Tenancy Features (3 weeks)**
- [ ] Add tenant/division context
- [ ] Implement cost center tracking
- [ ] Add organizational unit segmentation
- [ ] Update all queries with tenant filtering
- Tests: 15+ test cases

**Week 23-24: Advanced Automation (2 weeks)**
- [ ] Create event trigger system
- [ ] Add notification templates
- [ ] Build integration endpoints
- [ ] Add workflow automation
- Tests: 10+ test cases

**Deliverables:**
- Enterprise lineage tracking
- Complete contract lifecycle management
- Multi-tenancy support
- Event-driven automation
- 55+ new tests

**Estimated Effort:** 2-3 developers × 7 weeks = 14-21 developer-weeks

---

## Architectural Decisions

### Decision 1: Continue Django 5 Rebuild
**Status:** ✅ APPROVED

| Aspect | Django | FastAPI |
|--------|--------|---------|
| **Team Expertise** | Existing Django 5 expertise | Requires new learning curve |
| **Complexity** | Well-established patterns | Newer, less established patterns in team |
| **ORM Support** | Django ORM (excellent) | Manual or Pydantic models |
| **Testing** | Mature pytest ecosystem | pytest compatible but fewer patterns |
| **Migration Path** | Evolutionary from existing | Complete rewrite required |
| **Template Support** | Full Jinja2 + HTMX | Requires separate frontend |

**Rationale:** Team has existing Django expertise. FastAPI can serve as reference architecture without diverting focus.

**Implementation:** Continue Phase 4-6 work in Django with FastAPI app preserved in `archive/original-build/` as reference.

---

### Decision 2: Core Features First, Advanced Later
**Status:** ✅ APPROVED

**Order of Implementation:**
1. **Weeks 1-7:** Core relationships (contacts, identifiers, basic workflows) + audit
2. **Weeks 8-13:** Billing + advanced imports
3. **Weeks 14-16:** Quality + search
4. **Weeks 17-24:** Governance + enterprise features

**Rationale:** Users need functional contacts/identifiers/workflows before advanced features. Staged rollout allows for feedback and course correction.

**Risk Mitigation:** Each phase is independently deployable; can pause and adjust based on user feedback.

---

### Decision 3: Use django-fsm for Workflow State Management
**Status:** ✅ APPROVED

**Library:** `django-fsm>=3.0`

**Alternative Considered:** Custom state logic
- **Pros:** Full control, no external dependency
- **Cons:** Complex to maintain, error-prone state transitions

**django-fsm Rationale:**
- Proven library with 3K+ GitHub stars
- Easy state validation
- Built-in transition guards
- Decorator-based flow (clean)
- Audit-friendly (logs transitions)

**Example Usage:**
```python
from django_fsm import FSMField, transition

class OnboardingWorkflow(models.Model):
    status = FSMField(default='pending', 
                     choices=[('pending', 'Pending'),
                             ('in_progress', 'In Progress'),
                             ('completed', 'Completed')])
    
    @transition(field=status, source='pending', target='in_progress')
    def start(self):
        """Transition from pending to in_progress"""
        self.started_at = timezone.now()
```

---

### Decision 4: SCD Type 2 for Complete Audit Trail
**Status:** ✅ APPROVED

**Approach:** Slowly Changing Dimension Type 2 - track all changes with effective/end dates

**Implementation Pattern:**
```python
# Current table
class Vendor(models.Model):
    name = models.CharField()
    status = models.CharField()
    updated_at = models.DateTimeField(auto_now=True)

# Historical table (SCD2)
class HistoricalVendor(models.Model):
    vendor = models.ForeignKey(Vendor)
    name = models.CharField()
    status = models.CharField()
    effective_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True)
    changed_at = models.DateTimeField()
    changed_by = models.ForeignKey(User)
    change_reason = models.CharField()
```

**Rationale:**
- Complete audit trail without deleting data
- Can reconstruct state at any point in time
- Compliance-friendly (e.g., SOX, HIPAA)
- Minimal performance impact (separate table)

**Alternative:** Purely timestamp-based or delete-on-update
- **Rationale for SCD2:** More precise, audit-compliant

---

## Technology Stack

### Backend
- **Framework:** Django 5.0+ with Django REST Framework
- **Database:** PostgreSQL (primary), DuckDB (local development)
- **Backend Services:**
  - `django-fsm>=3.0` - Workflow state management
  - `django-mptt` - Hierarchical data (if needed)
  - `celery + redis` - Async task processing (Phase 5+)
  - `elasticsearch` - Full-text search (Phase 5)
  - `dbt` - Data transformation (optional, Phase 6)

### Frontend
- **Template Engine:** Jinja2 with HTMX
- **UI Framework:** Bootstrap 5 or similar
- **JavaScript:** Vanilla JS + Alpine.js for interactivity

### Testing & Quality
- **Test Framework:** pytest with pytest-django
- **Coverage:** Minimum 80% on new code
- **Linting:** ruff, mypy
- **CI/CD:** GitHub Actions (strict)

### Deployment
- **Target:** Databricks or cloud VMs
- **Container:** Docker (optional, Phase 6)
- **Version Control:** Git with semantic versioning

---

## Resource Requirements

### Team Composition
- **Backend Developers:** 2-3 (Django/Python expertise)
- **Frontend Developer:** 1 (Django templates + HTMX)
- **QA/Testing:** 1 (automated test development)
- **DevOps:** 0.5 (deployment automation)

### Total: 4.5 FTE over 24 weeks

### Distribution
- **Weeks 1-7 (Discovery + Core):** 2.5 FTE (intensive)
- **Weeks 8-13 (Expansion):** 3 FTE (peak)
- **Weeks 14-16 (Quality):** 2 FTE
- **Weeks 17-24 (Enterprise):** 2 FTE

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Workflow logic complexity | High | Use proven django-fsm library, extensive testing |
| Data migration issues | High | Test migrations on production copy, rollback plan |
| Performance at scale | Medium | Early load testing, query optimization, indexing strategy |
| Team skill gaps | Medium | Pair programming, code reviews, documentation |
| Scope creep | High | Strict phase gating, stakeholder sign-off per phase |
| FastAPI reference outdated | Medium | Keep in sync or explicitly freeze version |

---

## Success Metrics

### Code Quality
- ✅ Test coverage: >85% (rebuild scope)
- ✅ Lint/type-check: 100% pass
- ✅ Deployment: Zero-downtime (via feature flags)

### Feature Completeness
- ✅ Week 4: Core relationships operational
- ✅ Week 7: Audit trail comprehensive
- ✅ Week 13: All operational features complete
- ✅ Week 24: Enterprise parity with legacy

### Performance
- ✅ Vendor list load: <500ms
- ✅ Search results: <1s (100K records)
- ✅ Import processing: 10K+ records/minute

### User Adoption
- ✅ Phase 1-2 (Weeks 1-7): Pilot user group
- ✅ Phase 3-4 (Weeks 8-13): Broader team adoption
- ✅ Phase 5-6 (Weeks 14-24): Full organization on new system

---

## Next Steps

1. **Review & Approval** (This Week)
   - Stakeholder review of 24-week plan
   - Confirm resource allocation
   - Finalize Phase 1-2 scope

2. **Setup & Planning** (Week 1-2)
   - Create project board per phase
   - Set up development environment
   - Assign Phase 1 owners
   - Schedule daily standups

3. **Phase 1 Kickoff** (Week 1)
   - Begin VendorContact model implementation
   - Set up test infrastructure
   - Establish code review process
   - Create API documentation

4. **Continuous Review**
   - Weekly progress review
   - Phase gate sign-off before proceeding
   - Adjust timeline based on learnings
   - Maintain stakeholder communication

---

## References

- **FastAPI Implementation:** `archive/original-build/` (70% feature reference)
- **Legacy Schema:** `archive/sql_catalog/` (50+ table comprehensive schema)
- **Current Django:** `src/` (ongoing rebuild, currently Phase 4 complete)
- **Test Suite:** `tests_rebuild/` (30+ test modules, 80%+ coverage)

---

**Document Status:** Strategic Planning Complete | Ready for Execution  
**Last Updated:** February 2026  
**Next Review:** After Phase 2 Completion (Week 7)
