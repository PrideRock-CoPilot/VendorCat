/**
 * VENDOR 360 - CONTRACT MANAGEMENT
 * Quick-Start Implementation Guide
 * 
 * This document provides step-by-step instructions to integrate contract
 * management into your Vendor 360 dashboard.
 */

# CONTRACT MANAGEMENT - QUICK START GUIDE

## 📦 What's Included

This package provides complete contract management functionality for your Vendor 360 app:

### Types & Schemas (`types/contracts.ts`)
- `Contract` - Main contract entity with all fields
- `ContractType` - Enum for MSA, SOW, NDA, etc.
- `ContractStatus` - Auto-calculated based on expiration date
- `Contact` - Vendor contact person
- `ContractStatistics` - Aggregated metrics
- `ContractFormData` - Form submission payload

### Utilities (`utils/contractUtils.ts`)
- **`determineContractStatus()`** - Auto-labels contracts as "Expiring Soon" if within 60 days
- **`calculateContractStatistics()`** - Reactively calculates stats from contracts
- **`formatContractStatus()`** - Returns display label, color, and styling
- **`getDaysUntilExpiry()`** - Calculates days remaining
- **`formatCurrency()`** & **`formatDate()`** - Display formatters
- **`validateContractForm()`** - Form validation
- **`generateContractAlerts()`** - Create notifications for expiring contracts

### Hooks (`hooks/useContracts.ts`)
- **`useContracts(vendorId)`** - Manages contract CRUD operations and data fetching
- **`useContractStats(contracts)`** - Memoized statistics calculation
- **`useContractForm(contract)`** - Form state management with validation
- **`useContractSearch(contracts)`** - Search and filtering logic
- **`useContractNotifications(contracts)`** - Alert generation

### Components

#### 1. **ContractStats.tsx** - Statistics Dashboard
Display 4 key metrics in card format:
- Total Contracts
- Active Contracts  
- Expiring Soon (with warning)
- Total Contract Value

```tsx
<ContractStats
  stats={stats}
  isLoading={loading}
  onCardClick={(cardType) => handleCardClick(cardType)}
/>
```

#### 2. **ContractModal.tsx** - Create/Edit Form
Complete modal form with:
- Contract ID, Type, Name
- Value & Currency
- Start & Expiration dates
- Renewal options with auto-renew
- Contact assignment (Account Manager, Tech Lead)
- Notes & Tags
- Full validation with error messages

```tsx
<ContractModal
  isOpen={isModalOpen}
  onClose={handleClose}
  onSubmit={handleSaveContract}
  vendorId={vendorId}
  contract={editingContract}
  contacts={vendorContacts}
/>
```

#### 3. **KeyContacts.tsx** - Contact Directory
Three variants:

**Full Version** - Large cards showing Account Manager & Technical Lead
```tsx
<KeyContacts contacts={vendorContacts} onEdit={handleEdit} />
```

**Compact Version** - Sidebar widget
```tsx
<CompactKeyContacts contacts={vendorContacts} />
```

**All Contacts List** - Table view of all contacts
```tsx
<AllContactsList contacts={vendorContacts} onEdit={handleEdit} onAdd={handleAdd} />
```

#### 4. **ContractListView.tsx** - Contract Table/Grid
Displays contracts with expandable details:
- Table view (default) with inline expansion
- Grid view alternative
- Status badges with color coding
- "Expiring Soon" counter
- Edit/Delete actions
- Empty state with create button

```tsx
<ContractListView
  contracts={contracts}
  onEdit={handleEdit}
  onDelete={handleDelete}
  showActions={true}
/>
```

#### 5. **Vendor360Dashboard.tsx** - Complete Integration
Ready-to-use dashboard combining all components:
- Vendor header with status badges
- Statistics cards
- Tabbed interface (Contracts/Contacts)
- Contract list with actions
- Key contacts display
- Modal management

```tsx
<Vendor360Dashboard
  vendor={vendor}
  vendorContacts={contacts}
  onRefresh={refreshData}
/>
```

---

## 🚀 Getting Started (5 Minutes)

### Step 1: Copy Files to Your Project
```
src/
  apps/
    vendors/
      frontend/
        components/
          ├── ContractStats.tsx
          ├── ContractModal.tsx
          ├── KeyContacts.tsx
          ├── ContractListView.tsx
          └── Vendor360Dashboard.tsx
        hooks/
          └── useContracts.ts
        utils/
          └── contractUtils.ts
        types/
          └── contracts.ts
```

### Step 2: Install Dependencies
```bash
npm install lucide-react
# Tailwind CSS should already be installed
```

### Step 3: Use Complete Dashboard
The simplest way - just drop in the complete dashboard:

```tsx
// In your vendor detail page
import { Vendor360Dashboard } from '@/components/Vendor360Dashboard';

export default function VendorPage() {
  const vendor = { /* your vendor data */ };
  const contacts = [ /* vendor contacts */ ];
  
  return (
    <Vendor360Dashboard
      vendor={vendor}
      vendorContacts={contacts}
      onRefresh={refetchData}
    />
  );
}
```

### Step 4: Ensure API Endpoints Exist
Make sure your backend provides these endpoints:
```
GET /api/v1/vendors/{vendorId}/contracts/
POST /api/v1/vendors/{vendorId}/contracts/
PATCH /api/v1/contracts/{contractId}/
DELETE /api/v1/contracts/{contractId}/
```

---

## 📊 Key Features Explained

### Automatic Status Determination
Contracts automatically get their status based on expiration date:

```
- ACTIVE: Started, expires in 60+ days
- EXPIRING_SOON: Within 60 days of expiration ⚠️
- EXPIRED: Passed expiration date
- PENDING: Not yet started
- TERMINATED: Manually marked terminated
```

### Reactive Statistics
All stats update automatically as contracts change:

```typescript
// Example: stats automatically recalculate when contracts array changes
const stats = useContractStats(contracts);
// Output:
// {
//   totalCount: 15,
//   activeCount: 12,
//   expiringCount: 2,
//   totalValue: 2500000,
//   ...
// }
```

### Form Validation
Built-in validation with helpful error messages:

```
Required fields:
  - Contract ID
  - Contract Name
  - Contract Type
  - Total Value (> 0)
  - Start Date
  - Expiration Date (must be after start date)

Optional:
  - Description, renewal terms, notes, contacts
```

---

## 🎨 Customization Examples

### Change Expiry Warning Threshold (from 60 to 90 days)
```typescript
// In utils/contractUtils.ts, determineContractStatus():
const EXPIRY_THRESHOLD = 90; // Changed from 60
...
if (daysUntilExpiry <= EXPIRY_THRESHOLD) {
  return ContractStatus.EXPIRING_SOON;
}
```

### Add Custom Status Colors
```typescript
// In utils/contractUtils.ts, formatContractStatus():
const statusMap = {
  [ContractStatus.ACTIVE]: {
    bgColor: 'bg-blue-100',      // ← Change color
    textColor: 'text-blue-800',
    ...
  }
}
```

### Customize Modal Form Fields
```tsx
// In components/ContractModal.tsx, inside the form:
<input
  // Add any new field here
  value={formData.customField}
  onChange={(e) => handleChange('customField', e.target.value)}
/>
```

---

## 🔌 API Contract

### Fetch Contracts
```
GET /api/v1/vendors/{vendorId}/contracts/
Response: { results: Contract[], count: number }
```

### Create Contract
```
POST /api/v1/vendors/{vendorId}/contracts/
Body: ContractFormData
Response: Contract (with id, createdAt, status)
```

### Update Contract
```
PATCH /api/v1/contracts/{contractId}/
Body: Partial<Contract>
Response: Contract
```

### Delete Contract
```
DELETE /api/v1/contracts/{contractId}/
Response: 204 No Content
```

---

## 💡 Common Usage Patterns

### 1. Show Alert for Expiring Contracts
```tsx
const expiringContracts = contracts.filter(c => 
  c.status === 'EXPIRING_SOON'
);

{expiringContracts.length > 0 && (
  <Alert severity="warning">
    {expiringContracts.length} contracts expiring soon!
  </Alert>
)}
```

### 2. Filter Contracts by Status
```tsx
const { filters, setFilters } = useContractSearch(contracts);

// Filter to show only active contracts
setFilters({ status: ['ACTIVE'] });
```

### 3. Export Total Contract Value
```tsx
const totalValue = stats.totalValue;
const report = {
  vendor: vendor.name,
  totalContracts: stats.totalCount,
  totalValue: formatCurrency(totalValue),
  exported: new Date()
};
```

### 4. Get Contract Summary
```tsx
const summary = `
  Vendor: ${vendor.name}
  Total Contracts: ${stats.totalCount}
  Active: ${stats.activeCount}
  Expiring Soon: ${stats.expiringCount}
  Total Value: ${formatCurrency(stats.totalValue)}
`;
```

---

## 🧪 Testing Guidelines

### Test Contract Status Determination
```typescript
test('marks contracts as expiring if within 60 days', () => {
  const contract = {
    expirationDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
  };
  expect(determineContractStatus(contract)).toBe('EXPIRING_SOON');
});
```

### Test Statistics Calculation
```typescript
test('calculates correct statistics from contracts', () => {
  const contracts = [
    { status: 'ACTIVE', totalValue: 1000000 },
    { status: 'ACTIVE', totalValue: 500000 },
    { status: 'EXPIRED', totalValue: 200000 }
  ];
  const stats = calculateContractStatistics(contracts);
  expect(stats.totalCount).toBe(3);
  expect(stats.activeCount).toBe(2);
  expect(stats.totalValue).toBe(1700000);
});
```

### Test Form Validation
```typescript
test('validates required fields', () => {
  const data = { contractId: '', name: '' };
  const { isValid, errors } = validateContractForm(data);
  expect(isValid).toBe(false);
  expect(errors.contractId).toBeDefined();
  expect(errors.name).toBeDefined();
});
```

---

## 🐛 Troubleshooting

**Q: Stats not updating when contracts change?**
A: Make sure you're passing the contracts array as a dependency to useContractStats

**Q: Modal form not submitting?**
A: Check that all required fields are filled and validation passes

**Q: API errors?**
A: Check browser Network tab, verify endpoint URLs and authentication

**Q: Styles not applying?**
A: Ensure Tailwind CSS is properly configured and scan paths include these files

---

## 📚 File Size & Performance

- **Types**: ~3KB
- **Utils**: ~8KB  
- **Hooks**: ~6KB
- **Components**: 15KB total
- **Total Bundle**: ~32KB (gzipped: ~10KB)

All components are optimized with React.memo and useMemo for performance.

---

## 🔄 Update Strategy

When updating components:
1. Backup existing files
2. Update one component at a time
3. Test each integration
4. Run your test suite
5. Deploy with confidence!

---

## 📞 Support

For questions or issues integrating these components:
1. Check INTEGRATION_GUIDE.tsx for examples
2. Review component prop interfaces in the source code
3. Check browser console for errors
4. Verify API endpoints are working

---

**Ready to integrate? Start with the complete Vendor360Dashboard component - it's the fastest path to a fully-featured contract management system!** ✅
