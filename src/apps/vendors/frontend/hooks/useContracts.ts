/**
 * Vendor 360 - Contract Management Hooks
 * 
 * Custom React hooks for managing contract data, state, and operations
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { Contract, ContractStatistics, Contact, ContractFilters, ContractFormData, ContractStatus } from '../types/contracts';
import { calculateContractStatistics, determineContractStatus, generateContractAlerts } from '../utils/contractUtils';

/**
 * Hook: useContracts
 * Manages contract data and operations
 */
export function useContracts(vendorId?: string) {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<ContractFilters>({});

  // Fetch contracts from API
  const fetchContracts = useCallback(async (vid?: string) => {
    try {
      setLoading(true);
      setError(null);
      const endpoint = vid ? `/api/v1/vendors/${vid}/contracts/` : '/api/v1/contracts/';
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error('Failed to fetch contracts');
      const data = await response.json();
      setContracts(data.results || data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setContracts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount or when vendorId changes
  useEffect(() => {
    if (vendorId) {
      fetchContracts(vendorId);
    }
  }, [vendorId, fetchContracts]);

  // Add new contract
  const addContract = useCallback(async (contract: Contract) => {
    try {
      const response = await fetch(`/api/v1/vendors/${contract.vendorId}/contracts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(contract)
      });
      if (!response.ok) throw new Error('Failed to create contract');
      const newContract = await response.json();
      setContracts(prev => [...prev, newContract]);
      return newContract;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      throw err;
    }
  }, []);

  // Update contract
  const updateContract = useCallback(async (id: string, updates: Partial<Contract>) => {
    try {
      const response = await fetch(`/api/v1/contracts/${id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (!response.ok) throw new Error('Failed to update contract');
      const updated = await response.json();
      setContracts(prev => prev.map(c => c.id === id ? updated : c));
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      throw err;
    }
  }, []);

  // Delete contract
  const deleteContract = useCallback(async (id: string) => {
    try {
      const response = await fetch(`/api/v1/contracts/${id}/`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete contract');
      setContracts(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      throw err;
    }
  }, []);

  // Filtered contracts
  const filteredContracts = useMemo(() => {
    return contracts.filter(contract => {
      if (filters.status?.length && !filters.status.includes(contract.status)) return false;
      if (filters.type?.length && !filters.type.includes(contract.type as any)) return false;
      if (filters.minValue && contract.totalValue < filters.minValue) return false;
      if (filters.maxValue && contract.totalValue > filters.maxValue) return false;
      if (filters.searchText && !contract.name.toLowerCase().includes(filters.searchText.toLowerCase())) return false;
      return true;
    });
  }, [contracts, filters]);

  return {
    contracts,
    filteredContracts,
    loading,
    error,
    filters,
    setFilters,
    fetchContracts,
    addContract,
    updateContract,
    deleteContract,
    refresh: () => fetchContracts(vendorId)
  };
}

/**
 * Hook: useContractStats
 * Calculates and memoizes contract statistics
 */
export function useContractStats(contracts: Contract[]): ContractStatistics {
  return useMemo(() => {
    return calculateContractStatistics(contracts);
  }, [contracts]);
}

/**
 * Hook: useContractForm
 * Manages contract form state and validation
 */
export function useContractForm(initialData?: Contract) {
  const [formData, setFormData] = useState<ContractFormData>(
    initialData ? {
      contractId: initialData.contractId,
      type: initialData.type,
      name: initialData.name,
      description: initialData.description,
      totalValue: initialData.totalValue,
      currency: initialData.currency,
      startDate: initialData.startDate,
      expirationDate: initialData.expirationDate,
      renewalOption: initialData.renewalOption,
      autoRenew: initialData.autoRenew,
      renewalTermMonths: initialData.renewalTermMonths,
      accountManager: initialData.accountManager,
      technicalLead: initialData.technicalLead,
      signedDate: initialData.signedDate,
      approvedBy: initialData.approvedBy,
      approvedDate: initialData.approvedDate,
      attachmentUrl: initialData.attachmentUrl,
      notes: initialData.notes,
      tags: initialData.tags
    } : {
      contractId: '',
      type: 'MSA' as any,
      name: '',
      totalValue: 0,
      currency: 'USD',
      startDate: new Date(),
      expirationDate: new Date(),
      tags: []
    }
  );

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const handleChange = useCallback((field: keyof ContractFormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (touched[field]) {
      validateField(field, value);
    }
  }, [touched]);

  const handleBlur = useCallback((field: keyof ContractFormData) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    validateField(field, formData[field]);
  }, [formData]);

  const validateField = (field: keyof ContractFormData, value: any) => {
    const fieldErrors = { ...errors };
    
    switch (field) {
      case 'contractId':
        if (!value?.trim()) fieldErrors.contractId = 'Contract ID is required';
        else delete fieldErrors.contractId;
        break;
      case 'name':
        if (!value?.trim()) fieldErrors.name = 'Name is required';
        else delete fieldErrors.name;
        break;
      case 'totalValue':
        if (value <= 0) fieldErrors.totalValue = 'Must be greater than 0';
        else delete fieldErrors.totalValue;
        break;
      case 'expirationDate':
        if (formData.startDate && value <= formData.startDate) {
          fieldErrors.expirationDate = 'Must be after start date';
        } else {
          delete fieldErrors.expirationDate;
        }
        break;
    }

    setErrors(fieldErrors);
  };

  const isValid = Object.keys(errors).length === 0 && formData.contractId && formData.name;

  const reset = useCallback(() => {
    setFormData({
      contractId: '',
      type: 'MSA' as any,
      name: '',
      totalValue: 0,
      currency: 'USD',
      startDate: new Date(),
      expirationDate: new Date(),
      tags: []
    });
    setErrors({});
    setTouched({});
  }, []);

  return { formData, setFormData, handleChange, handleBlur, errors, touched, isValid, reset };
}

/**
 * Hook: useContractSearch
 * Manages contract search and filtering
 */
export function useContractSearch(contracts: Contract[]) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ContractStatus[]>([]);
  const [sortBy, setSortBy] = useState<'name' | 'value' | 'expiry' | 'date'>('name');

  const filteredAndSorted = useMemo(() => {
    let result = [...contracts];

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(c => 
        c.name.toLowerCase().includes(query) ||
        c.contractId.toLowerCase().includes(query) ||
        c.description?.toLowerCase().includes(query)
      );
    }

    // Apply status filter
    if (statusFilter.length > 0) {
      result = result.filter(c => statusFilter.includes(c.status));
    }

    // Apply sorting
    result.sort((a, b) => {
      switch (sortBy) {
        case 'value':
          return b.totalValue - a.totalValue;
        case 'expiry':
          return new Date(a.expirationDate).getTime() - new Date(b.expirationDate).getTime();
        case 'date':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'name':
        default:
          return a.name.localeCompare(b.name);
      }
    });

    return result;
  }, [contracts, searchQuery, statusFilter, sortBy]);

  return {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    sortBy,
    setSortBy,
    results: filteredAndSorted,
    count: filteredAndSorted.length
  };
}

/**
 * Hook: useContractNotifications
 * Generates notifications for contracts needing attention
 */
export function useContractNotifications(contracts: Contract[], vendorName: string) {
  const [alerts, setAlerts] = useState<any[]>([]);

  useEffect(() => {
    const newAlerts = generateContractAlerts(contracts, vendorName);
    setAlerts(newAlerts);
  }, [contracts, vendorName]);

  const unreadCount = useMemo(() => {
    return alerts.filter(a => !a.isRead).length;
  }, [alerts]);

  const markAsRead = useCallback((alertId: string) => {
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, isRead: true } : a));
  }, []);

  return { alerts, unreadCount, markAsRead };
}
