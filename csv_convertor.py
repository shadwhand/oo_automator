#!/usr/bin/env python3
"""
Hybrid CSV Converter with Pattern Detection + MAR Validation
First applies pattern-based rules, then validates with MAR
"""

import csv
import re
import sys
import os
from pathlib import Path


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def pattern_based_convert(value):
    """
    Apply pattern-based conversion rules for common mistyped values.
    Rules:
    - 1 or -1 -> 0.01 or -0.01
    - 0.x00000 pattern (like 0.100000) -> 0.00x (like 0.001)
    - x.y pattern (like 0.5) -> 0.0xy (like 0.005)
    - single digit (like 5) -> 0.005
    """
    if not value or value == '':
        return value, False
    
    # Check if it's numeric
    try:
        float_val = float(value)
    except ValueError:
        return value, False
    
    val = value.strip()
    
    # Special case for 1 and -1 (including with trailing zeros)
    if val in ['1', '1.0', '1.000000']:
        return '0.01', True
    elif val in ['-1', '-1.0', '-1.000000']:
        return '-0.01', True
    
    # Pattern for 0.x00000 format (like 0.100000, 0.200000, etc.)
    pattern_trailing = re.match(r'^(-?)0\.(\d)0{5}$', value)
    if pattern_trailing:
        sign = pattern_trailing.group(1)
        digit = pattern_trailing.group(2)
        return f"{sign}0.00{digit}", True
    
    # Pattern for 0.x00 format (like 0.100, 0.200, etc.)
    pattern_hundreds = re.match(r'^(-?)0\.([1-9])00$', value)
    if pattern_hundreds:
        sign = pattern_hundreds.group(1)
        digit = pattern_hundreds.group(2)
        return f"{sign}0.00{digit}", True
    
    # Pattern for 0.x format (like 0.1, 0.2, etc.)
    pattern_tenths = re.match(r'^(-?)0\.([1-9])$', value)
    if pattern_tenths:
        sign = pattern_tenths.group(1)
        digit = pattern_tenths.group(2)
        return f"{sign}0.00{digit}", True
    
    # Pattern for x.y (two single digits) - like 1.5 -> 0.015
    pattern_xy = re.match(r'^(-?)(\d)\.(\d)$', value)
    if pattern_xy:
        sign = pattern_xy.group(1)
        first_digit = pattern_xy.group(2)
        second_digit = pattern_xy.group(3)
        return f"{sign}0.0{first_digit}{second_digit}", True
    
    # Pattern for single digit (including negative) - like 5 -> 0.005
    pattern_single = re.match(r'^(-?)([1-9])$', value)
    if pattern_single:
        sign = pattern_single.group(1)
        digit = pattern_single.group(2)
        return f"{sign}0.00{digit}", True
    
    # Handle 0 specially
    if val in ['0', '-0', '0.0', '0.000000']:
        return '0.000', True
    
    return value, False


def calculate_mar(cagr, drawdown):
    """Calculate MAR with protection against division by zero. MAR is always absolute."""
    if abs(drawdown) < 0.0001:
        return 0
    return abs(cagr) / abs(drawdown)  # MAR is always positive (absolute value)


def validate_mar(cagr, drawdown, mar_expected):
    """
    Check if CAGR and Drawdown produce the expected MAR.
    Returns True if MAR is exact or very close (within 1%)
    """
    if abs(drawdown) < 0.0001:
        return abs(mar_expected) < 0.0001
    
    mar_calculated = calculate_mar(cagr, drawdown)
    
    # Check for exact match or very close match
    if abs(mar_expected) < 0.0001:
        return abs(mar_calculated) < 0.0001
    
    error = abs(mar_calculated - mar_expected) / abs(mar_expected)
    return error < 0.01  # Within 1% is considered valid


def process_csv_hybrid(input_file, output_file):
    """
    Process CSV using hybrid approach: pattern detection + MAR validation.
    """
    try:
        # Read the input CSV
        with open(input_file, 'r', newline='', encoding='utf-8') as infile:
            sample = infile.read(1024)
            infile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.reader(infile, delimiter=delimiter)
            rows = list(reader)
        
        if len(rows) < 2:
            print("Error: CSV file has no data rows")
            return False
        
        header = rows[0]
        data_rows = rows[1:]
        
        # Find column indices
        cagr_idx = None
        drawdown_idx = None
        mar_idx = None
        capture_idx = None
        
        for i, col in enumerate(header):
            if 'CAGR' in col:
                cagr_idx = i
            elif 'Drawdown' in col:
                drawdown_idx = i
            elif 'MAR' in col:
                mar_idx = i
            elif 'Capture' in col:
                capture_idx = i
        
        if None in [cagr_idx, drawdown_idx, mar_idx]:
            print("Error: Required columns (CAGR, Max Drawdown, MAR) not found")
            print(f"Found columns: {header}")
            return False
        
        # Process rows
        processed_rows = [header]
        pattern_corrections = 0
        mar_validations = 0
        correction_examples = []
        mar_mismatches = []
        
        for row_idx, row in enumerate(data_rows):
            new_row = row.copy()
            
            # Step 1: Apply pattern-based conversions
            cagr_str = row[cagr_idx]
            dd_str = row[drawdown_idx]
            capture_str = row[capture_idx] if capture_idx else None
            
            # Convert CAGR
            cagr_converted, cagr_changed = pattern_based_convert(cagr_str)
            if cagr_changed:
                new_row[cagr_idx] = cagr_converted
                pattern_corrections += 1
                if len(correction_examples) < 10:
                    correction_examples.append({
                        'row': row_idx + 2,
                        'col': 'CAGR',
                        'old': cagr_str,
                        'new': cagr_converted,
                        'type': 'pattern'
                    })
            
            # Convert Drawdown
            dd_converted, dd_changed = pattern_based_convert(dd_str)
            if dd_changed:
                new_row[drawdown_idx] = dd_converted
                pattern_corrections += 1
                if len(correction_examples) < 10:
                    correction_examples.append({
                        'row': row_idx + 2,
                        'col': 'Max Drawdown',
                        'old': dd_str,
                        'new': dd_converted,
                        'type': 'pattern'
                    })
            
            # Convert Capture Rate if it exists
            if capture_idx is not None and capture_str:
                capture_converted, capture_changed = pattern_based_convert(capture_str)
                if capture_changed:
                    new_row[capture_idx] = capture_converted
                    pattern_corrections += 1
                    if len(correction_examples) < 10:
                        correction_examples.append({
                            'row': row_idx + 2,
                            'col': 'Capture Rate',
                            'old': capture_str,
                            'new': capture_converted,
                            'type': 'pattern'
                        })
            
            # Step 2: Validate with MAR
            try:
                cagr_final = float(new_row[cagr_idx])
                dd_final = float(new_row[drawdown_idx])
                mar_expected = float(row[mar_idx])
                
                # Check if MAR matches
                if not validate_mar(cagr_final, dd_final, mar_expected):
                    # MAR doesn't match - try to fix
                    mar_calculated = calculate_mar(cagr_final, dd_final)
                    
                    # Try converting CAGR if it wasn't already converted
                    if not cagr_changed and abs(cagr_final) > 0.1:
                        cagr_test = cagr_final / 100
                        if validate_mar(cagr_test, dd_final, mar_expected):
                            new_row[cagr_idx] = f"{cagr_test:.6f}".rstrip('0').rstrip('.')
                            mar_validations += 1
                            if len(correction_examples) < 10:
                                correction_examples.append({
                                    'row': row_idx + 2,
                                    'col': 'CAGR',
                                    'old': cagr_str,
                                    'new': new_row[cagr_idx],
                                    'type': 'MAR fix'
                                })
                        else:
                            # Still doesn't match - log it
                            if len(mar_mismatches) < 5:
                                mar_mismatches.append({
                                    'row': row_idx + 2,
                                    'cagr': cagr_final,
                                    'dd': dd_final,
                                    'mar_expected': mar_expected,
                                    'mar_calculated': mar_calculated
                                })
                    
                    # Try converting Drawdown if it wasn't already converted
                    elif not dd_changed and abs(dd_final) > 0.1:
                        dd_test = dd_final / 100
                        if validate_mar(cagr_final, dd_test, mar_expected):
                            new_row[drawdown_idx] = f"{dd_test:.6f}".rstrip('0').rstrip('.')
                            mar_validations += 1
                            if len(correction_examples) < 10:
                                correction_examples.append({
                                    'row': row_idx + 2,
                                    'col': 'Max Drawdown',
                                    'old': dd_str,
                                    'new': new_row[drawdown_idx],
                                    'type': 'MAR fix'
                                })
                    else:
                        # Pattern conversion didn't fix MAR
                        if len(mar_mismatches) < 5:
                            mar_mismatches.append({
                                'row': row_idx + 2,
                                'cagr': cagr_final,
                                'dd': dd_final,
                                'mar_expected': mar_expected,
                                'mar_calculated': mar_calculated
                            })
                
            except (ValueError, IndexError):
                # Keep row as-is if there's an error
                pass
            
            processed_rows.append(new_row)
        
        # Write output
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile, delimiter=delimiter)
            writer.writerows(processed_rows)
        
        # Report results
        print(f"\n{'='*70}")
        print(f"Hybrid Conversion Complete!")
        print(f"{'='*70}")
        print(f"Input:  {input_file}")
        print(f"Output: {output_file}")
        print(f"Rows processed: {len(data_rows)}")
        print(f"Pattern-based corrections: {pattern_corrections}")
        print(f"MAR-based corrections: {mar_validations}")
        print(f"Total corrections: {pattern_corrections + mar_validations}")
        
        if correction_examples:
            print(f"\n{'='*70}")
            print(f"Example corrections:")
            print(f"{'-'*70}")
            for ex in correction_examples[:10]:
                print(f"Row {ex['row']:3d}, {ex['col']:15s}: {ex['old']:10s} → {ex['new']:10s} [{ex['type']}]")
        
        if mar_mismatches:
            print(f"\n{'='*70}")
            print(f"⚠️  MAR Validation Issues (need manual review):")
            print(f"{'-'*70}")
            for mm in mar_mismatches:
                print(f"Row {mm['row']:3d}: CAGR={mm['cagr']:.4f}, DD={mm['dd']:.4f}")
                print(f"         MAR expected: {mm['mar_expected']:.4f}, calculated: {mm['mar_calculated']:.4f}")
        
        return True
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
        return False
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_patterns():
    """Test pattern detection on known problematic values."""
    test_cases = [
        ('0.6', '0.006'),
        ('0.7', '0.007'),
        ('0.8', '0.008'),
        ('0.9', '0.009'),
        ('0.100000', '0.001'),
        ('0.200000', '0.002'),
        ('-0.100000', '-0.001'),
        ('1', '0.01'),
        ('-1', '-0.01'),
        ('0.5', '0.005'),
        ('-0.5', '-0.005'),
        ('5', '0.005'),
        ('-7', '-0.007'),
        ('0.014', '0.014'),  # Should not change
        ('-0.023', '-0.023'),  # Should not change
    ]
    
    print("\nPattern Detection Test:")
    print("-" * 40)
    all_passed = True
    for input_val, expected in test_cases:
        result, changed = pattern_based_convert(input_val)
        if changed:
            status = "✓" if result == expected else "✗"
            if result != expected:
                all_passed = False
            print(f"{status} {input_val:8s} → {result:8s} (expected {expected})")
        else:
            status = "✓" if input_val == expected else "✗"
            if input_val != expected:
                all_passed = False
            print(f"{status} {input_val:8s} → unchanged (expected {expected})")
    
    print("-" * 40)
    print(f"All tests passed: {all_passed}")
    return all_passed


def interactive_mode():
    """Run the converter in interactive mode."""
    clear_screen()
    print("=" * 70)
    print("Hybrid CSV Converter - Pattern Detection + MAR Validation")
    print("=" * 70)
    print("\nThis tool corrects CSV values using:")
    print("  1. Pattern-based detection for common formats (0.6 → 0.006)")
    print("  2. MAR validation to ensure |CAGR| / |Drawdown| = MAR")
    print()
    
    # Run pattern tests
    test_patterns()
    
    while True:
        print("\n" + "-" * 70)
        filename = input("Enter CSV filename (or 'quit' to exit): ").strip()
        
        if filename.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye!")
            break
        
        if not filename:
            print("Please enter a filename.")
            continue
        
        # Add .csv extension if not present
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        input_file = Path(filename)
        
        if not input_file.exists():
            print(f"\n⚠️  File '{filename}' not found.")
            continue
        
        # Generate output filename
        output_file = input_file.parent / f"{input_file.stem}_corrected{input_file.suffix}"
        
        print(f"\nProcessing: {filename}")
        print(f"Output will be: {output_file}")
        
        # Process the file
        success = process_csv_hybrid(input_file, output_file)
        
        if success:
            print(f"\n✓ File successfully processed!")
        else:
            print(f"\n✗ Failed to process file.")
        
        # Ask if user wants to continue
        print("\n" + "-" * 70)
        choice = input("Process another file? (y/n): ").strip().lower()
        
        if choice not in ['y', 'yes']:
            print("\nGoodbye!")
            break
        
        clear_screen()


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Command-line mode
        if sys.argv[1] in ['--help', '-h']:
            print("Hybrid CSV Converter - Pattern Detection + MAR Validation")
            print("\nUsage:")
            print("  python csv_converter.py           # Interactive mode")
            print("  python csv_converter.py file.csv  # Process single file")
            print("  python csv_converter.py --test    # Run pattern tests")
            sys.exit(0)
        elif sys.argv[1] == '--test':
            test_patterns()
            sys.exit(0)
        
        # Process single file from command line
        input_file = Path(sys.argv[1])
        if not input_file.exists():
            print(f"Error: File '{input_file}' not found.")
            sys.exit(1)
        
        output_file = input_file.parent / f"{input_file.stem}_corrected{input_file.suffix}"
        success = process_csv_hybrid(input_file, output_file)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
