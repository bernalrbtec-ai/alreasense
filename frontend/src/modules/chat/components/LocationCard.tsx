/**
 * Card para exibir mensagens de localização compartilhada
 * Exibe nome/endereço e link para abrir no Google Maps
 */
import React from 'react';
import { MapPin, ExternalLink } from 'lucide-react';

interface LocationCardProps {
  locationData: {
    latitude?: number;
    longitude?: number;
    name?: string;
    address?: string;
  };
  content?: string;
}

export function LocationCard({ locationData, content }: LocationCardProps) {
  const lat = locationData?.latitude;
  const lng = locationData?.longitude;
  const name = locationData?.name || '';
  const address = locationData?.address || '';

  const hasCoords = typeof lat === 'number' && typeof lng === 'number';
  const displayName = name || address || 'Localização compartilhada';
  const mapUrl = hasCoords
    ? `https://www.google.com/maps?q=${lat},${lng}`
    : address
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`
      : null;

  return (
    <div className="mb-2 border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start gap-3 p-3">
        <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-green-100 to-green-200 dark:from-green-900/30 dark:to-green-800/30 flex items-center justify-center">
          <MapPin className="w-6 h-6 text-green-600 dark:text-green-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">
            📍 Localização
          </div>
          <div className="font-medium text-gray-900 dark:text-gray-100 mb-1 line-clamp-2">
            {displayName}
          </div>
          {address && name && address !== name && (
            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-2">
              {address}
            </p>
          )}
          {mapUrl && (
            <a
              href={mapUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Abrir no Google Maps
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
