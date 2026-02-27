/**
 * Vendor 360 - Contract Management Utilities
 * 
 * Helper functions for contract status determination, calculations, and formatting
 */

import { Contract, ContractStatus, ContractStatistics, ContractAlert, AlertType } from '../types/contracts';

/**
 * Determines contract status based on expiration date and contract state
 * Automatically labels as "Expiring Soon" if within 60 days
 * @param contract - The contract to evaluate
 * @param currentStatus - Current status from database (optional override)
 * @returns Calculated ContractStatus
 */
export function determineContractStatus(
  contract: Contract,
  currentStatus?: ContractStatus
): ContractStatus {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // If explicitly terminated, always return terminated
  if (currentStatus === ContractStatus.TERMINATED || contract.status === ContractStatus.TERMINATED) {
    return ContractStatus.TERMINATED;
  }

  // Check if expired
  const expirationDate = new Date(contract.expirationDate);
  expirationDate.setHours(0, 0, 0, 0);

  if (expirationDate < today) {
    return ContractStatus.EXPIRED;
  }

  // Check if expiring soon (within 60 days)
  const daysUntilExpiry = Math.floor((expirationDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (daysUntilExpiry <= 60) {
    return ContractStatus.EXPIRING_SOON;
  }

  // Otherwise active (assuming startDate is in the past)
  const startDate = new Date(contract.startDate);
  startDate.setHours(0, 0, 0, 0);

  if (startDate > today) {
    return ContractStatus.PENDING;
  }

  return ContractStatus.ACTIVE;
}

/**
 * Calculates days remaining until contract expiration
 * @param expirationDate - Contract expiration date
 * @returns Number of days remaining, negative if already expired
 */
export function getDaysUntilExpiry(expirationDate: Date): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const expDate = new Date(expirationDate);
  expDate.setHours(0, 0, 0, 0);

  return Math.floor((expDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

/**
 * Formats a contract status for display with color and label
 * @param status - Contract status
 * @returns Object with label, color, and badge class
 */
export function formatContractStatus(
  status: ContractStatus
): { label: string; color: string; bgColor: string; textColor: string; iconClass: string } {
  const statusMap = {
    [ContractStatus.ACTIVE]: {
      label: "Active",
      color: "green",
      bgColor: "bg-green-50",
      textColor: "text-green-700",
      iconClass: "text-green-500"
    },
    [ContractStatus.EXPIRING_SOON]: {
      label: "Expiring Soon",
      color: "amber",
      bgColor: "bg-amber-50",
      textColor: "text-amber-700",
      iconClass: "text-amber-500"
    },
    [ContractStatus.EXPIRED]: {
      label: "Expired",
      color: "red",
      bgColor: "bg-red-50",
      textColor: "text-red-700",
      iconClass: "text-red-500"
    },
    [ContractStatus.TERMINATED]: {
      label: "Terminated",
      color: "gray",
      bgColor: "bg-gray-50",
      textColor: "text-gray-700",
      iconClass: "text-gray-500"
    },
    [ContractStatus.PENDING]: {
      label: "Pending",
      color: "blue",
      bgColor: "bg-blue-50",
      textColor: "text-blue-700",
      iconClass: "text-blue-500"
    },
    [ContractStatus.DRAFT]: {
      label: "Draft",
      color: "slate",
      bgColor: "bg-slate-50",
      textColor: "text-slate-700",
      iconClass: "text-slate-500"
    }
  };

  return statusMap[status] || statusMap[ContractStatus.ACTIVE];
}

/**
 * Calculates comprehensive statistics from a list of contracts
 * @param contracts - Array of contracts
 * @returns ContractStatistics object
 */
export function calculateContractStatistics(contracts: Contract[]): ContractStatistics {
  if (!contracts || contracts.length === 0) {
    return {
      totalCount: 0,
      activeCount: 0,
      expiringCount: 0,
      expiredCount: 0,
      totalValue: 0,
      activeValue: 0,
      expiringValue: 0,
      averageValue: 0,
      averageTermMonths: 0
    };
  }

  const stats: ContractStatistics = {
    totalCount: contracts.length,
    activeCount: 0,
    expiringCount: 0,
    expiredCount: 0,
    totalValue: 0,
    activeValue: 0,
    expiringValue: 0,
    averageValue: 0,
    averageTermMonths: 0
  };

  let totalTermMonths = 0;

  contracts.forEach(contract => {
    // Add to total value
    stats.totalValue += contract.totalValue;

    // Count by status
    const status = determineContractStatus(contract);
    if (status === ContractStatus.ACTIVE) {
      stats.activeCount++;
      stats.activeValue += contract.totalValue;
    } else if (status === ContractStatus.EXPIRING_SOON) {
      stats.expiringCount++;
      stats.expiringValue += contract.totalValue;
    } else if (status === ContractStatus.EXPIRED) {
      stats.expiredCount++;
    }

    // Calculate term in months
    const startDate = new Date(contract.startDate);
    const endDate = new Date(contract.expirationDate);
    const months = (endDate.getFullYear() - startDate.getFullYear()) * 12 +
                   (endDate.getMonth() - startDate.getMonth());
    totalTermMonths += Math.max(months, 1);
  });

  stats.averageValue = Math.round(stats.totalValue / contracts.length);
  stats.averageTermMonths = Math.round(totalTermMonths / contracts.length);

  return stats;
}

/**
 * Formats currency for display
 * @param amount - Numeric amount
 * @param currency - ISO currency code (default: USD)
 * @returns Formatted currency string
 */
export function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount);
}

/**
 * Formats a date for display
 * @param date - Date to format
 * @param format - Format style ('short', 'long', 'full')
 * @returns Formatted date string
 */
export function formatDate(date: Date, format: 'short' | 'long' | 'full' = 'short'): string {
  const opts: Intl.DateTimeFormatOptions = {
    short: { month: '2-digit', day: '2-digit', year: '2-digit' },
    long: { year: 'numeric', month: 'long', day: 'numeric' },
    full: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }
  };

  return new Date(date).toLocaleDateString('en-US', opts[format]);
}

/**
 * Generates alerts for contracts that need attention
 * @param contracts - Array of contracts
 * @param vendorName - Name of the vendor
 * @returns Array of ContractAlert objects
 */
export function generateContractAlerts(contracts: Contract[], vendorName: string): ContractAlert[] {
  const alerts: ContractAlert[] = [];
  const today = new Date();

  contracts.forEach(contract => {
    const daysUntilExpiry = getDaysUntilExpiry(new Date(contract.expirationDate));
    const status = determineContractStatus(contract);

    if (status === ContractStatus.EXPIRED) {
      alerts.push({
        id: `${contract.id}-expired`,
        contractId: contract.id,
        vendorId: contract.vendorId,
        vendorName,
        contractName: contract.name,
        daysUntilExpiry,
        expirationDate: new Date(contract.expirationDate),
        alertType: AlertType.EXPIRED,
        isRead: false,
        createdAt: today
      });
    } else if (daysUntilExpiry <= 7) {
      alerts.push({
        id: `${contract.id}-critical`,
        contractId: contract.id,
        vendorId: contract.vendorId,
        vendorName,
        contractName: contract.name,
        daysUntilExpiry,
        expirationDate: new Date(contract.expirationDate),
        alertType: AlertType.EXPIRING_CRITICAL,
        isRead: false,
        createdAt: today
      });
    } else if (daysUntilExpiry <= 60) {
      alerts.push({
        id: `${contract.id}-expiring`,
        contractId: contract.id,
        vendorId: contract.vendorId,
        vendorName,
        contractName: contract.name,
        daysUntilExpiry,
        expirationDate: new Date(contract.expirationDate),
        alertType: AlertType.EXPIRING_SOON,
        isRead: false,
        createdAt: today
      });
    }
  });

  return alerts;
}

/**
 * Validates contract form data
 * @param data - Form data to validate
 * @returns Object with isValid flag and error messages
 */
export function validateContractForm(data: any): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  if (!data.contractId?.trim()) {
    errors.contractId = 'Contract ID is required';
  }

  if (!data.name?.trim()) {
    errors.name = 'Contract name is required';
  }

  if (!data.type) {
    errors.type = 'Contract type is required';
  }

  if (!data.totalValue || data.totalValue <= 0) {
    errors.totalValue = 'Total value must be greater than 0';
  }

  if (!data.startDate) {
    errors.startDate = 'Start date is required';
  }

  if (!data.expirationDate) {
    errors.expirationDate = 'Expiration date is required';
  }

  if (data.startDate && data.expirationDate) {
    const start = new Date(data.startDate);
    const expiry = new Date(data.expirationDate);
    if (start >= expiry) {
      errors.expirationDate = 'Expiration date must be after start date';
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
}

/**
 * Compares two contracts for changes
 * @param original - Original contract
 * @param updated - Updated contract
 * @returns Object showing what changed
 */
export function getContractChanges(
  original: Contract,
  updated: Contract
): Record<string, { from: any; to: any }> {
  const changes: Record<string, { from: any; to: any }> = {};
  const keysToCheck = [
    'name', 'type', 'description', 'totalValue', 'currency',
    'startDate', 'expirationDate', 'status', 'renewalOption',
    'autoRenew', 'renewalTermMonths', 'accountManager', 'technicalLead',
    'signedDate', 'approvedBy', 'approvedDate', 'notes'
  ];

  keysToCheck.forEach(key => {
    const origValue = (original as any)[key];
    const updValue = (updated as any)[key];

    if (JSON.stringify(origValue) !== JSON.stringify(updValue)) {
      changes[key] = { from: origValue, to: updValue };
    }
  });

  return changes;
}
