import websockets
import asyncio
import json
import datetime
import xml.etree.ElementTree as ET
from typing import Dict, Any

# Your AISstream.io API key
API_KEY = "7b46c01db14030f0dde8697dbba85f448e58efd8"

async def test_ais_stream():
    """Test AIS stream and show raw data"""
    url = "wss://stream.aisstream.io/v0/stream"
    
    subscription_message = {
        "APIKey": API_KEY,
        "BoundingBoxes": [[[-180, -90], [180, 90]]]  # Whole world
    }

    while True:
        try:
            async with websockets.connect(url) as websocket:
                await websocket.send(json.dumps(subscription_message))
                print("Connected to AISstream")
                
                message_count = 0
                while True:
                    message = await websocket.recv()
                    ais_data = json.loads(message)
                    
                    # Only process position updates
                    if ais_data.get('MessageType') == 'PositionReport':
                        message_count += 1
                        
                        # Extract data from the correct locations
                        metadata = ais_data.get('MetaData', {})
                        position_report = ais_data.get('Message', {}).get('PositionReport', {})
                        
                        mmsi = metadata.get('MMSI')
                        ship_name = metadata.get('ShipName', '').strip()
                        lat = position_report.get('Latitude')
                        lon = position_report.get('Longitude')
                        course = position_report.get('TrueHeading')
                        speed = position_report.get('Sog')  # Speed over ground
                        
                        print("\n=== Raw JSON ===")
                        print(json.dumps(ais_data, indent=2))
                        
                        print("\n=== Parsed Data ===")
                        print(f"Message #{message_count}")
                        print(f"Message Type: {ais_data.get('MessageType')}")
                        print(f"MMSI: {mmsi}")
                        print(f"Ship Name: {ship_name}")
                        print(f"Position: {lat}, {lon}")
                        print(f"Course: {course}")
                        print(f"Speed: {speed} knots")
                        
                        # Create and show CoT message
                        event = ET.Element('event')
                        event.set('version', '2.0')
                        event.set('type', 'a-f-G-M-N-V')
                        event.set('uid', f"AIS.{mmsi if mmsi else 'UNKNOWN'}")
                        event.set('time', datetime.datetime.utcnow().isoformat() + 'Z')
                        event.set('start', datetime.datetime.utcnow().isoformat() + 'Z')
                        event.set('stale', (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat() + 'Z')
                        event.set('how', 'h-e')

                        point = ET.SubElement(event, 'point')
                        point.set('lat', str(lat if lat is not None else 0))
                        point.set('lon', str(lon if lon is not None else 0))
                        point.set('hae', '0')
                        point.set('ce', '10')
                        point.set('le', '10')

                        detail = ET.SubElement(event, 'detail')
                        track = ET.SubElement(detail, 'track')
                        track.set('course', str(course if course is not None and course != 511 else 0))
                        track.set('speed', str(speed * 0.514444 if speed is not None else 0))
                        
                        contact = ET.SubElement(detail, 'contact')
                        contact.set('callsign', ship_name if ship_name else 'UNKNOWN')
                        
                        remarks = ET.SubElement(detail, 'remarks')
                        remarks.text = f"MMSI: {mmsi if mmsi else 'UNKNOWN'}, Vessel: {ship_name if ship_name else 'UNKNOWN'}"

                        cot_message = ET.tostring(event, encoding='unicode')
                        
                        print("\n=== Generated CoT Message ===")
                        print(cot_message)
                        print("\n" + "="*50)
                        
                        # Only show first 5 messages then ask to continue
                        if message_count % 5 == 0:
                            response = input("\nPress Enter to continue (or 'q' to quit): ")
                            if response.lower() == 'q':
                                return

        except websockets.exceptions.ConnectionClosed:
            print("Connection lost. Reconnecting...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)

def main():
    print("\n=== AIS Stream Test ===\n")
    print("This script will show raw AIS messages and their corresponding CoT format")
    print("Press Ctrl+C to stop at any time\n")
    
    try:
        asyncio.get_event_loop().run_until_complete(test_ais_stream())
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()