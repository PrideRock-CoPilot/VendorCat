/**
 * VENDOR 360 - CONTRACT MANAGEMENT
 * Architecture & Component Hierarchy
 */

# 🏗️ System Architecture

## Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                   Vendor360Dashboard                            │
│                   (Complete Solution)                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │         Vendor Header Section                       │       │
│  │  (Name, Status Badge, Risk Tier, LOB)              │       │
│  └─────────────────────────────────────────────────────┘       │
│                          │                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │      Alerts Section (If Contracts Expiring)         │       │
│  │  useContracts() + determineContractStatus()        │       │
│  └─────────────────────────────────────────────────────┘       │
│                          │                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          ContractStats Component                     │       │
│  │                                                     │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│       │
│  │  │  Total   │ │  Active  │ │ Expiring │ │ Value  ││       │
│  │  │Contracts │ │Contracts │ │ Soon     │ │        ││       │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘│       │
│  │                                                     │       │
│  │  Uses: useContractStats()                          │       │
│  │  Calculates: totals, counts, averages (automatically)│    │
│  └─────────────────────────────────────────────────────┘       │
│                          │                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │         Tabbed Interface                            │       │
│  │  ┌──────────────┐    ┌──────────────┐              │       │
│  │  │  Contracts   │    │Contacts      │              │       │
│  │  └──────────────┘    └──────────────┘              │       │
│  │         │                    │                      │       │
│  │         ▼                    ▼                       │       │
│  │   ┌──────────────┐    ┌──────────────┐              │       │
│  │   │Contract List │    │ KeyContacts  │              │       │
│  │   │       View   │    │  Component   │              │       │
│  │   └──────────────┘    └──────────────┘              │       │
│  └─────────────────────────────────────────────────────┘       │
│                          │                                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │          ContractModal Component                    │       │
│  │     (Create/Edit Modal Dialog)                      │       │
│  │                                                     │       │
│  │  ┌──────────────────────────────────────────────┐  │       │
│  │  │  Form Fields:                                │  │       │
│  │  │  - Contract ID, Type, Name, Description      │  │       │
│  │  │  - Value, Currency, Dates                    │  │       │
│  │  │  - Renewal Options                           │  │       │
│  │  │  - Contact Assignment                        │  │       │
│  │  │  - Notes                                     │  │       │
│  │  └──────────────────────────────────────────────┘  │       │
│  │                                                     │       │
│  │  Uses: useContractForm()                           │       │
│  │  Validates: required fields, dates, values         │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     React Component Tree                       │
│                  (User Interface Layer)                        │
└──────────────┬───────────────────────────────────────────────────┘
               │
        ┌──────▼───────┐
        │ Custom Hooks │
        │ (State Mgmt) │◄────────────────────────────────┐
        └──────┬───────┘                                 │
               │                                        │
        ┌──────┴─────────────────────────────────┐      │
        │         useContracts()                 │      │
        │  ├─ contracts[]                        │      │
        │  ├─ loading, error                     │      │
        │  ├─ addContract(), updateContract()   │      │
        │  ├─ deleteContract()                   │      │
        │  └─ refresh()                          │      │
        └──────┬─────────────────────────────────┘      │
               │                                        │
        ┌──────▼──────────────────────────────────────┐ │
        │    Utility Functions                        │ │
        │                                              │ │
        │  determineContractStatus()                  │ │
        │  calculateContractStatistics()              │ │
        │  formatContractStatus()                     │ │
        │  getDaysUntilExpiry()                       │ │
        │  validateContractForm()                     │ │
        │  formatCurrency(), formatDate()             │ │
        │  generateContractAlerts()                   │ │
        └──────┬──────────────────────────────────────┘ │
               │                                        │
        ┌──────▼────────────────────────────────────┐   │
        │       API Layer                           │   │
        │                                            │   │
        │  GET    /api/v1/vendors/{id}/contracts/  │   │
        │  POST   /api/v1/vendors/{id}/contracts/  │   │
        │  PATCH  /api/v1/contracts/{id}/          │   │
        │  DELETE /api/v1/contracts/{id}/          │   │
        │  GET    /api/v1/vendors/{id}/contacts/   │   │
        └──────┬────────────────────────────────────┘   │
               │                                        │
        ┌──────▼────────────────────────────────────┐   │
        │       Database Layer                       │   │
        │                                            │   │
        │  contracts table                          │   │
        │  contract_events table                    │   │
        │  contacts table                           │   │
        │  vendor_contracts table (n-to-n)          │   │
        └────────────────────────────────────────────┘   │
               │                                         │
               └─────────────────────────────────────────┘
                    (Bi-directional data flow)
```

---

## Module Organization

```
frontend/
│
├── components/
│   ├── ContractStats.tsx
│   │   └─ Displays: Total, Active, Expiring, Value cards
│   │   └─ Uses: useContractStats() hook
│   │
│   ├── ContractModal.tsx
│   │   └─ Modal form for create/edit
│   │   └─ Uses: useContractForm() hook for validation
│   │
│   ├── KeyContacts.tsx
│   │   ├─ Full version (large cards)
│   │   ├─ Compact version (sidebar widget)
│   │   └─ All contacts list (table view)
│   │
│   ├── ContractListView.tsx
│   │   ├─ Table view (default, expandable rows)
│   │   ├─ Grid view (card layout)
│   │   └─ Both views: actions, status badges, details
│   │
│   └── Vendor360Dashboard.tsx
│       └─ Orchestrates all components
│       └─ Uses: all hooks, all components
│
├── hooks/
│   └── useContracts.ts (350 lines)
│       ├── useContracts()
│       │   └─ CRUD operations, data fetching
│       ├── useContractStats()
│       │   └─ Memoized statistics calculation
│       ├── useContractForm()
│       │   └─ Form state + validation
│       ├── useContractSearch()
│       │   └─ Search + filtering logic
│       └── useContractNotifications()
│           └─ Alert generation
│
├── utils/
│   └── contractUtils.ts (350 lines)
│       ├── determineContractStatus()
│       ├── calculateContractStatistics()
│       ├── formatContractStatus()
│       ├── getDaysUntilExpiry()
│       ├── formatCurrency()
│       ├── formatDate()
│       ├── validateContractForm()
│       ├── generateContractAlerts()
│       └── getContractChanges()
│
├── types/
│   └── contracts.ts (350 lines)
│       ├── Contract interface
│       ├── ContractType enum
│       ├── ContractStatus enum
│       ├── Contact interface
│       ├── ContactRole enum
│       ├── ContractStatistics interface
│       ├── ContractFormData interface
│       ├── ContractAlert interface
│       └── ... (more types)
│
├── contracts/
│   └── index.ts
│       └─ Barrel exports (components, hooks, types, utils)
│
└── docs/
    ├── README.md                  (Feature overview)
    ├── QUICKSTART.md              (5-minute setup)
    ├── INTEGRATION_GUIDE.tsx      (Integration examples)
    ├── IMPLEMENTATION_SUMMARY.md (This document)
    └── ARCHITECTURE.md            (Architecture guide)
```

---

## Data Type Relationships

```
Vendor (parent)
│
├─ Contract[] (1:M)
│  ├── ContractType (enum)
│  ├── ContractStatus (auto-determined)
│  ├── startDate, expirationDate
│  ├── totalValue, currency
│  ├── accountManager → Contact.id
│  └── technicalLead → Contact.id
│
└─ Contact[] (1:M, role-based)
   ├── ContactRole (ACCOUNT_MANAGER, TECHNICAL_LEAD, etc.)
   ├── firstName, lastName
   ├── email, phone
   ├── title, department
   └── isActive (boolean)
```

---

## State Management Flow

```
┌──────────────────────────────────────────┐
│   User Action (Click "New Contract")     │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Handle setIsModalOpen(true)             │
│  Handle setEditingContract(null)         │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  ContractModal renders with isOpen=true  │
│  useContractForm() initializes state     │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  User fills form, types values           │
│  handleChange() updates formData         │
│  handleBlur() triggers validation        │
│  errors show inline messages             │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  User clicks "Create Contract"           │
│  Form validates before submit            │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  onSubmit() calls addContract()           │
│  Hook sends POST to /api/contracts/      │
│  Backend creates contract                │
│  State updates with new contract         │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Modal closes                            │
│  ContractListView updates (reactively)   │
│  ContractStats recalculates (useMemo)    │
│  UI reflects new data                    │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  User sees new contract in list          │
│  Stats cards show updated numbers        │
│  Success notification shown              │
└──────────────────────────────────────────┘
```

---

## Dependency Graph

```
Vendor360Dashboard
    ├─ useContracts()
    │   └─ Fetches from /api/contracts/
    │
    ├─ useContractStats()
    │   ├─ Depends on: contracts[]
    │   └─ Uses: calculateContractStatistics()
    │
    ├─ ContractStats
    │   ├─ Props: stats, isLoading, onCardClick
    │   └─ Uses: formatCurrency()
    │
    ├─ ContractListView
    │   ├─ Props: contracts, onEdit, onDelete
    │   ├─ Uses: determineContractStatus()
    │   ├─ Uses: formatContractStatus()
    │   ├─ Uses: getDaysUntilExpiry()
    │   └─ Uses: formatDate(), formatCurrency()
    │
    ├─ KeyContacts
    │   └─ Props: contacts, onEdit
    │
    ├─ ContractModal
    │   ├─ useContractForm()
    │   │   ├─ Uses: validateContractForm()
    │   │   └─ State: formData, errors, touched
    │   │
    │   └─ Props: contract, vendorId, contacts
    │
    └─ Error Boundary (implicit)
        └─ Catches API/component errors
```

---

## Performance Optimizations

### Memoization Strategy

```
useContractStats()
    └─ useMemo([contracts])
    └─ Recalculates only when contracts array changes
    └─ Prevents ComponentStats from re-rendering unnecessarily

ContractStats
    └─ const StatCard = ({ bgColor, color, icon, ... }) => (...)
    └─ No memoization needed (simple render)

ContractListView Table
    └─ Each row memoized per contract
    └─ Expandable rows don't affect siblings

ContractModal Form
    └─ Each field validates independently
    └─ No wasteful re-renders of entire form
```

### API Call Optimization

```
useContracts()
    └─ Fetches on mount (useEffect + vendorId dependency)
    └─ useCallback wraps add/update/delete
    └─ Prevents stale closure bugs
    └─ Allows parent to store callback refs
```

---

## Error Handling Flow

```
User Action
    │
    ▼
API Call
    │
    ├─ Network Error
    │   ├─ Set error state
    │   └─ Show error notification
    │
    ├─ Validation Error (400)
    │   ├─ Display field errors in form
    │   └─ Highlight invalid fields
    │
    ├─ Authorization Error (403)
    │   ├─ Show "Access Denied" message
    │   └─ Redirect to login (if needed)
    │
    └─ Server Error (500)
        ├─ Log to error tracking service
        └─ Show "Something went wrong" message
```

---

## Testing Strategy

```
Unit Tests
    ├─ calculateContractStatistics()
    ├─ determineContractStatus()
    ├─ formatContractStatus()
    └─ validateContractForm()

Integration Tests
    ├─ useContracts() hook
    ├─ useContractForm() validation
    └─ Contract CRUD operations

Component Tests
    ├─ ContractStats rendering
    ├─ ContractModal form submission
    ├─ ContractListView CRUD actions
    └─ Vendor360Dashboard navigation

E2E Tests
    ├─ Create contract flow
    ├─ Edit contract flow
    ├─ Delete contract flow
    └─ Status auto-update flow
```

---

## Deployment Checklist

```
Pre-Deployment
  ☐ Code review
  ☐ Unit tests passing
  ☐ Integration tests passing
  ☐ E2E tests passing
  ☐ Performance profiling
  ☐ Accessibility audit

Deployment
  ☐ Build production bundle
  ☐ Verify bundle size < 50KB
  ☐ Deploy to staging
  ☐ Smoke test in staging
  ☐ Deploy to production
  ☐ Monitor error tracking
  ☐ Monitor performance metrics

Post-Deployment
  ☐ Verify all endpoints working
  ☐ Check contract creation workflow
  ☐ Verify stats calculations
  ☐ Monitor API response times
  ☐ Collect user feedback
```

---

**Architecture designed for simplicity, extensibility, and performance.** ✅
