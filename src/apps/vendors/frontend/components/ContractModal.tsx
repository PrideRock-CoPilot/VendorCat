/**
 * Vendor 360 - Contract Creation/Edit Modal Component
 * 
 * Modal form for creating and editing contracts with validation
 */

import React, { useState, useEffect } from 'react';
import { X, Plus, Check, AlertCircle } from 'lucide-react';
import { Contract, ContractType, ContractFormData } from '../types/contracts';
import { useContractForm } from '../hooks/useContracts';
import { validateContractForm, formatDate } from '../utils/contractUtils';

interface ContractModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ContractFormData, contractId?: string) => Promise<void>;
  vendorId: string;
  contract?: Contract;
  contacts?: Array<{ id: string; firstName: string; lastName: string; title: string }>;
  isLoading?: boolean;
}

/**
 * Contract Modal - Create/Edit contracts
 */
export const ContractModal: React.FC<ContractModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  vendorId,
  contract,
  contacts = [],
  isLoading = false
}) => {
  const { formData, handleChange, handleBlur, errors, touched, isValid, reset } = useContractForm(contract);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(false);

    const validation = validateContractForm(formData);
    if (!validation.isValid) {
      setSubmitError('Please fix the errors below');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit(formData, contract?.id);
      setSubmitSuccess(true);
      reset();
      setTimeout(() => {
        onClose();
        setSubmitSuccess(false);
      }, 1500);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to save contract');
    } finally {
      setIsSubmitting(false);
    }
  };

  const contractTypeOptions = Object.values(ContractType);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">
            {contract ? 'Edit Contract' : 'Create New Contract'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Error/Success Messages */}
          {submitError && (
            <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle size={20} />
              <span>{submitError}</span>
            </div>
          )}

          {submitSuccess && (
            <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
              <Check size={20} />
              <span>Contract {contract ? 'updated' : 'created'} successfully!</span>
            </div>
          )}

          {/* Row 1: Contract ID & Type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contract ID *
              </label>
              <input
                type="text"
                value={formData.contractId}
                onChange={(e) => handleChange('contractId', e.target.value)}
                onBlur={() => handleBlur('contractId')}
                placeholder="e.g., CNT-2024-001"
                className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  touched.contractId && errors.contractId
                    ? 'border-red-500'
                    : 'border-gray-300'
                }`}
              />
              {touched.contractId && errors.contractId && (
                <p className="text-red-500 text-xs mt-1">{errors.contractId}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contract Type *
              </label>
              <select
                value={formData.type}
                onChange={(e) => handleChange('type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a type</option>
                {contractTypeOptions.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Contract Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Contract Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              onBlur={() => handleBlur('name')}
              placeholder="e.g., Software License Agreement"
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                touched.name && errors.name ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {touched.name && errors.name && (
              <p className="text-red-500 text-xs mt-1">{errors.name}</p>
            )}
          </div>

          {/* Row 3: Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description || ''}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Add details about this contract..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Row 4: Total Value & Currency */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Total Value *
              </label>
              <div className="flex items-center gap-2">
                <span className="text-gray-600">$</span>
                <input
                  type="number"
                  value={formData.totalValue}
                  onChange={(e) => handleChange('totalValue', parseFloat(e.target.value) || 0)}
                  onBlur={() => handleBlur('totalValue')}
                  placeholder="0"
                  min="0"
                  step="1000"
                  className={`flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    touched.totalValue && errors.totalValue
                      ? 'border-red-500'
                      : 'border-gray-300'
                  }`}
                />
              </div>
              {touched.totalValue && errors.totalValue && (
                <p className="text-red-500 text-xs mt-1">{errors.totalValue}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Currency
              </label>
              <select
                value={formData.currency}
                onChange={(e) => handleChange('currency', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="CAD">CAD</option>
              </select>
            </div>
          </div>

          {/* Row 5: Start & Expiration Dates */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Start Date *
              </label>
              <input
                type="date"
                value={formData.startDate instanceof Date
                  ? formData.startDate.toISOString().split('T')[0]
                  : formData.startDate}
                onChange={(e) => handleChange('startDate', new Date(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Expiration Date *
              </label>
              <input
                type="date"
                value={formData.expirationDate instanceof Date
                  ? formData.expirationDate.toISOString().split('T')[0]
                  : formData.expirationDate}
                onChange={(e) => handleChange('expirationDate', new Date(e.target.value))}
                onBlur={() => handleBlur('expirationDate')}
                className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  touched.expirationDate && errors.expirationDate
                    ? 'border-red-500'
                    : 'border-gray-300'
                }`}
              />
              {touched.expirationDate && errors.expirationDate && (
                <p className="text-red-500 text-xs mt-1">{errors.expirationDate}</p>
              )}
            </div>
          </div>

          {/* Row 6: Renewal Options */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="renewalOption"
                checked={formData.renewalOption || false}
                onChange={(e) => handleChange('renewalOption', e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="renewalOption" className="text-sm font-medium text-gray-700">
                Has Renewal Option
              </label>
            </div>

            {formData.renewalOption && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">
                    Renewal Term (Months)
                  </label>
                  <input
                    type="number"
                    value={formData.renewalTermMonths || 12}
                    onChange={(e) => handleChange('renewalTermMonths', parseInt(e.target.value) || 12)}
                    min="1"
                    max="60"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>

                <div className="flex items-end">
                  <input
                    type="checkbox"
                    id="autoRenew"
                    checked={formData.autoRenew || false}
                    onChange={(e) => handleChange('autoRenew', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="autoRenew" className="text-sm font-medium text-gray-700 ml-2">
                    Auto-Renew
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Row 7: Key Contacts */}
          {contacts.length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Account Manager
                </label>
                <select
                  value={formData.accountManager || ''}
                  onChange={(e) => handleChange('accountManager', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select contact</option>
                  {contacts.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.firstName} {c.lastName}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Technical Lead
                </label>
                <select
                  value={formData.technicalLead || ''}
                  onChange={(e) => handleChange('technicalLead', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select contact</option>
                  {contacts.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.firstName} {c.lastName}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Row 8: Notes & Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes
            </label>
            <textarea
              value={formData.notes || ''}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder="Internal notes about this contract..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isValid || isSubmitting || isLoading}
              className={`px-4 py-2 rounded-lg text-white font-medium flex items-center gap-2 transition ${
                !isValid || isSubmitting || isLoading
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Plus size={18} />
                  {contract ? 'Update Contract' : 'Create Contract'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ContractModal;
