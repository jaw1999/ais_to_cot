# AIS to CoT Converter

This tool converts AIS (Automatic Identification System) vessel data to Cursor on Target (CoT) format in real-time. It connects to the AISstream.io service to receive vessel positions and information, converts them to CoT format, and forwards them to a specified destination.

## Features

- Real-time AIS data conversion to CoT
- Support for both TCP and UDP forwarding
- Vessel type differentiation with distinct icons:
  - US Military vessels
  - NATO/Allied military vessels
  - Law Enforcement vessels
  - Fishing vessels
  - Passenger vessels
  - Cargo vessels
  - Tankers
  - High-speed craft
  - Other civilian vessels
- Filtering options to include/exclude specific vessel types
- Automatic reconnection on connection loss
- Proper handling of vessel metadata and position information

## Requirements

```
python >= 3.7
websockets
asyncio
```

Install requirements using:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Edit the `API_KEY` variable in `ais_to_cot.py` with your AISstream.io API key
2. (Optional) Modify the military MMSI prefixes in the `military_prefixes` dictionary

## Usage

1. Activate the virtual environment:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the script:
```bash
python ais_to_cot.py
```

3. Follow the prompts to enter:
   - Destination IP address
   - Destination port
   - Protocol (TCP/UDP)
   - Vessel types to include/exclude

## Vessel Type Filters

Available vessel type filters:
- `mil-us` : US Military vessels
- `mil-nato` : NATO/Allied military vessels
- `law` : Law Enforcement vessels
- `fishing` : Fishing vessels
- `passenger` : Passenger vessels
- `cargo` : Cargo vessels
- `tanker` : Tankers
- `highspeed` : High-speed craft
- `other` : Other civilian vessels

Example filter combinations:
- Show all vessels: Enter 'all' when prompted for inclusion
- Military only: `mil-us,mil-nato`
- Commercial only: `cargo,tanker,passenger`
- Everything except passenger ships: Use 'all' for include and `passenger` for exclude

## CoT Types Used

| Vessel Category | CoT Type | Description |
|----------------|----------|-------------|
| US Military | a-n-G-U-C-F | US Navy vessels |
| NATO Military | a-n-G-E-V-A | Allied military vessels |
| Law Enforcement | a-f-G-U-L-E | Coast Guard/Police vessels |
| Fishing | a-f-G-E-V-F | Commercial fishing vessels |
| Passenger | a-f-G-E-V-P | Passenger ships/ferries |
| Cargo | a-f-G-E-V-C | Cargo ships |
| Tanker | a-f-G-E-V-T | Tanker vessels |
| High-speed | a-f-G-E-V-H | High-speed craft |
| Other | a-f-G-E-V | Generic civilian vessels |

## Notes

- Military vessel detection is based on MMSI prefixes and AIS ship type codes
- Some military vessels may not broadcast AIS or may use civilian identifiers
- AIS data quality depends on vessels properly configuring and broadcasting their information
- The script automatically reconnects if the connection to AISstream.io is lost

## Error Handling

The script includes error handling for:
- Invalid IP addresses
- Invalid port numbers
- Connection losses
- Invalid AIS messages
- Socket errors
