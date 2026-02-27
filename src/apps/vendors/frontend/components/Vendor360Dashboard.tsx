/**
 * Vendor 360 Dashboard - Complete Integration Example
 * 
 * This is a ready-to-use example of how to integrate all contract management
 * components into the Vendor 360 dashboard
 */

import React, { useState, useMemo } from 'react';
import { Plus, AlertCircle } from 'lucide-react';
import { Contract, Contact, ContractFormData } from '../types/contracts';
import { useContracts, useContractStats } from '../hooks/useContracts';
import { ContractStats } from './ContractStats';
import { ContractModal } from './ContractModal';
import { KeyContacts } from './KeyContacts';
import { ContractListView } from './ContractListView';
import { determineContractStatus } from '../utils/contractUtils';

interface Vendor {
  id: string;
  vendorId: string;
  displayName: string;
  legalName: string;
  status: string;
  riskTier: string;
  lob?: string;
}

interface Vendor360DashboardProps {
  vendor: Vendor;
  vendorContacts?: Contact[];
  onRefresh?: () => Promise<void>;
}

/**
 * Complete Vendor 360 Dashboard with Contract Management
 * 
 * @example
 * ```tsx
 * <Vendor360Dashboard
 *   vendor={selectedVendor}
 *   vendorContacts={vendorContacts}
 *   onRefresh={refreshVendorData}
 * />
 * ```
 */
export const Vendor360Dashboard: React.FC<Vendor360DashboardProps> = ({
  vendor,
  vendorContacts = [],
  onRefresh
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingContract, setEditingContract] = useState<Contract | null>(null);
  const [activeTab, setActiveTab] = useState<'contracts' | 'contacts'>('contracts');

  // Fetch contracts using the hook
  const {
    contracts,
    filteredContracts,
    loading,
    error,
    addContract,
    updateContract,
    deleteContract,
    refresh
  } = useContracts(vendor.id);

  // Calculate statistics
  const stats = useContractStats(contracts);

  // Filter for expiring contracts
  const expiringContracts = useMemo(() => {
    return contracts.filter(c => {
      const status = determineContractStatus(c);
      return status === 'EXPIRING_SOON' || status === 'EXPIRED';
    });
  }, [contracts]);

  // Handle contract form submission
  const handleSubmitContract = async (formData: ContractFormData, contractId?: string) => {
    try {
      if (contractId) {
        // Update existing contract
        await updateContract(contractId, {
          ...formData,
          vendorId: vendor.id,
          status: determineContractStatus({
            ...formData,
            id: contractId,
            vendorId: vendor.id
          } as Contract)
        } as any);
      } else {
        // Create new contract
        const newContract: Contract = {
          ...formData,
          id: `contract-${Date.now()}`,
          vendorId: vendor.id,
          status: determineContractStatus({
            ...formData,
            id: `contract-${Date.now()}`,
            vendorId: vendor.id
          } as Contract),
          createdAt: new Date(),
          updatedAt: new Date(),
          createdBy: 'current-user',
          updatedBy: 'current-user'
        };
        await addContract(newContract);
      }
      setEditingContract(null);
      setIsModalOpen(false);
      await onRefresh?.();
    } catch (error) {
      console.error('Failed to save contract:', error);
      throw error;
    }
  };

  const handleOpenModal = (contract?: Contract) => {
    if (contract) {
      setEditingContract(contract);
    }
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingContract(null);
  };

  return (
    <div className="space-y-8">
      {/* Header with vendor info */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-lg p-6 text-white">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold">{vendor.displayName}</h1>
            <p className="text-blue-100 mt-1">{vendor.legalName}</p>
            <div className="flex gap-4 mt-4">
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                vendor.status === 'Active' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-amber-100 text-amber-800'
              }`}>
                {vendor.status}
              </span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                vendor.riskTier === 'Low'
                  ? 'bg-green-100 text-green-800'
                  : vendor.riskTier === 'Medium'
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                Risk: {vendor.riskTier}
              </span>
              {vendor.lob && (
                <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-semibold">
                  {vendor.lob}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Error notification */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle size={20} />
          <div>
            <p className="font-semibold">Error loading contracts</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Expiring contracts alert */}
      {expiringContracts.length > 0 && (
        <div className="flex items-start gap-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertCircle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-900">
              {expiringContracts.length} contract{expiringContracts.length !== 1 ? 's' : ''} need attention
            </p>
            <p className="text-sm text-amber-700">
              Review contracts expiring soon to plan renewals
            </p>
          </div>
        </div>
      )}

      {/* Statistics cards */}
      <ContractStats
        stats={stats}
        isLoading={loading}
        onCardClick={(cardType) => {
          setActiveTab('contracts');
          // Could filter contracts here based on card type
        }}
      />

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex gap-8">
          <button
            onClick={() => setActiveTab('contracts')}
            className={`px-1 py-3 font-semibold border-b-2 transition ${
              activeTab === 'contracts'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Contracts ({contracts.length})
          </button>
          <button
            onClick={() => setActiveTab('contacts')}
            className={`px-1 py-3 font-semibold border-b-2 transition ${
              activeTab === 'contacts'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Key Contacts
          </button>
        </div>
      </div>

      {/* Contracts Tab */}
      {activeTab === 'contracts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">Contracts</h2>
            <button
              onClick={() => handleOpenModal()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
            >
              <Plus size={18} />
              New Contract
            </button>
          </div>

          <ContractListView
            contracts={filteredContracts}
            isLoading={loading}
            onAdd={() => handleOpenModal()}
            onEdit={(contract) => handleOpenModal(contract)}
            onDelete={async (contractId) => {
              try {
                await deleteContract(contractId);
                await onRefresh?.();
              } catch (error) {
                console.error('Failed to delete contract:', error);
              }
            }}
            onViewDetails={(contract) => {
              // Could open a detail view modal here
              console.log('View details:', contract);
            }}
            showActions={true}
            emptyMessage="No contracts yet. Create your first contract to get started!"
          />
        </div>
      )}

      {/* Contacts Tab */}
      {activeTab === 'contacts' && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">Vendor Team</h2>

          {/* Key Contacts */}
          <KeyContacts
            contacts={vendorContacts}
            onEdit={(contact) => {
              // Could open contact editor here
              console.log('Edit contact:', contact);
            }}
            isLoading={loading}
            showActions={true}
          />
        </div>
      )}

      {/* Contract Modal */}
      <ContractModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onSubmit={handleSubmitContract}
        vendorId={vendor.id}
        contract={editingContract || undefined}
        contacts={vendorContacts.map(c => ({
          id: c.id,
          firstName: c.firstName,
          lastName: c.lastName,
          title: c.title
        }))}
        isLoading={loading}
      />
    </div>
  );
};

/**
 * Compact sidebar widget for quick vendor overview
 */
export const Vendor360Widget: React.FC<{ vendor: Vendor; contacts: Contact[] }> = ({
  vendor,
  contacts
}) => {
  const { contracts, loading } = useContracts(vendor.id);
  const stats = useContractStats(contracts);
  const accountManager = contacts.find(c => c.role === 'ACCOUNT_MANAGER' && c.isActive);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-900 mb-4">{vendor.displayName}</h3>

      {/* Quick stats */}
      <div className="space-y-2 mb-4 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-gray-600">Total Contracts</span>
          <span className="font-semibold text-gray-900">{stats.totalCount}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-600">Active</span>
          <span className="font-semibold text-green-600">{stats.activeCount}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-600">Total Value</span>
          <span className="font-semibold text-gray-900">${(stats.totalValue / 1000000).toFixed(1)}M</span>
        </div>
      </div>

      {/* Account manager */}
      {accountManager && (
        <div className="border-t border-gray-200 pt-3">
          <p className="text-xs text-gray-600 font-semibold mb-1">Account Manager</p>
          <p className="text-sm text-gray-900">{accountManager.firstName} {accountManager.lastName}</p>
          <a
            href={`mailto:${accountManager.email}`}
            className="text-xs text-blue-600 hover:underline"
          >
            {accountManager.email}
          </a>
        </div>
      )}
    </div>
  );
};

export default Vendor360Dashboard;
