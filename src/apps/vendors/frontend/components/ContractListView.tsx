/**
 * Vendor 360 - Contract List Component
 * 
 * Displays contracts in a table with filtering, searching, and status indicators
 */

import React, { useState } from 'react';
import { Plus, Trash2, Edit, Calendar, DollarSign, FileText, ChevronDown } from 'lucide-react';
import { Contract, ContractStatus } from '../types/contracts';
import { formatDate, formatCurrency, formatContractStatus, getDaysUntilExpiry } from '../utils/contractUtils';

interface ContractListProps {
  contracts: Contract[];
  isLoading?: boolean;
  onAdd?: () => void;
  onEdit?: (contract: Contract) => void;
  onDelete?: (contractId: string) => void;
  onViewDetails?: (contract: Contract) => void;
  showActions?: boolean;
  emptyMessage?: string;
}

/**
 * Status badge component
 */
const StatusBadge: React.FC<{ status: ContractStatus }> = ({ status }) => {
  const { label, bgColor, textColor } = formatContractStatus(status);
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${bgColor} ${textColor}`}>
      {label}
    </span>
  );
};

/**
 * Contract table view
 */
const ContractTable: React.FC<ContractListProps> = ({
  contracts,
  isLoading,
  onAdd,
  onEdit,
  onDelete,
  onViewDetails,
  showActions = true,
  emptyMessage = "No contracts yet. Create your first contract!"
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="space-y-2 p-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-12 bg-gray-200 animate-pulse rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (contracts.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 border-dashed p-12 text-center">
        <FileText size={48} className="text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 mb-4">{emptyMessage}</p>
        {onAdd && (
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            <Plus size={18} />
            Create First Contract
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left font-semibold text-gray-700">Contract</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-700">Value</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-700">Dates</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
              {showActions && <th className="px-4 py-3 text-center font-semibold text-gray-700">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {contracts.map((contract) => {
              const daysUntilExpiry = getDaysUntilExpiry(new Date(contract.expirationDate));
              const isExpanded = expandedId === contract.id;

              return (
                <React.Fragment key={contract.id}>
                  <tr className="hover:bg-gray-50 transition cursor-pointer">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : contract.id)}
                          className="text-gray-400 hover:text-gray-600"
                        >
                          <ChevronDown
                            size={16}
                            className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                          />
                        </button>
                        <div
                          onClick={() => onViewDetails?.(contract)}
                          className="cursor-pointer flex-1"
                        >
                          <p className="font-medium text-gray-900">{contract.name}</p>
                          <p className="text-xs text-gray-500">{contract.contractId}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                        {contract.type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-semibold text-gray-900">
                        {formatCurrency(contract.totalValue, contract.currency)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      <div>{formatDate(new Date(contract.startDate))}</div>
                      <div className="text-gray-500">→ {formatDate(new Date(contract.expirationDate))}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={contract.status} />
                        {contract.status === ContractStatus.EXPIRING_SOON && (
                          <span className="text-xs text-amber-700 font-semibold">
                            {daysUntilExpiry}d left
                          </span>
                        )}
                      </div>
                    </td>
                    {showActions && (
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          {onEdit && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onEdit(contract);
                              }}
                              className="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded transition"
                              title="Edit contract"
                            >
                              <Edit size={16} />
                            </button>
                          )}
                          {onDelete && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (confirm('Delete this contract? This action cannot be undone.')) {
                                  onDelete(contract.id);
                                }
                              }}
                              className="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition"
                              title="Delete contract"
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>

                  {/* Expanded details row */}
                  {isExpanded && (
                    <tr className="bg-gray-50 border-t border-gray-200">
                      <td colSpan={showActions ? 6 : 5} className="px-4 py-4">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                          {contract.description && (
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Description</p>
                              <p className="text-sm text-gray-700">{contract.description}</p>
                            </div>
                          )}

                          {contract.renewalOption && (
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Renewal</p>
                              <p className="text-sm text-gray-700">
                                {contract.renewalTermMonths}-month term
                                {contract.autoRenew && ' (Auto-renews)'}
                              </p>
                            </div>
                          )}

                          {contract.signedDate && (
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Signed Date</p>
                              <p className="text-sm text-gray-700">
                                {formatDate(new Date(contract.signedDate))}
                              </p>
                            </div>
                          )}

                          {contract.approvedBy && (
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Approved By</p>
                              <p className="text-sm text-gray-700">{contract.approvedBy}</p>
                            </div>
                          )}

                          {contract.notes && (
                            <div className="md:col-span-3">
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Notes</p>
                              <p className="text-sm text-gray-700">{contract.notes}</p>
                            </div>
                          )}

                          {contract.attachmentUrl && (
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase mb-1">Document</p>
                              <a
                                href={contract.attachmentUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-blue-600 hover:underline"
                              >
                                View Document →
                              </a>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/**
 * Card grid view for contracts
 */
interface ContractCardGridProps extends Omit<ContractListProps, 'showActions'> {
  viewMode?: 'table' | 'grid';
}

export const ContractListView: React.FC<ContractCardGridProps> = (props) => {
  const { viewMode = 'table' } = props;

  if (viewMode === 'grid') {
    return <ContractCardGrid {...props} />;
  }

  return <ContractTable {...props} />;
};

const ContractCardGrid: React.FC<ContractListProps> = ({
  contracts,
  isLoading,
  onAdd,
  onEdit,
  onDelete,
  showActions = true,
  emptyMessage
}) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-48 bg-gray-200 animate-pulse rounded-lg" />
        ))}
      </div>
    );
  }

  if (contracts.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 border-dashed p-12 text-center col-span-3">
        <FileText size={48} className="text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 mb-4">{emptyMessage}</p>
        {onAdd && (
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            <Plus size={18} />
            Create First Contract
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {contracts.map(contract => {
        const daysUntilExpiry = getDaysUntilExpiry(new Date(contract.expirationDate));
        const { bgColor, textColor } = formatContractStatus(contract.status);

        return (
          <div key={contract.id} className="bg-white rounded-lg border border-gray-200 hover:shadow-md transition overflow-hidden">
            <div className={`h-1 ${bgColor}`} />

            <div className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h4 className="font-semibold text-gray-900">{contract.name}</h4>
                  <p className="text-xs text-gray-500">{contract.contractId}</p>
                </div>
                <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${bgColor} ${textColor}`}>
                  {contract.type}
                </span>
              </div>

              <div className="space-y-2 mb-4 text-sm">
                <div className="flex items-center gap-2 text-gray-700">
                  <DollarSign size={14} className="text-gray-400" />
                  <span className="font-semibold">{formatCurrency(contract.totalValue, contract.currency)}</span>
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <Calendar size={14} className="text-gray-400" />
                  <span className="text-xs">
                    {formatDate(new Date(contract.startDate))} → {formatDate(new Date(contract.expirationDate))}
                  </span>
                </div>
              </div>

              <div className="border-t border-gray-200 pt-3 flex items-center justify-between">
                <StatusBadge status={contract.status} />
                {contract.status === ContractStatus.EXPIRING_SOON && (
                  <span className="text-xs text-amber-700 font-semibold">{daysUntilExpiry}d</span>
                )}
              </div>

              {showActions && (
                <div className="border-t border-gray-200 mt-3 pt-3 flex gap-2 justify-end">
                  {onEdit && (
                    <button
                      onClick={() => onEdit(contract)}
                      className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition"
                      title="Edit"
                    >
                      <Edit size={16} />
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={() => {
                        if (confirm('Delete this contract?')) {
                          onDelete(contract.id);
                        }
                      }}
                      className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ContractListView;
