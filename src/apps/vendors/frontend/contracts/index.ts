/**
 * Vendor 360 - Contract Management - Barrel Exports
 * 
 * Import everything you need from a single index file:
 * 
 * import {
 *   ContractStats,
 *   ContractModal,
 *   KeyContacts,
 *   ContractListView,
 *   Vendor360Dashboard,
 *   useContracts,
 *   useContractStats,
 *   Contract,
 *   ContractType,
 *   formatCurrency,
 *   determineContractStatus
 * } from '@/vendor-catalog/contracts';
 */

// ============================================================================
// COMPONENTS
// ============================================================================

export { ContractStats, CompactContractStats } from './components/ContractStats';
export { ContractModal } from './components/ContractModal';
export {
  KeyContacts,
  CompactKeyContacts,
  AllContactsList
} from './components/KeyContacts';
export { ContractListView } from './components/ContractListView';
export {
  Vendor360Dashboard,
  Vendor360Widget
} from './components/Vendor360Dashboard';

// ============================================================================
// HOOKS
// ============================================================================

export {
  useContracts,
  useContractStats,
  useContractForm,
  useContractSearch,
  useContractNotifications
} from './hooks/useContracts';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

export type {
  Contract,
  Contact,
  ContractStatistics,
  ContractFilters,
  ContractFormData,
  ContractTimelineEvent,
  VendorWithContracts,
  ContractAlert
} from './types/contracts';

export {
  ContractType,
  ContractStatus,
  ContactRole,
  TimelineEventType,
  AlertType
} from './types/contracts';

// ============================================================================
// UTILITIES
// ============================================================================

export {
  determineContractStatus,
  getDaysUntilExpiry,
  formatContractStatus,
  calculateContractStatistics,
  formatCurrency,
  formatDate,
  generateContractAlerts,
  validateContractForm,
  getContractChanges
} from './utils/contractUtils';

// ============================================================================
// DEFAULT EXPORT - Complete Dashboard
// ============================================================================

export { default } from './components/Vendor360Dashboard';
