import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudMoon,
  CloudRain,
  CloudSnow,
  CloudSun,
  Moon,
  Snowflake,
  Sun,
  type LucideIcon,
} from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  clearsky: Sun,
  clearsky_day: Sun,
  clearsky_night: Moon,
  clearsky_polartwilight: Sun,
  fair: CloudSun,
  fair_day: CloudSun,
  fair_night: CloudMoon,
  fair_polartwilight: CloudSun,
  partlycloudy: CloudSun,
  partlycloudy_day: CloudSun,
  partlycloudy_night: CloudMoon,
  partlycloudy_polartwilight: CloudSun,
  cloudy: Cloud,
  fog: CloudFog,
  rain: CloudRain,
  lightrain: CloudDrizzle,
  heavyrain: CloudRain,
  rainshowers: CloudDrizzle,
  lightrainshowers: CloudDrizzle,
  heavyrainshowers: CloudRain,
  sleet: CloudSnow,
  lightsleet: CloudSnow,
  heavysleet: CloudSnow,
  sleetshowers: CloudSnow,
  lightsleetshowers: CloudSnow,
  heavysleetshowers: CloudSnow,
  snow: Snowflake,
  lightsnow: CloudSnow,
  heavysnow: Snowflake,
  snowshowers: CloudSnow,
  lightsnowshowers: CloudSnow,
  heavysnowshowers: Snowflake,
}

export function weatherIcon(symbolCode: string | null | undefined): LucideIcon {
  if (!symbolCode) return Cloud
  if (ICONS[symbolCode]) return ICONS[symbolCode]
  const base = symbolCode.replace(/_day$|_night$|_polartwilight$/, '')
  if (base.includes('thunder')) return CloudLightning
  if (base.includes('fog')) return CloudFog
  if (base.includes('snow')) return base.includes('heavy') ? Snowflake : CloudSnow
  if (base.includes('sleet')) return CloudSnow
  if (base.includes('rain')) return base.includes('light') || base.includes('shower') ? CloudDrizzle : CloudRain
  if (ICONS[base]) return ICONS[base]
  return Cloud
}

export function weatherIconLabel(symbolCode: string | null | undefined) {
  if (!symbolCode) return 'Oblacno'
  const base = symbolCode.replace(/_day$|_night$|_polartwilight$/, '')
  if (base.includes('thunder')) return 'Grmljavina'
  if (base.includes('snow')) return 'Sneg'
  if (base.includes('sleet')) return 'Sušnežica'
  if (base.includes('rain')) return 'Kiša'
  if (base.includes('fog')) return 'Magla'
  if (base === 'cloudy') return 'Oblačno'
  if (base === 'partlycloudy' || base === 'fair') return 'Delimično oblačno'
  if (base === 'clearsky') return 'Vedro'
  return 'Prognoza'
}
