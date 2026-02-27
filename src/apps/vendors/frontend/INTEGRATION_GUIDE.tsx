/**
 * VENDOR 360 - CONTRACT MANAGEMENT INTEGRATION GUIDE
 * 
 * This guide explains how to integrate all the new contract management
 * components into your existing Vendor 360 dashboard.
 */

/**
 * ============================================================================
 * QUICK START - Copy & Paste Integration
 * ============================================================================
 * 
 * 1. IMPORT THE COMPLETE DASHBOARD
 * 
 *    // In your existing Vendor360.tsx or dashboard page
 *    import { Vendor360Dashboard } from '@/components/Vendor360Dashboard';
 * 
 *    export default function VendorDetailPage() {
 *      const { vendorId } = useParams();
 *      const [ vendor, setVendor ] = useState(null);
 *      const [ contacts, setContacts ] = useState([]);
 * 
 *      // Your existing fetch logic...
 * 
 *      return (
 *        <Vendor360Dashboard
 *          vendor={vendor}
 *          vendorContacts={contacts}
 *          onRefresh={refetchVendorData}
 *        />
 *      );
 *    }
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * MODULAR INTEGRATION - Use Individual Components
 * ============================================================================
 * 
 * If you want to integrate components piece by piece into your existing layout:
 * 
 * STEP 1: Import Components
 * ───────────────────────────
 */

import { ContractStats } from '@/components/ContractStats';
import { ContractModal } from '@/components/ContractModal';
import { KeyContacts, CompactKeyContacts } from '@/components/KeyContacts';
import { ContractListView } from '@/components/ContractListView';
import { useContracts, useContractStats } from '@/hooks/useContracts';
import { Contract, ContractFormData } from '@/types/contracts';

/**
 * STEP 2: Use Hooks in Your Component
 * ────────────────────────────────────
 * 
 * export default function MyVendor360View() {
 *   const vendorId = 'vendor-123'; // From route or state
 *   const [isModalOpen, setIsModalOpen] = useState(false);
 *   const [editingContract, setEditingContract] = useState<Contract | null>(null);
 * 
 *   // Load contracts automatically
 *   const {
 *     contracts,
 *     filteredContracts,
 *     loading,
 *     error,
 *     addContract,
 *     updateContract,
 *     deleteContract,
 *     refresh
 *   } = useContracts(vendorId);
 * 
 *   // Calculate statistics reactively
 *   const stats = useContractStats(contracts);
 * 
 *   // ... rest of component logic
 * }
 * 
 * ============================================================================
 */

/**
 * STEP 3: Render Components in JSX
 * ─────────────────────────────────
 * 
 * 3a. Statistics Cards (at the top of your dashboard):
 * 
 *   <ContractStats
 *     stats={stats}
 *     isLoading={loading}
 *     onCardClick={(cardType) => {
 *       // Handle card clicks to filter contracts
 *       console.log('Clicked:', cardType);
 *     }}
 *   />
 * 
 * 3b. Contract List/Table:
 * 
 *   <ContractListView
 *     contracts={filteredContracts}
 *     isLoading={loading}
 *     onAdd={() => {
 *       setEditingContract(null);
 *       setIsModalOpen(true);
 *     }}
 *     onEdit={(contract) => {
 *       setEditingContract(contract);
 *       setIsModalOpen(true);
 *     }}
 *     onDelete={async (contractId) => {
 *       await deleteContract(contractId);
 *       await refresh();
 *     }}
 *     showActions={true}
 *   />
 * 
 * 3c. Key Contacts Section:
 * 
 *   <KeyContacts
 *     contacts={vendorContacts}
 *     onEdit={(contact) => {
 *       // Handle contact edit
 *     }}
 *     showActions={true}
 *   />
 * 
 * 3d. Contract Creation Modal:
 * 
 *   <ContractModal
 *     isOpen={isModalOpen}
 *     onClose={() => {
 *       setIsModalOpen(false);
 *       setEditingContract(null);
 *     }}
 *     onSubmit={async (formData, contractId) => {
 *       try {
 *         if (contractId) {
 *           await updateContract(contractId, formData);
 *         } else {
 *           await addContract({
 *             ...formData,
 *             id: crypto.randomUUID(),
 *             vendorId,
 *             createdAt: new Date(),
 *             updatedAt: new Date(),
 *             createdBy: currentUser.id,
 *             updatedBy: currentUser.id,
 *             status: 'ACTIVE'
 *           });
 *         }
 *         await refresh();
 *         setIsModalOpen(false);
 *         setEditingContract(null);
 *       } catch (error) {
 *         console.error('Failed to save contract:', error);
 *       }
 *     }}
 *     vendorId={vendorId}
 *     contract={editingContract}
 *     contacts={vendorContacts}
 *   />
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * API INTEGRATION GUIDE
 * ============================================================================
 * 
 * The components expect the following API endpoints:
 * 
 * GET /api/v1/vendors/{vendorId}/contracts/
 *   Returns: { results: Contract[], count: number }
 * 
 * GET /api/v1/contracts/?search=...&status=...&type=...
 *   Returns: { results: Contract[], count: number }
 * 
 * POST /api/v1/vendors/{vendorId}/contracts/
 *   Body: ContractFormData
 *   Returns: Contract
 * 
 * PATCH /api/v1/contracts/{contractId}/
 *   Body: Partial<Contract>
 *   Returns: Contract
 * 
 * DELETE /api/v1/contracts/{contractId}/
 *   Returns: 204 No Content
 * 
 * GET /api/v1/vendors/{vendorId}/contacts/
 *   Returns: { results: Contact[], count: number }
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * STYLING REQUIREMENTS
 * ============================================================================
 * 
 * Tailwind CSS classes used:
 * - Core utilities: flex, grid, gap, p-*, m-*, rounded, border, etc.
 * - Colors: bg-blue-*, text-gray-*, border-amber-*, etc.
 * - Responsive: md:, lg:, etc.
 * 
 * Make sure your tailwind.config.js includes:
 * 
 *   module.exports = {
 *     content: [
 *       './src/**/*.{js,jsx,ts,tsx}',
 *     ],
 *     theme: {
 *       extend: {},
 *     },
 *     plugins: [],
 *   }
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * LUCIDE REACT ICONS
 * ============================================================================
 * 
 * Install: npm install lucide-react
 * 
 * Icons used in components:
 * - Plus, Trash2, Edit, Calendar, DollarSign, FileText
 * - User, Mail, Phone, Edit2, AlertCircle, Check
 * - TrendingUp, ChevronDown, X
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * COMPLETE INTEGRATION EXAMPLE - Full Page Component
 * ============================================================================
 */

export default function CompleteIntegrationExample() {
  return `
import React, { useState, useEffect } from 'react';
import { ContractStats } from '@/components/ContractStats';
import { ContractModal } from '@/components/ContractModal';
import { KeyContacts } from '@/components/KeyContacts';
import { ContractListView } from '@/components/ContractListView';
import { useContracts, useContractStats } from '@/hooks/useContracts';
import { Contract, Contact } from '@/types/contracts';

export default function VendorDetailsPage() {
  const vendorId = 'vendor-123'; // From route params
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingContract, setEditingContract] = useState<Contract | null>(null);
  const [vendorData, setVendorData] = useState({
    id: vendorId,
    displayName: 'Acme Corp',
    legalName: 'Acme Corporation Inc.',
    status: 'Active',
    riskTier: 'Low',
    lob: 'IT Services'
  });
  const [vendorContacts, setVendorContacts] = useState<Contact[]>([]);

  const { contracts, loading, error, addContract, updateContract, deleteContract, refresh } = useContracts(vendorId);
  const stats = useContractStats(contracts);

  useEffect(() => {
    // Fetch vendor data and contacts
    async function fetchData() {
      try {
        const [vendorRes, contactsRes] = await Promise.all([
          fetch(\`/api/v1/vendors/\${vendorId}/\`),
          fetch(\`/api/v1/vendors/\${vendorId}/contacts/\`)
        ]);
        
        const vendor = await vendorRes.json();
        const contacts = await contactsRes.json();
        
        setVendorData(vendor);
        setVendorContacts(contacts.results || contacts);
      } catch (error) {
        console.error('Failed to fetch vendor data:', error);
      }
    }

    fetchData();
  }, [vendorId]);

  async function handleSubmitContract(formData, contractId) {
    try {
      if (contractId) {
        await updateContract(contractId, formData);
      } else {
        await addContract({
          ...formData,
          id: crypto.randomUUID(),
          vendorId,
          createdAt: new Date(),
          updatedAt: new Date(),
          createdBy: 'current-user',
          updatedBy: 'current-user'
        });
      }
      await refresh();
      setIsModalOpen(false);
      setEditingContract(null);
    } catch (error) {
      console.error('Failed to save contract:', error);
      throw error;
    }
  }

  return (
    <div className="space-y-8 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{vendorData.displayName}</h1>
          <p className="text-gray-600 mt-1">{vendorData.legalName}</p>
        </div>
      </div>

      {/* Stats Cards */}
      <ContractStats stats={stats} isLoading={loading} />

      {/* List Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Contracts</h2>
        <button
          onClick={() => {
            setEditingContract(null);
            setIsModalOpen(true);
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          + New Contract
        </button>
      </div>

      {/* Contract List */}
      <ContractListView
        contracts={contracts}
        isLoading={loading}
        onEdit={(contract) => {
          setEditingContract(contract);
          setIsModalOpen(true);
        }}
        onDelete={async (contractId) => {
          await deleteContract(contractId);
          await refresh();
        }}
        showActions={true}
      />

      {/* Key Contacts */}
      <KeyContacts contacts={vendorContacts} />

      {/* Modal */}
      <ContractModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingContract(null);
        }}
        onSubmit={handleSubmitContract}
        vendorId={vendorId}
        contract={editingContract}
        contacts={vendorContacts}
      />
    </div>
  );
}
  `;
}

/**
 * ============================================================================
 * CUSTOMIZATION GUIDE
 * ============================================================================
 * 
 * 1. STATUS BADGE COLORS
 *    Edit formatContractStatus() in utils/contractUtils.ts
 * 
 * 2. EXPIRY THRESHOLD
 *    Change getDaysUntilExpiry() threshold from 60 days
 *    in utils/contractUtils.ts
 * 
 * 3. FORM FIELDS
 *    Add/remove fields in ContractModal.tsx
 *    Update ContractFormData interface in types/contracts.ts
 * 
 * 4. API ENDPOINTS
 *    Update fetch calls in useContracts hook
 * 
 * 5. DARK MODE
 *    Use Tailwind's dark: prefix on components
 *    Ensure tailwind.config.js has darkMode: 'class'
 * 
 * ============================================================================
 */

/**
 * ============================================================================
 * COMMON PATTERNS & CODE SNIPPETS
 * ============================================================================
 */

/**
 * PATTERN 1: Filter contracts by status
 * 
 * const activeContracts = contracts.filter(
 *   c => determineContractStatus(c) === 'ACTIVE'
 * );
 */

/**
 * PATTERN 2: Get total value at a glance
 * 
 * const totalValue = stats.totalValue;
 * const formattedValue = formatCurrency(totalValue);
 */

/**
 * PATTERN 3: Check if contract is expiring
 * 
 * const daysLeft = getDaysUntilExpiry(contract.expirationDate);
 * if (daysLeft <= 60) {
 *   // Show expiration warning
 * }
 */

/**
 * PATTERN 4: Form validation before submit
 * 
 * const validation = validateContractForm(formData);
 * if (!validation.isValid) {
 *   console.error('Validation errors:', validation.errors);
 * }
 */

/**
 * ============================================================================
 * TROUBLESHOOTING
 * ============================================================================
 * 
 * Q: "Module not found" errors?
 * A: Check import paths match your project structure
 * 
 * Q: Styles not showing up?
 * A: Ensure Tailwind CSS is installed and configured
 * 
 * Q: Modal not opening?
 * A: Check isOpen prop is being set and onClose is being called
 * 
 * Q: Contracts not loading?
 * A: Check network tab for API errors, ensure endpoint URLs are correct
 * 
 * Q: Stats not updating?
 * A: useContractStats depends on contracts array, ensure it's being populated
 * 
 * ============================================================================
 */
