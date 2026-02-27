/**
 * Vendor 360 - Contract Management Data Structures & Types
 * 
 * Comprehensive TypeScript interfaces for contracts, contacts, and related entities
 */

/**
 * Contract Types/Categories
 */
export enum ContractType {
  MSA = "MSA",              // Master Service Agreement
  SOW = "SOW",              // Statement of Work
  NDA = "NDA",              // Non-Disclosure Agreement
  PURCHASE = "PURCHASE",    // Purchase Agreement
  LEASE = "LEASE",          // Lease Agreement
  SERVICE = "SERVICE",      // Service Agreement
  SUPPORT = "SUPPORT",      // Support/Maintenance Agreement
  LICENSE = "LICENSE",      // License Agreement
  PARTNERSHIP = "PARTNERSHIP", // Partnership Agreement
  OTHER = "OTHER"
}

/**
 * Contract Status (derived from expiration date)
 */
export enum ContractStatus {
  ACTIVE = "ACTIVE",
  EXPIRING_SOON = "EXPIRING_SOON",  // Within 60 days
  EXPIRED = "EXPIRED",
  TERMINATED = "TERMINATED",
  PENDING = "PENDING",
  DRAFT = "DRAFT"
}

/**
 * Contract object - Core contract entity
 */
export interface Contract {
  id: string;                      // Unique identifier (UUID or database ID)
  vendorId: string;                // Foreign key to Vendor
  contractId: string;              // External contract reference number
  type: ContractType;              // Type of contract
  name: string;                    // Contract name/title
  description?: string;            // Detailed description
  totalValue: number;              // Contract value in USD
  currency: string;                // ISO currency code (default: USD)
  startDate: Date;                 // Contract start date
  expirationDate: Date;            // Contract expiration date
  status: ContractStatus;          // Derived status
  renewalOption?: boolean;         // Can it be renewed?
  renewalDate?: Date;              // Auto-renewal date if applicable
  autoRenew?: boolean;             // Auto-renews?
  renewalTermMonths?: number;      // Renewal period in months
  
  // Key contacts
  accountManager?: string;         // Account manager contact ID
  technicalLead?: string;          // Technical lead contact ID
  
  // Compliance & tracking
  signedDate?: Date;               // When contract was signed
  approvedBy?: string;             // Who approved it
  approvedDate?: Date;             // Approval date
  
  // Metadata
  attachmentUrl?: string;          // Link to document
  notes?: string;                  // Internal notes
  tags?: string[];                 // Tags for categorization
  
  createdAt: Date;
  updatedAt: Date;
  createdBy: string;
  updatedBy: string;
}

/**
 * Contact object - Key personnel from vendor
 */
export interface Contact {
  id: string;
  vendorId: string;
  firstName: string;
  lastName: string;
  email: string;
  phone?: string;
  title: string;
  department?: string;
  role: ContactRole;
  isPrimary: boolean;
  isActive: boolean;
  notes?: string;
  
  createdAt: Date;
  updatedAt: Date;
}

export enum ContactRole {
  ACCOUNT_MANAGER = "ACCOUNT_MANAGER",
  TECHNICAL_LEAD = "TECHNICAL_LEAD",
  EXECUTIVE = "EXECUTIVE",
  FINANCE = "FINANCE",
  OPERATIONS = "OPERATIONS",
  SUPPORT = "SUPPORT",
  OTHER = "OTHER"
}

/**
 * Contract Statistics - Aggregated metrics
 */
export interface ContractStatistics {
  totalCount: number;           // Total number of contracts
  activeCount: number;          // Number of active contracts
  expiringCount: number;        // Number expiring within 60 days
  expiredCount: number;         // Number expired
  totalValue: number;           // Sum of all contract values
  activeValue: number;          // Sum of active contract values
  expiringValue: number;        // Sum of expiring contract values
  averageValue: number;         // Average contract value
  averageTermMonths: number;    // Average contract duration
}

/**
 * Contract Filter/Search Criteria
 */
export interface ContractFilters {
  vendorId?: string;
  status?: ContractStatus[];
  type?: ContractType[];
  fromDate?: Date;
  toDate?: Date;
  minValue?: number;
  maxValue?: number;
  searchText?: string;
  tags?: string[];
}

/**
 * Contract Creation/Update Form Data
 */
export interface ContractFormData {
  contractId: string;
  type: ContractType;
  name: string;
  description?: string;
  totalValue: number;
  currency: string;
  startDate: Date;
  expirationDate: Date;
  renewalOption?: boolean;
  autoRenew?: boolean;
  renewalTermMonths?: number;
  accountManager?: string;
  technicalLead?: string;
  signedDate?: Date;
  approvedBy?: string;
  approvedDate?: Date;
  attachmentUrl?: string;
  notes?: string;
  tags?: string[];
}

/**
 * Contract Timeline Event (for history/audit trail)
 */
export interface ContractTimelineEvent {
  id: string;
  contractId: string;
  eventType: TimelineEventType;
  eventDate: Date;
  actor: string;
  description: string;
  beforeValue?: any;
  afterValue?: any;
}

export enum TimelineEventType {
  CREATED = "CREATED",
  SIGNED = "SIGNED",
  APPROVED = "APPROVED",
  ACTIVATED = "ACTIVATED",
  MODIFIED = "MODIFIED",
  RENEWED = "RENEWED",
  EXPIRED = "EXPIRED",
  TERMINATED = "TERMINATED",
  COMMENTED = "COMMENTED"
}

/**
 * Vendor with enhanced contract data
 */
export interface VendorWithContracts {
  id: string;
  vendorId: string;
  displayName: string;
  legalName: string;
  status: string;
  riskTier: string;
  lob?: string;
  
  // Contract related
  contracts: Contract[];
  contacts: Contact[];
  contractStats: ContractStatistics;
}

/**
 * Notification/Alert for expiring contracts
 */
export interface ContractAlert {
  id: string;
  contractId: string;
  vendorId: string;
  vendorName: string;
  contractName: string;
  daysUntilExpiry: number;
  expirationDate: Date;
  alertType: AlertType;
  isRead: boolean;
  createdAt: Date;
}

export enum AlertType {
  EXPIRING_SOON = "EXPIRING_SOON",
  EXPIRING_CRITICAL = "EXPIRING_CRITICAL",  // < 7 days
  EXPIRED = "EXPIRED",
  RENEWAL_APPROACHING = "RENEWAL_APPROACHING"
}
