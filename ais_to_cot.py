import websockets
import asyncio
import json
import socket
import datetime
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Set

# Your AISstream.io API key
API_KEY = "API KEY"

class AISToCoTConverter:
    def __init__(self, cot_host: str, cot_port: int, protocol: str = 'tcp', include_types: Set[str] = None, exclude_types: Set[str] = None):
        self.api_key = API_KEY
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

    def get_vessel_type(self, mmsi: str, ship_type: int = None) -> str:
        """Determine vessel type and return appropriate CoT type string"""
        mmsi_str = str(mmsi) if mmsi else ''
        
        # Military prefixes
        military_prefixes = {
            '338': 'us',    # US military
            '339': 'us',    # US military
            '244': 'nato',  # Netherlands military
            '235': 'nato',  # UK military
            '250': 'nato',  # France military
        }

        # Check for military vessels first
        for prefix, military_type in military_prefixes.items():
            if mmsi_str.startswith(prefix):
                return f'a-n-G-U-C-F' if military_type == 'us' else 'a-n-G-E-V-A'  # US Navy or NATO

        # If ship_type is provided, categorize based on AIS type codes
        if ship_type:
            if ship_type == 35:
                return 'a-n-G-U-C-F'  # Military operations
            elif ship_type in [51, 55]:
                return 'a-f-G-U-L-E'  # Law Enforcement
            elif ship_type in range(30, 38):
                return 'a-f-G-E-V-F'  # Fishing vessels
            elif ship_type in range(60, 70):
                return 'a-f-G-E-V-P'  # Passenger vessels
            elif ship_type in range(70, 80):
                return 'a-f-G-E-V-C'  # Cargo vessels
            elif ship_type in range(80, 90):
                return 'a-f-G-E-V-T'  # Tankers
            elif ship_type == 40:
                return 'a-f-G-E-V-H'  # High speed craft
            
        # Default to generic commercial vessel
        return 'a-f-G-E-V'

    def should_process_vessel(self, cot_type: str) -> bool:
        """Determine if vessel should be processed based on filters"""
        if self.include_types:
            return cot_type in self.include_types
        elif self.exclude_types:
            return cot_type not in self.exclude_types
        return True

    def create_cot_from_ais(self, ais_data: Dict[str, Any]) -> str:
        """Convert AIS message to CoT XML format"""
        # Extract data from the correct locations
        metadata = ais_data.get('MetaData', {})
        position_report = ais_data.get('Message', {}).get('PositionReport', {})
        
        # Extract all needed fields
        mmsi = metadata.get('MMSI')
        ship_name = metadata.get('ShipName', '').strip()
        lat = position_report.get('Latitude')
        lon = position_report.get('Longitude')
        course = position_report.get('TrueHeading')
        speed = position_report.get('Sog')  # Speed over ground
        
        # Get ship type from static data if available
        ship_type = ais_data.get('Message', {}).get('StaticData', {}).get('Type')
        
        # Determine vessel type for CoT
        cot_type = self.get_vessel_type(mmsi, ship_type)
        
        # Check if we should process this vessel type
        if not self.should_process_vessel(cot_type):
            return None
        
        # Create CoT XML
        event = ET.Element('event')
        event.set('version', '2.0')
        event.set('type', cot_type)
        event.set('uid', f"AIS.{mmsi if mmsi else 'UNKNOWN'}")
        event.set('time', datetime.datetime.utcnow().isoformat() + 'Z')
        event.set('start', datetime.datetime.utcnow().isoformat() + 'Z')
        event.set('stale', (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat() + 'Z')
        event.set('how', 'h-e') # AIS electronic tracking

        # Point data
        point = ET.SubElement(event, 'point')
        point.set('lat', str(lat if lat is not None else 0))
        point.set('lon', str(lon if lon is not None else 0))
        point.set('hae', '0') # Height above ellipsoid
        point.set('ce', '10') # Circular error
        point.set('le', '10') # Linear error

        # Detail data
        detail = ET.SubElement(event, 'detail')
        track = ET.SubElement(detail, 'track')
        track.set('course', str(course if course is not None and course != 511 else 0))
        track.set('speed', str(speed * 0.514444 if speed is not None else 0))
        
        contact = ET.SubElement(detail, 'contact')
        contact.set('callsign', ship_name if ship_name else 'UNKNOWN')
        
        # Add vessel type to remarks if available
        remarks = ET.SubElement(detail, 'remarks')
        type_str = f", Type: {ship_type}" if ship_type else ""
        remarks.text = f"MMSI: {mmsi if mmsi else 'UNKNOWN'}, Vessel: {ship_name if ship_name else 'UNKNOWN'}{type_str}"

        return ET.tostring(event, encoding='unicode')

    async def connect_and_process(self):
        """Connect to AISstream and process messages"""
        url = "wss://stream.aisstream.io/v0/stream"
        
        subscription_message = {
            "APIKey": self.api_key,
            "BoundingBoxes": [[[-180, -90], [180, 90]]]  # Whole world
        }

        while True:
            try:
                async with websockets.connect(url) as websocket:
                    await websocket.send(json.dumps(subscription_message))
                    print(f"Connected to AISstream and forwarding to {self.cot_host}:{self.cot_port} via {self.protocol.upper()}")

                    while True:
                        message = await websocket.recv()
                        ais_data = json.loads(message)
                        
                        # Process both position reports and static data
                        if ais_data.get('MessageType') in ['PositionReport', 'StaticData']:
                            cot_message = self.create_cot_from_ais(ais_data)
                            
                            # Only send if message was created (not filtered out)
                            if cot_message:
                                if self.protocol == 'tcp':
                                    self.socket.send(cot_message.encode() + b'\n')
                                else:
                                    self.socket.sendto(cot_message.encode(), 
                                                     (self.cot_host, self.cot_port))

            except websockets.exceptions.ConnectionClosed:
                print("Connection lost. Reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

    def run(self):
        """Run the converter"""
        asyncio.get_event_loop().run_until_complete(self.connect_and_process())

def get_valid_ip():
    while True:
        ip = input("Enter destination IP address: ").strip()
        try:
            # Try to validate IP format
            socket.inet_aton(ip)
            return ip
        except socket.error:
            print("Invalid IP address format. Please try again.")

def get_valid_port():
    while True:
        try:
            port = int(input("Enter destination port: ").strip())
            if 1 <= port <= 65535:
                return port
            print("Port must be between 1 and 65535. Please try again.")
        except ValueError:
            print("Invalid port number. Please enter a number between 1 and 65535.")

def get_protocol():
    while True:
        protocol = input("Enter protocol (tcp/udp) [default: tcp]: ").strip().lower()
        if protocol == "":
            return "tcp"
        if protocol in ['tcp', 'udp']:
            return protocol
        print("Invalid protocol. Please enter 'tcp' or 'udp'.")

VESSEL_TYPES = {
    'mil-us': 'a-n-G-U-C-F',     # US Military vessels
    'mil-nato': 'a-n-G-E-V-A',   # NATO/Allied military vessels
    'law': 'a-f-G-U-L-E',        # Law Enforcement vessels
    'fishing': 'a-f-G-E-V-F',    # Fishing vessels
    'passenger': 'a-f-G-E-V-P',  # Passenger vessels
    'cargo': 'a-f-G-E-V-C',      # Cargo vessels
    'tanker': 'a-f-G-E-V-T',     # Tankers
    'highspeed': 'a-f-G-E-V-H',  # High-speed craft
    'other': 'a-f-G-E-V',        # Other civilian vessels
}

def get_vessel_filters():
    """Get vessel type filters from user"""
    print("\nVessel type filters:")
    print("Available types:")
    for key, value in VESSEL_TYPES.items():
        print(f"  {key:<10} : {value}")
    
    while True:
        include = input("\nEnter vessel types to include (comma-separated, or 'all'): ").strip().lower()
        if include == 'all':
            return set(), set()
        
        include_types = {VESSEL_TYPES[t.strip()] for t in include.split(',') if t.strip() in VESSEL_TYPES}
        
        if include_types or include == "":
            break
        print("Invalid vessel types. Please try again.")
    
    while True:
        exclude = input("Enter vessel types to exclude (comma-separated, or none): ").strip().lower()
        if exclude == "":
            return include_types, set()
        
        exclude_types = {VESSEL_TYPES[t.strip()] for t in exclude.split(',') if t.strip() in VESSEL_TYPES}
        
        if exclude_types:
            break
        print("Invalid vessel types. Please try again.")
    
    return include_types, exclude_types

def main():
    print("\n=== AIS to CoT Converter ===\n")
    
    # Get connection details from user
    ip = get_valid_ip()
    port = get_valid_port()
    protocol = get_protocol()
    
    # Get vessel type filters
    include_types, exclude_types = get_vessel_filters()
    
    print(f"\nStarting converter with the following settings:")
    print(f"Destination: {ip}:{port}")
    print(f"Protocol: {protocol.upper()}")
    if include_types:
        print("Including only:", include_types)
    if exclude_types:
        print("Excluding:", exclude_types)
    print("\nPress Ctrl+C to stop the converter.\n")

    converter = AISToCoTConverter(ip, port, protocol, include_types, exclude_types)
    try:
        converter.run()
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
