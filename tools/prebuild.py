#!/usr/bin/env python3
"""
Pre-build script for Factorio blueprints.

Processes blueprint directories, merging headers with bodies where configured,
and outputs everything to a dist folder ready for encoding.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Import merge functionality
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "merge_blueprints",
    os.path.join(os.path.dirname(__file__), "merge-blueprints.py")
)
merge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_module)
do_merge = merge_module.merge_blueprints


def should_process_file(filename):
    """Check if a file should be processed."""
    if filename.startswith('.') or filename.startswith('_'):
        return False
    if filename == 'headers':
        return False
    return True


def copy_with_metadata(src_file, dst_file, verbose=False):
    """Copy a blueprint file and its metadata to destination."""
    if verbose:
        print(f"  Copying: {src_file.name}")
    
    # Copy main file
    shutil.copy2(src_file, dst_file)
    
    # Copy metadata if it exists
    src_meta = src_file.with_suffix('.metadata')
    if src_meta.exists():
        dst_meta = dst_file.with_suffix('.metadata')
        shutil.copy2(src_meta, dst_meta)


def merge_and_output(body_file, header_file, output_dir, verbose=False):
    """Merge a header with a body and output the result."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load blueprints
    with open(body_file, 'r') as f:
        body_data = json.load(f)
    
    with open(header_file, 'r') as f:
        header_data = json.load(f)
    
    # Get body name without extension for output filename
    body_name = body_file.stem
    header_name = header_file.stem
    
    if verbose:
        print(f"  Merging: {body_name} + {header_name}")
    
    # Merge
    try:
        merged = do_merge(body_data, header_data, verbose=False)
    except Exception as e:
        print(f"    ERROR merging {body_name} + {header_name}: {e}", file=sys.stderr)
        return None
    
    # Create output filename
    output_file = output_dir / f"{body_name}.json"
    
    # Write merged blueprint
    with open(output_file, 'w') as f:
        json.dump(merged, f, indent=2)
    
    # Copy metadata from body if it exists
    body_meta = body_file.with_suffix('.metadata')
    if body_meta.exists():
        output_meta = output_file.with_suffix('.metadata')
        shutil.copy2(body_meta, output_meta)
    
    return output_file


def process_directory(src_dir, dst_dir, verbose=False):
    """
    Process a directory, handling merges and copies.
    
    If a 'headers' subdirectory exists:
    - Create a subdirectory for each header in dst_dir
    - Merge each header with each body blueprint
    - Output merged blueprints to header-named subdirectories
    
    Otherwise:
    - Copy files and recursively process subdirectories
    """
    src_path = Path(src_dir)
    dst_path = Path(dst_dir)
    
    # Create destination directory
    dst_path.mkdir(parents=True, exist_ok=True)
    
    # Check for headers subdirectory
    headers_dir = src_path / 'headers'
    
    if headers_dir.exists() and headers_dir.is_dir():
        # This directory has headers - perform merging
        if verbose:
            print(f"Processing merge directory: {src_path.name}")
        
        # Get all header files
        header_files = sorted([f for f in headers_dir.glob('*.json') if should_process_file(f.name)])
        
        if not header_files:
            print(f"  WARNING: No header files found in {headers_dir}", file=sys.stderr)
            return
        
        # Get all body blueprint files (excluding headers subdirectory)
        body_files = sorted([
            f for f in src_path.glob('*.json')
            if should_process_file(f.name) and f.is_file()
        ])
        
        if not body_files:
            print(f"  WARNING: No body files found in {src_path}", file=sys.stderr)
            return
        
        # Track used indices to avoid conflicts
        used_indices = set()
        
        # Check existing metadata files in the destination directory to find used indices
        if dst_path.exists():
            for item in dst_path.iterdir():
                if item.is_dir():
                    meta_file = item / '_metadata.json'
                    if meta_file.exists():
                        try:
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                                if 'index' in meta:
                                    used_indices.add(meta['index'])
                        except Exception:
                            pass
        
        # Load parent directory metadata once
        parent_meta_file = src_path / '_metadata.json'
        parent_base_index = None
        parent_meta_template = None
        
        if parent_meta_file.exists():
            with open(parent_meta_file, 'r') as f:
                parent_meta_template = json.load(f)
                parent_base_index = parent_meta_template.get('index')
        
        # For each header, create a subdirectory and merge with all bodies
        for i, header_file in enumerate(header_files):
            header_name = header_file.stem
            header_output_dir = dst_path / header_name
            
            if verbose:
                print(f"\n  Building merged blueprints for: {header_name}")
            
            # Track successful merges
            successful_merges = 0
            
            # Merge this header with all body blueprints
            for body_file in body_files:
                result = merge_and_output(body_file, header_file, header_output_dir, verbose)
                if result is not None:
                    successful_merges += 1
            
            # Only keep the header directory if we had successful merges
            if successful_merges == 0:
                if verbose:
                    print(f"  Skipping {header_name}: No successful merges")
                if header_output_dir.exists():
                    shutil.rmtree(header_output_dir)
                continue
            
            # Copy metadata for the header subdirectory
            # Use parent directory metadata and prepend first word from header label
            dst_meta = header_output_dir / '_metadata.json'
            
            # Load header to get its label
            with open(header_file, 'r') as f:
                header_data = json.load(f)
            
            # Extract first word from header label
            header_bp = header_data.get('blueprint', {})
            header_label = header_bp.get('label', header_name)
            first_word = header_label.split()[0] if header_label else header_name.split('-')[0].title()
            
            # Determine the index for this metadata
            if parent_base_index is not None:
                # Start from parent index and increment if needed
                candidate_index = parent_base_index + i
                while candidate_index in used_indices:
                    candidate_index += 1
                used_indices.add(candidate_index)
            else:
                candidate_index = i
            
            if parent_meta_template:
                parent_meta = parent_meta_template.copy()
                
                # Update index
                parent_meta['index'] = candidate_index
                
                # Prepend first word to the label
                if 'blueprint_book' in parent_meta:
                    original_label = parent_meta['blueprint_book'].get('label', '')
                    parent_meta['blueprint_book']['label'] = f"{first_word} {original_label}"
                
                with open(dst_meta, 'w') as f:
                    json.dump(parent_meta, f, indent=2)
            else:
                # Create minimal metadata with prepended label
                metadata = {
                    "index": candidate_index,
                    "blueprint_book": {
                        "item": "blueprint-book",
                        "label": f"{first_word} {src_path.name.replace('-', ' ').title()}",
                        "version": 562949957025792
                    }
                }
                with open(dst_meta, 'w') as f:
                    json.dump(metadata, f, indent=2)
        
        # Copy parent directory metadata if it exists
        src_meta = src_path / '_metadata.json'
        if src_meta.exists():
            dst_meta = dst_path / '_metadata.json'
            shutil.copy2(src_meta, dst_meta)
    
    else:
        # No headers - standard directory processing
        if verbose:
            print(f"Processing directory: {src_path.name}")
        
        # Copy all files
        for item in src_path.iterdir():
            if not should_process_file(item.name):
                # Copy metadata and config files
                if item.is_file() and (item.name.startswith('.') or item.name.startswith('_')):
                    dst_item = dst_path / item.name
                    shutil.copy2(item, dst_item)
                continue
            
            if item.is_file():
                dst_item = dst_path / item.name
                copy_with_metadata(item, dst_item, verbose)
            
            elif item.is_dir():
                # Recursively process subdirectory
                dst_subdir = dst_path / item.name
                process_directory(item, dst_subdir, verbose)


def main():
    parser = argparse.ArgumentParser(
        description='Pre-build script to merge and prepare blueprints for encoding'
    )
    parser.add_argument(
        'source',
        type=Path,
        help='Source directory containing blueprints'
    )
    parser.add_argument(
        'dist',
        type=Path,
        help='Destination dist directory for processed blueprints',
        default=Path('./dist')
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean dist directory before processing'
    )
    
    args = parser.parse_args()
    
    # Validate source
    if not args.source.exists():
        print(f"ERROR: Source directory does not exist: {args.source}", file=sys.stderr)
        sys.exit(1)
    
    if not args.source.is_dir():
        print(f"ERROR: Source is not a directory: {args.source}", file=sys.stderr)
        sys.exit(1)
    
    # Clean dist if requested
    if args.clean and args.dist.exists():
        if args.verbose:
            print(f"Cleaning dist directory: {args.dist}")
        shutil.rmtree(args.dist)
    
    # Determine the output path that preserves the source structure
    # For example: source=brians-trains/book, dist=./dist -> output=./dist/brians-trains/book
    output_path = args.dist / args.source
    
    # Process the source directory
    if args.verbose:
        print(f"Processing: {args.source} -> {output_path}\n")
    
    process_directory(args.source, output_path, args.verbose)
    
    if args.verbose:
        print(f"\nDone! Output in: {output_path}")


if __name__ == '__main__':
    main()
