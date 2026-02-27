/**
 * Vendor 360 - Key Contacts Directory Component
 * 
 * Displays Account Manager and Technical Lead with contact information
 */

import React from 'react';
import { Mail, Phone, User, Edit2, Phone as PhoneIcon } from 'lucide-react';
import { Contact, ContactRole } from '../types/contracts';

interface KeyContactsProps {
  contacts: Contact[];
  onEdit?: (contact: Contact) => void;
  isLoading?: boolean;
  showActions?: boolean;
}

/**
 * Individual contact card component
 */
interface ContactCardProps {
  contact: Contact;
  role: string;
  onEdit?: () => void;
  showActions?: boolean;
}

const ContactCard: React.FC<ContactCardProps> = ({ contact, role, onEdit, showActions = true }) => {
  const fullName = `${contact.firstName} ${contact.lastName}`;

  return (
    <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg border border-gray-200 p-4 hover:shadow-md transition">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 flex-1">
          <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-semibold">
            {contact.firstName[0]}{contact.lastName[0]}
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">{fullName}</h4>
            <p className="text-xs text-gray-600">{role}</p>
          </div>
        </div>
        {showActions && onEdit && (
          <button
            onClick={onEdit}
            className="text-gray-400 hover:text-blue-600 transition p-1"
            title="Edit contact"
          >
            <Edit2 size={16} />
          </button>
        )}
      </div>

      <div className="space-y-2">
        <a
          href={`mailto:${contact.email}`}
          className="flex items-center gap-2 text-sm text-gray-700 hover:text-blue-600 transition"
        >
          <Mail size={14} className="text-gray-400" />
          <span className="truncate">{contact.email}</span>
        </a>

        {contact.phone && (
          <a
            href={`tel:${contact.phone}`}
            className="flex items-center gap-2 text-sm text-gray-700 hover:text-blue-600 transition"
          >
            <PhoneIcon size={14} className="text-gray-400" />
            <span>{contact.phone}</span>
          </a>
        )}

        {contact.department && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <User size={14} className="text-gray-400" />
            <span>{contact.department}</span>
          </div>
        )}
      </div>

      {contact.isActive === false && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <span className="inline-block px-2 py-1 bg-gray-300 text-gray-700 text-xs rounded font-medium">
            Inactive
          </span>
        </div>
      )}
    </div>
  );
};

/**
 * Key Contacts Directory - displays account manager and technical lead
 */
export const KeyContacts: React.FC<KeyContactsProps> = ({
  contacts,
  onEdit,
  isLoading = false,
  showActions = true
}) => {
  const accountManager = contacts.find(c => c.role === ContactRole.ACCOUNT_MANAGER && c.isActive);
  const technicalLead = contacts.find(c => c.role === ContactRole.TECHNICAL_LEAD && c.isActive);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Key Contacts</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-32 bg-gray-200 animate-pulse rounded-lg" />
          <div className="h-32 bg-gray-200 animate-pulse rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <User size={20} className="text-blue-600" />
        Key Contacts
      </h3>

      {!accountManager && !technicalLead ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <User size={32} className="text-gray-300 mb-2" />
          <p className="text-gray-500 text-sm">No key contacts assigned yet</p>
          <p className="text-gray-400 text-xs mt-1">
            Add Account Manager and Technical Lead in the vendor details
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {accountManager ? (
            <ContactCard
              contact={accountManager}
              role={`${ContactRole.ACCOUNT_MANAGER.replace('_', ' ')}`}
              onEdit={() => onEdit?.(accountManager)}
              showActions={showActions}
            />
          ) : (
            <div className="bg-gray-50 rounded-lg border border-dashed border-gray-300 p-4 flex items-center justify-center h-32">
              <div className="text-center">
                <User size={24} className="text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No Account Manager</p>
              </div>
            </div>
          )}

          {technicalLead ? (
            <ContactCard
              contact={technicalLead}
              role={`${ContactRole.TECHNICAL_LEAD.replace('_', ' ')}`}
              onEdit={() => onEdit?.(technicalLead)}
              showActions={showActions}
            />
          ) : (
            <div className="bg-gray-50 rounded-lg border border-dashed border-gray-300 p-4 flex items-center justify-center h-32">
              <div className="text-center">
                <User size={24} className="text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No Technical Lead</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Compact key contacts for sidebar display
 */
export const CompactKeyContacts: React.FC<{ contacts: Contact[] }> = ({ contacts }) => {
  const accountManager = contacts.find(c => c.role === ContactRole.ACCOUNT_MANAGER && c.isActive);
  const technicalLead = contacts.find(c => c.role === ContactRole.TECHNICAL_LEAD && c.isActive);

  return (
    <div className="bg-white rounded-lg p-3 border border-gray-200 space-y-2">
      <h4 className="font-semibold text-gray-900 text-sm">Key Contacts</h4>

      {accountManager && (
        <div className="space-y-1">
          <p className="text-xs text-gray-600 font-medium">Account Manager</p>
          <p className="text-sm text-gray-900">{accountManager.firstName} {accountManager.lastName}</p>
          <a
            href={`mailto:${accountManager.email}`}
            className="text-xs text-blue-600 hover:underline"
          >
            {accountManager.email}
          </a>
        </div>
      )}

      {technicalLead && accountManager && <hr className="my-2" />}

      {technicalLead && (
        <div className="space-y-1">
          <p className="text-xs text-gray-600 font-medium">Technical Lead</p>
          <p className="text-sm text-gray-900">{technicalLead.firstName} {technicalLead.lastName}</p>
          <a
            href={`mailto:${technicalLead.email}`}
            className="text-xs text-blue-600 hover:underline"
          >
            {technicalLead.email}
          </a>
        </div>
      )}

      {!accountManager && !technicalLead && (
        <p className="text-xs text-gray-500 italic">No contacts assigned</p>
      )}
    </div>
  );
};

/**
 * All Contacts List - view all vendor contacts
 */
interface AllContactsListProps {
  contacts: Contact[];
  onEdit?: (contact: Contact) => void;
  onAdd?: () => void;
  isLoading?: boolean;
}

export const AllContactsList: React.FC<AllContactsListProps> = ({
  contacts,
  onEdit,
  onAdd,
  isLoading = false
}) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">All Contacts</h3>
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-200 animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <User size={20} className="text-blue-600" />
          All Vendor Contacts ({contacts.length})
        </h3>
        {onAdd && (
          <button
            onClick={onAdd}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition"
          >
            Add Contact
          </button>
        )}
      </div>

      {contacts.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-500">No contacts yet</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Name</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Email</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Role</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Department</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
                {onEdit && <th className="px-4 py-3 text-center font-semibold text-gray-700">Action</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {contacts.map(contact => (
                <tr key={contact.id} className="hover:bg-gray-50 transition">
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-900">
                      {contact.firstName} {contact.lastName}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={`mailto:${contact.email}`}
                      className="text-blue-600 hover:underline"
                    >
                      {contact.email}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-gray-700">
                      {contact.role.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-gray-600">
                      {contact.department || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                      contact.isActive
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {contact.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  {onEdit && (
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => onEdit(contact)}
                        className="text-blue-600 hover:text-blue-800 transition"
                        title="Edit contact"
                      >
                        <Edit2 size={16} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default KeyContacts;
