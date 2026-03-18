const numberFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const decimalFormatter = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const compactNumberFormatter = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

export const formatNumber = (value: number): string => numberFormatter.format(Math.round(value));

export const formatFractional = (value: number): string => {
  return decimalFormatter.format(value);
};

export const formatCompactNumber = (value: number): string => {
  return compactNumberFormatter.format(value);
};

export const formatPercent = (value: number): string => {
  return `${decimalFormatter.format(value * 100)}%`;
};

export const formatDelta = (value: number): string => {
  const sign = value > 0 ? '+' : value < 0 ? '' : '';
  return `${sign}${value}`;
};

export const formatCompactDate = (isoDate: string): string => {
  const date = new Date(isoDate);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
};

export const formatVelocity = (value: number): string => {
  return `${decimalFormatter.format(value * 100)} pts`;
};

export const chartAxisLabel = (value: string | number): string => {
  if (typeof value === 'number') {
    return numberFormatter.format(value);
  }
  return value;
};

// In production these helpers would wrap live Spotify/Cannabliss data before rendering.
