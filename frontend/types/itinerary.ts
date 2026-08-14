export interface Location {
  lat: number;
  lng: number;
}

export interface TransitInfo {
  commute_mins?: number;
  step_by_step?: string;
  [key: string]: any;
}

export interface ItineraryStop {
  id?: string;
  name?: string;
  venue_name?: string; // For compatibility with backend response
  location?: Location;
  lat?: number;
  lng?: number;
  address?: string;
  description?: string;
  why_go?: string;
  time?: string;
  start_time?: string;
  end_time?: string;
  stay_duration_mins?: number;
  category?: string;
  transit_to_next?: TransitInfo;
  [key: string]: any; // Allows flexible extension
}

export interface ItineraryData {
  title?: string;
  summary?: string;
  start_location?: string;
  start_time?: string;
  initial_transit?: TransitInfo;
  stops: ItineraryStop[];
  [key: string]: any;
}