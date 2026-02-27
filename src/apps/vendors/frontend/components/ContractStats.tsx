/**
 * Vendor 360 - Contract Statistics Card Component
 * 
 * Displays key contract metrics with reactive calculations
 */

import React from 'react';
import { TrendingUp, DollarSign, AlertCircle, CheckCircle } from 'lucide-react';
import { ContractStatistics } from '../types/contracts';
import { formatCurrency } from '../utils/contractUtils';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  subtitle?: string;
  trend?: { direction: 'up' | 'down'; percent: number };
  color: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  onClick?: () => void;
  isLoading?: boolean;
}

/**
 * Individual stat card - reusable component
 */
const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  subtitle,
  trend,
  color,
  onClick,
  isLoading = false
}) => {
  const colorStyles = {
    blue: 'from-blue-50 to-blue-100 border-blue-200',
    green: 'from-green-50 to-green-100 border-green-200',
    amber: 'from-amber-50 to-amber-100 border-amber-200',
    red: 'from-red-50 to-red-100 border-red-200',
    purple: 'from-purple-50 to-purple-100 border-purple-200'
  };

  const iconColorStyles = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    amber: 'bg-amber-100 text-amber-600',
    red: 'bg-red-100 text-red-600',
    purple: 'bg-purple-100 text-purple-600'
  };

  return (
    <div
      onClick={onClick}
      className={`bg-gradient-to-br ${colorStyles[color]} border rounded-lg p-6 transition-all hover:shadow-md cursor-pointer`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-gray-600 text-sm font-medium">{title}</p>
          <h3 className={`text-3xl font-bold text-gray-900 mt-2 ${isLoading ? 'opacity-50' : ''}`}>
            {isLoading ? '...' : value}
          </h3>
          {subtitle && <p className="text-gray-700 text-xs mt-1">{subtitle}</p>}
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-xs font-semibold ${
              trend.direction === 'up' ? 'text-green-600' : 'text-red-600'
            }`}>
              <TrendingUp size={14} className={trend.direction === 'down' ? 'rotate-180' : ''} />
              {trend.percent}% {trend.direction === 'up' ? 'increase' : 'decrease'}
            </div>
          )}
        </div>
        <div className={`${iconColorStyles[color]} p-3 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  );
};

interface ContractStatsProps {
  stats: ContractStatistics;
  onCardClick?: (cardType: 'total' | 'active' | 'expiring' | 'value') => void;
  isLoading?: boolean;
}

/**
 * Contract Statistics Dashboard - displays all key metrics
 */
export const ContractStats: React.FC<ContractStatsProps> = ({
  stats,
  onCardClick,
  isLoading = false
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <StatCard
        title="Total Contracts"
        value={stats.totalCount}
        icon={<DollarSign size={24} />}
        color="blue"
        subtitle={`Avg value: ${formatCurrency(stats.averageValue)}`}
        onClick={() => onCardClick?.('total')}
        isLoading={isLoading}
      />

      <StatCard
        title="Active Contracts"
        value={stats.activeCount}
        icon={<CheckCircle size={24} />}
        color="green"
        subtitle={`Worth: ${formatCurrency(stats.activeValue)}`}
        onClick={() => onCardClick?.('active')}
        isLoading={isLoading}
      />

      <StatCard
        title="Expiring Soon"
        value={stats.expiringCount}
        icon={<AlertCircle size={24} />}
        color="amber"
        subtitle={`Worth: ${formatCurrency(stats.expiringValue)}`}
        onClick={() => onCardClick?.('expiring')}
        isLoading={isLoading}
      />

      <StatCard
        title="Total Contract Value"
        value={formatCurrency(stats.totalValue)}
        icon={<TrendingUp size={24} />}
        color="purple"
        subtitle={`Avg term: ${stats.averageTermMonths} months`}
        onClick={() => onCardClick?.('value')}
        isLoading={isLoading}
      />
    </div>
  );
};

/**
 * Compact stats for sidebar or widget display
 */
export const CompactContractStats: React.FC<{ stats: ContractStatistics }> = ({ stats }) => {
  return (
    <div className="bg-white rounded-lg p-4 border border-gray-200 space-y-3">
      <h4 className="font-semibold text-gray-900 text-sm">Contract Overview</h4>

      <div className="space-y-2">
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-600">Total Contracts</span>
          <span className="font-semibold text-gray-900">{stats.totalCount}</span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-600">Active</span>
          <span className="font-semibold text-green-600">{stats.activeCount}</span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-600">Expiring Soon</span>
          <span className="font-semibold text-amber-600">{stats.expiringCount}</span>
        </div>
        <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between items-center text-sm">
          <span className="text-gray-600 font-semibold">Total Value</span>
          <span className="font-bold text-gray-900">{formatCurrency(stats.totalValue)}</span>
        </div>
      </div>
    </div>
  );
};

export default ContractStats;
