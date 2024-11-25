import requests
import xml.etree.ElementTree as ET
import datetime
import socket
import asyncio

# Aircraft types mapping
AIRCRAFT_TYPES = {
    'military': 'a-n-A-M-F',  # Military aircraft
    'nato': 'a-n-A-N-F',      # NATO aircraft
    'civilian': 'a-f-A-M-F',  # Civilian fixed-wing aircraft
    'unknown': 'a-x-A-M-F',   # Unknown type
}

# ICAO prefix mapping for country classification
ICAO_PREFIXES = {
    'AF': 'military',  # Afghanistan (example for military)
    'US': 'military',  # United States (military)
    'UK': 'nato',      # United Kingdom (NATO)
    'FR': 'nato',      # France (NATO)
    # Add more prefixes as needed
}


class ADSBToCoTConverter:
    def __init__(self, cot_host, cot_port, protocol='tcp', include_types=None, exclude_types=None):
        self.cot_host = cot_host
        self.cot_port = cot_port
        self.protocol = protocol.lower()
        self.include_types = include_types
        self.exclude_types = exclude_types
        self.socket = None

        if self.protocol == 'tcp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.cot_host, self.cot_port))
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def get_aircraft_type(self, callsign, icao24):
        """Determine aircraft type based on callsign and ICAO24 prefix."""
        callsign = callsign.strip() if callsign else ""
        icao_prefix = icao24[:2].upper() if icao24 else ""

        # Classify based on callsign patterns
        if callsign.startswith('MIL') or 'FORCE' in callsign.upper():
            return AIRCRAFT_TYPES['military']
        if 'NATO' in callsign.upper():
            return AIRCRAFT_TYPES['nato']

        # Classify based on ICAO prefix
        if icao_prefix in ICAO_PREFIXES:
            return AIRCRAFT_TYPES[ICAO_PREFIXES[icao_prefix]]

        # Default to civilian if no other matches
        return AIRCRAFT_TYPES['civilian']

    def should_process_aircraft(self, cot_type):
        """Filter aircraft based on user preferences."""
        if self.include_types:
            return cot_type in self.include_types
        elif self.exclude_types:
            return cot_type not in self.exclude_types
        return True

    def create_cot_from_adsb(self, aircraft_data):
        """Convert ADS-B data to CoT XML format."""
        icao24 = aircraft_data.get('icao24', 'UNKNOWN')
        callsign = aircraft_data.get('callsign', 'UNKNOWN').strip()
        lat = aircraft_data.get('latitude')
        lon = aircraft_data.get('longitude')
        alt = aircraft_data.get('geoaltitude', 0)
        speed = aircraft_data.get('velocity', 0)
        heading = aircraft_data.get('heading', 0)

        cot_type = self.get_aircraft_type(callsign, icao24)

        # Filter based on type
        if not self.should_process_aircraft(cot_type):
            return None

        # Create CoT XML
        event = ET.Element('event')
        event.set('version', '2.0')
        event.set('type', cot_type)
        event.set('uid', f"ADSB.{icao24}")
        event.set('time', datetime.datetime.utcnow().isoformat() + 'Z')
        event.set('start', datetime.datetime.utcnow().isoformat() + 'Z')
        event.set('stale', (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).isoformat() + 'Z')
        event.set('how', 'h-e')  # Electronic tracking

        # Point data
        point = ET.SubElement(event, 'point')
        point.set('lat', str(lat if lat else 0))
        point.set('lon', str(lon if lon else 0))
        point.set('hae', str(alt if alt else 0))
        point.set('ce', '100')  # Circular error
        point.set('le', '100')  # Linear error

        # Detail data
        detail = ET.SubElement(event, 'detail')
        track = ET.SubElement(detail, 'track')
        track.set('course', str(heading))
        track.set('speed', str(speed))

        contact = ET.SubElement(detail, 'contact')
        contact.set('callsign', callsign)

        remarks = ET.SubElement(detail, 'remarks')
        remarks.text = f"ICAO24: {icao24}, Callsign: {callsign}"

        return ET.tostring(event, encoding='unicode')

    async def fetch_adsb_data(self):
        """Fetch ADS-B data from OpenSky API."""
        url = "https://opensky-network.org/api/states/all"
        response = requests.get(url)

        if response.status_code == 200:
            return response.json().get('states', [])
        else:
            print(f"Failed to fetch ADS-B data: {response.status_code}")
            return []

    async def connect_and_process(self):
        """Fetch ADS-B data and forward as CoT messages."""
        while True:
            try:
                adsb_data = await self.fetch_adsb_data()
                for aircraft in adsb_data:
                    # Map OpenSky data to a dictionary
                    aircraft_dict = {
                        'icao24': aircraft[0],
                        'callsign': aircraft[1],
                        'latitude': aircraft[6],
                        'longitude': aircraft[5],
                        'geoaltitude': aircraft[7],
                        'velocity': aircraft[9],
                        'heading': aircraft[10],
                    }

                    cot_message = self.create_cot_from_adsb(aircraft_dict)
                    if cot_message:
                        if self.protocol == 'tcp':
                            self.socket.send(cot_message.encode() + b'\n')
                        else:
                            self.socket.sendto(cot_message.encode(), 
                                               (self.cot_host, self.cot_port))

                await asyncio.sleep(10)  # Fetch data every 10 seconds
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

    def run(self):
        """Run the converter."""
        asyncio.get_event_loop().run_until_complete(self.connect_and_process())


def main():
    print("\n=== ADS-B to CoT Converter ===\n")

    ip = input("Enter destination IP address: ").strip()
    port = int(input("Enter destination port: ").strip())
    protocol = input("Enter protocol (tcp/udp) [default: tcp]: ").strip().lower() or 'tcp'

    print("\nPress Ctrl+C to stop the converter.\n")

    converter = ADSBToCoTConverter(ip, port, protocol)
    try:
        converter.run()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
