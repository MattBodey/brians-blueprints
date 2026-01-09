#!/usr/bin/env python3

"""
Merge two Factorio blueprints using train-stop entities as merge points.

The main blueprint provides the base structure, and the header blueprint
is merged at train-stop locations. Entity positions and wire connections
are automatically adjusted.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from copy import deepcopy


def parse_position_string(pos_str: str) -> Tuple[float, float]:
    """Parse a position string like '3.5,0.5' into (x, y) tuple."""
    x, y = pos_str.split(',')
    return (float(x), float(y))


def format_position_string(x: float, y: float) -> str:
    """Format x, y coordinates into a position string."""
    # Format to remove unnecessary decimal points
    x_str = str(int(x)) if x == int(x) else str(x)
    y_str = str(int(y)) if y == int(y) else str(y)
    return f"{x_str},{y_str}"


def get_entity_position(entity: Dict) -> Tuple[float, float]:
    """Get the (x, y) position of an entity."""
    pos = entity.get("position", {})
    return (pos.get("x", 0), pos.get("y", 0))


def set_entity_position(entity: Dict, x: float, y: float) -> None:
    """Set the position of an entity."""
    if "position" not in entity:
        entity["position"] = {}
    entity["position"]["x"] = x
    entity["position"]["y"] = y


def find_train_stops(entities: List[Dict]) -> List[Tuple[int, Dict]]:
    """Find all train-stop or logistic-train-stop entities and return their indices and data."""
    train_stops = []
    for idx, entity in enumerate(entities):
        entity_name = entity.get("name")
        if entity_name in ("train-stop", "logistic-train-stop"):
            train_stops.append((idx, entity))
    return train_stops


def adjust_position(x: float, y: float, offset_x: float, offset_y: float) -> Tuple[float, float]:
    """Adjust a position by the given offset."""
    return (x + offset_x, y + offset_y)


def deep_merge_entity_properties(main_entity: Dict, header_entity: Dict) -> Dict:
    """Merge entity properties, preferring header values unless undefined or empty."""
    merged = deepcopy(main_entity)
    
    for key, header_value in header_entity.items():
        # Skip position - that's handled separately
        if key == "position":
            continue
        
        # Use header value if it's not None and not empty string
        if header_value is not None and header_value != "":
            if isinstance(header_value, dict) and key in merged and isinstance(merged[key], dict):
                # Recursively merge dicts
                merged[key] = deep_merge_dict(merged[key], header_value)
            else:
                # Replace with header value
                merged[key] = deepcopy(header_value)
    
    return merged


def deep_merge_dict(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries, preferring override values unless undefined or empty."""
    result = deepcopy(base)
    
    for key, override_value in override.items():
        if override_value is not None and override_value != "":
            if isinstance(override_value, dict) and key in result and isinstance(result[key], dict):
                result[key] = deep_merge_dict(result[key], override_value)
            else:
                result[key] = deepcopy(override_value)
    
    return result


def merge_entities(main_entities: List[Dict], header_entities: List[Dict], 
                   offset_x: float, offset_y: float) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Merge header entities into main entities, adjusting positions.
    
    Returns:
        - Merged entity list
        - Mapping from old header positions to new positions (for entities that were added OR exist in main)
    """
    merged = deepcopy(main_entities)
    position_mapping = {}  # old header pos -> new merged pos
    
    # Build a set of existing positions in main blueprint for duplicate detection
    existing_positions = set()
    main_position_map = {}  # (x, y, name) -> entity for main blueprint
    for entity in main_entities:
        pos = get_entity_position(entity)
        key = (pos[0], pos[1], entity.get("name"))
        existing_positions.add(key)
        main_position_map[key] = entity
    
    # Find train-stop in main blueprint
    main_train_stop_pos = None
    for entity in main_entities:
        if entity.get("name") == "train-stop":
            main_train_stop_pos = get_entity_position(entity)
            break
    
    # Process header entities
    skipped_duplicates = 0
    for entity in header_entities:
        old_x, old_y = get_entity_position(entity)
        old_pos_str = format_position_string(old_x, old_y)
        
        if entity.get("name") == "train-stop":
            # Map train-stop to the main's train-stop position
            if main_train_stop_pos:
                new_pos_str = format_position_string(main_train_stop_pos[0], main_train_stop_pos[1])
                position_mapping[old_pos_str] = new_pos_str
            continue
        
        # Calculate new position
        new_x, new_y = adjust_position(old_x, old_y, offset_x, offset_y)
        new_pos_str = format_position_string(new_x, new_y)
        entity_key = (new_x, new_y, entity.get("name"))
        
        # Check if entity already exists at this position (duplicate)
        # For train-stop/logistic-train-stop, also check cross-type matches
        entity_name = entity.get("name")
        is_train_stop = entity_name in ("train-stop", "logistic-train-stop")
        
        matching_entity = None
        if entity_key in existing_positions:
            matching_entity = main_position_map.get(entity_key)
        elif is_train_stop:
            # Check for cross-type train-stop match
            alternate_name = "logistic-train-stop" if entity_name == "train-stop" else "train-stop"
            alternate_key = (new_x, new_y, alternate_name)
            if alternate_key in existing_positions:
                matching_entity = main_position_map.get(alternate_key)
                entity_key = alternate_key  # Use the alternate key for tracking
        
        if matching_entity:
            # Entity is duplicate - merge properties from header into existing entity
            position_mapping[old_pos_str] = new_pos_str
            skipped_duplicates += 1
            
            # For train-stop/logistic-train-stop cross-type matches, replace entirely
            if is_train_stop and matching_entity.get("name") != entity_name:
                # Replace the train-stop with logistic-train-stop (or vice versa)
                # Keep the new position, but take all other properties from header
                new_entity = deepcopy(entity)
                set_entity_position(new_entity, new_x, new_y)
                
                # Replace in the merged list
                for i, e in enumerate(merged):
                    if e is matching_entity:
                        merged[i] = new_entity
                        main_position_map[entity_key] = new_entity
                        break
            else:
                # Deep merge properties, preferring header values
                merged_entity = deep_merge_entity_properties(matching_entity, entity)
                # Update the entity in the merged list
                for i, e in enumerate(merged):
                    if e is matching_entity:
                        merged[i] = merged_entity
                        break
            continue
        
        # Add new entity
        new_entity = deepcopy(entity)
        set_entity_position(new_entity, new_x, new_y)
        existing_positions.add(entity_key)
        merged.append(new_entity)
        main_position_map[entity_key] = new_entity
        position_mapping[old_pos_str] = new_pos_str
    
    if skipped_duplicates > 0:
        print(f"Skipped {skipped_duplicates} duplicate entities", file=sys.stderr)
    
    return merged, position_mapping


def update_wire_positions(wire: List, offset_x: float, offset_y: float) -> List:
    """
    Update wire position references by applying offset.
    Wire format: [position_str, circuit_id, position_str, circuit_id]
    """
    updated = wire.copy()
    for idx in [0, 2]:  # Position indices in wire array
        if idx < len(updated) and isinstance(updated[idx], str) and ',' in updated[idx]:
            x, y = parse_position_string(updated[idx])
            new_x, new_y = adjust_position(x, y, offset_x, offset_y)
            updated[idx] = format_position_string(new_x, new_y)
    return updated


def get_min_position(entities: List[Dict]) -> Tuple[float, float]:
    """Get the minimum x and y positions from entity list."""
    if not entities:
        return (0, 0)
    return (min(e["position"]["x"] for e in entities),
            min(e["position"]["y"] for e in entities))


def get_wire_positions(wire: List) -> List[Tuple[float, float]]:
    """Extract position tuples from wire at indices 0 and 2."""
    positions = []
    for idx in [0, 2]:
        if idx < len(wire) and isinstance(wire[idx], str) and ',' in wire[idx]:
            positions.append(parse_position_string(wire[idx]))
    return positions


def merge_blueprints(main_bp: Dict, header_bp: Dict, verbose: bool = False) -> Dict:
    """
    Merge header blueprint into main blueprint using train-stop as anchor.
    
    Args:
        main_bp: The main blueprint (primary source)
        header_bp: The header blueprint to merge in
        
    Returns:
        Merged blueprint dictionary (preserves index from main blueprint)
    """
    # Get the blueprint data (handle blueprint vs blueprint_book structure)
    main_data = main_bp.get("blueprint")
    header_data = header_bp.get("blueprint")
    
    if not main_data or not header_data:
        raise ValueError("Both inputs must contain 'blueprint' data")
    
    # Get minimum positions for wire coordinate conversion
    main_entities = main_data.get("entities", [])
    header_entities = header_data.get("entities", [])
    main_min_x, main_min_y = get_min_position(main_entities)
    header_min_x, header_min_y = get_min_position(header_entities)

    # Create result preserving index from main blueprint if present
    result = {"blueprint": deepcopy(main_data)}
    if "index" in main_bp:
        result["index"] = main_bp["index"]
    
    # Find train-stops to determine merge points
    main_train_stops = find_train_stops(main_entities)
    header_train_stops = find_train_stops(header_entities)
    
    if not main_train_stops:
        # No train-stops in main blueprint - return it unchanged
        if verbose:
            print("No train-stops found in main blueprint - returning unchanged", file=sys.stderr)
        return result
    if len(header_train_stops) != 1:
        raise ValueError(f"Header blueprint must contain exactly one train-stop, found {len(header_train_stops)}")
    
    header_stop_pos = get_entity_position(header_train_stops[0][1])
    print(f"Found {len(main_train_stops)} train-stop(s) in main blueprint", file=sys.stderr)
    print(f"Header train-stop at: {header_stop_pos}", file=sys.stderr)
    
    # Start with main entities and wires
    merged_entities = deepcopy(main_entities)
    
    # Build position set for duplicate detection
    existing_positions = set()
    for entity in merged_entities:
        pos = get_entity_position(entity)
        key = (pos[0], pos[1], entity.get("name"))
        existing_positions.add(key)
    
    # Initialize wire tracking
    wire_set = set()
    merged_wires = []
    
    # Process main wires (convert to absolute coordinates)
    for wire in main_data.get("wires", []):
        absolute_wire = update_wire_positions(wire, main_min_x, main_min_y)
        wire_key = tuple(absolute_wire)
        if wire_key not in wire_set:
            wire_set.add(wire_key)
            merged_wires.append(absolute_wire)
    
    # Merge header at each train-stop location
    total_entities_added = 0
    total_wires_added = 0
    total_duplicates_skipped = 0
    
    for stop_idx, (_, main_stop_entity) in enumerate(main_train_stops):
        main_stop_pos = get_entity_position(main_stop_entity)
        
        # Calculate offset for this train-stop
        offset_x = main_stop_pos[0] - header_stop_pos[0]
        offset_y = main_stop_pos[1] - header_stop_pos[1]
        
        if verbose:
            print(f"\nMerging at train-stop {stop_idx + 1}/{len(main_train_stops)}: {main_stop_pos}", file=sys.stderr)
            print(f"  Offset: ({offset_x}, {offset_y})", file=sys.stderr)
        
        # Merge header entities at this location
        duplicates_at_stop = 0
        entities_added_at_stop = 0
        
        for entity in header_entities:
            entity_name = entity.get("name")
            
            old_x, old_y = get_entity_position(entity)
            new_x, new_y = adjust_position(old_x, old_y, offset_x, offset_y)
            entity_key = (new_x, new_y, entity_name)
            
            # Check for exact match or cross-type train-stop match
            is_train_stop = entity_name in ("train-stop", "logistic-train-stop")
            matching_entity_idx = None
            old_entity_name = None
            
            if entity_key in existing_positions:
                # Find the matching entity index
                for idx, e in enumerate(merged_entities):
                    if get_entity_position(e) == (new_x, new_y) and e.get("name") == entity_name:
                        matching_entity_idx = idx
                        old_entity_name = entity_name
                        break
            elif is_train_stop:
                # Check for cross-type match (train-stop vs logistic-train-stop)
                alternate_name = "logistic-train-stop" if entity_name == "train-stop" else "train-stop"
                alternate_key = (new_x, new_y, alternate_name)
                if alternate_key in existing_positions:
                    for idx, e in enumerate(merged_entities):
                        if get_entity_position(e) == (new_x, new_y) and e.get("name") == alternate_name:
                            matching_entity_idx = idx
                            old_entity_name = alternate_name
                            break
            
            if matching_entity_idx is not None:
                # Entity exists - replace it with header version (keeping position)
                new_entity = deepcopy(entity)
                set_entity_position(new_entity, new_x, new_y)
                
                # For train-stops, preserve station name from main if header has empty name
                if is_train_stop:
                    old_entity = merged_entities[matching_entity_idx]
                    old_station = old_entity.get("station", "")
                    new_station = new_entity.get("station", "")
                    if new_station == "" and old_station != "":
                        new_entity["station"] = old_station
                
                # Remove old key if entity name changed, add new key
                if old_entity_name != entity_name:
                    old_key = (new_x, new_y, old_entity_name)
                    existing_positions.discard(old_key)
                    existing_positions.add(entity_key)
                
                # Replace the entity
                merged_entities[matching_entity_idx] = new_entity
                duplicates_at_stop += 1
                continue
            
            # Add new entity
            new_entity = deepcopy(entity)
            set_entity_position(new_entity, new_x, new_y)
            existing_positions.add(entity_key)
            merged_entities.append(new_entity)
            entities_added_at_stop += 1
        
        # Merge header wires at this location
        wires_added_at_stop = 0
        for wire in header_data.get("wires", []):
            # Convert to absolute, then apply merge offset
            absolute_wire = update_wire_positions(wire, header_min_x, header_min_y)
            merged_wire = update_wire_positions(absolute_wire, offset_x, offset_y)
            wire_key = tuple(merged_wire)
            
            if wire_key not in wire_set:
                wire_set.add(wire_key)
                merged_wires.append(merged_wire)
                wires_added_at_stop += 1
        
        total_entities_added += entities_added_at_stop
        total_wires_added += wires_added_at_stop
        total_duplicates_skipped += duplicates_at_stop
        
        if verbose:
            print(f"  Added {entities_added_at_stop} entities, {wires_added_at_stop} wires", file=sys.stderr)
            if duplicates_at_stop > 0:
                print(f"  Skipped {duplicates_at_stop} duplicate entities", file=sys.stderr)
    
    result["blueprint"]["entities"] = merged_entities
    result["blueprint"]["wires"] = merged_wires
    
    print(f"\n=== Merge Summary ===", file=sys.stderr)
    print(f"Merged at {len(main_train_stops)} train-stop location(s)", file=sys.stderr)
    print(f"Added {total_entities_added} entities ({total_duplicates_skipped} duplicates skipped)", file=sys.stderr)
    print(f"Total entities: {len(merged_entities)}", file=sys.stderr)
    print(f"Added {total_wires_added} wires, total: {len(merged_wires)}", file=sys.stderr)
    
    # Normalize positions to ensure minimum x and y are 0
    min_x, min_y = get_min_position(merged_entities)
    
    # Check wire positions too
    for wire in merged_wires:
        for x, y in get_wire_positions(wire):
            min_x = min(min_x, x)
            min_y = min(min_y, y)
    
    # Apply normalization if needed
    if min_x < 0 or min_y < 0:
        norm_x = -min_x if min_x < 0 else 0
        norm_y = -min_y if min_y < 0 else 0
        
        if verbose:
            print(f"Normalizing positions by ({norm_x}, {norm_y})", file=sys.stderr)
        
        # Normalize entities
        for entity in merged_entities:
            x, y = get_entity_position(entity)
            set_entity_position(entity, x + norm_x, y + norm_y)
        
        # Normalize wires
        result["blueprint"]["wires"] = [
            update_wire_positions(wire, norm_x, norm_y) for wire in merged_wires
        ]
        
        # Adjust shift coordinates to compensate
        if "shift_x" in result["blueprint"]:
            result["blueprint"]["shift_x"] += min_x
        if "shift_y" in result["blueprint"]:
            result["blueprint"]["shift_y"] += min_y
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Merge Factorio blueprints using train-stop as anchor point.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge header into main and output to file
  %(prog)s main.json header.json -o merged.json
  
  # Merge and output to stdout
  %(prog)s main.json header.json
  
  # Verbose output
  %(prog)s main.json header.json -o merged.json -v
        """
    )
    
    parser.add_argument("main", type=Path,
                       help="Main blueprint JSON file (primary source)")
    parser.add_argument("header", type=Path,
                       help="header blueprint JSON file to merge in")
    parser.add_argument("-o", "--output", type=Path,
                       help="Output file (default: stdout)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")
    parser.add_argument("--pretty", action="store_true",
                       help="Pretty-print JSON output")
    
    args = parser.parse_args()
    
    # Load blueprints
    if args.verbose:
        print(f"Loading main blueprint from {args.main}", file=sys.stderr)
    main_bp = json.loads(args.main.read_text(encoding="utf8"))
    
    if args.verbose:
        print(f"Loading header blueprint from {args.header}", file=sys.stderr)
    header_bp = json.loads(args.header.read_text(encoding="utf8"))
    
    # Merge
    merged = merge_blueprints(main_bp, header_bp, verbose=args.verbose)
    
    # Output
    if args.pretty:
        output = json.dumps(merged, indent=2, ensure_ascii=False)
    else:
        output = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    
    if args.output:
        if args.verbose:
            print(f"Writing merged blueprint to {args.output}", file=sys.stderr)
        args.output.write_text(output + "\n", encoding="utf8")
    else:
        print(output)
    
    if args.verbose:
        print("Merge complete!", file=sys.stderr)


if __name__ == "__main__":
    main()
