"""
Migration Helper Script
Helps transition from old automation to refactored version

Usage:
    python migrate_to_refactored.py --check     # Check current setup
    python migrate_to_refactored.py --setup     # Create new structure
    python migrate_to_refactored.py --verify    # Verify installation
"""

import os
import sys
import shutil
import argparse
from pathlib import Path


def check_current_setup():
    """Check what files exist in current setup"""
    print("="*70)
    print("CHECKING CURRENT SETUP")
    print("="*70)
    
    required_old_files = [
        'OO_Automator_Plugin.py',
        'parameter_plugin_system.py',
        'trade_analysis_plugin.py'
    ]
    
    found_files = []
    missing_files = []
    
    for filename in required_old_files:
        if os.path.exists(filename):
            found_files.append(filename)
            print(f"✅ Found: {filename}")
        else:
            missing_files.append(filename)
            print(f"❌ Missing: {filename}")
    
    print(f"\nFound {len(found_files)}/{len(required_old_files)} required files")
    
    # Check for existing backups
    backup_dir = 'backup_original'
    if os.path.exists(backup_dir):
        print(f"\n⚠️  Backup directory already exists: {backup_dir}")
        print("   Previous migration may have been attempted")
    
    return len(found_files) == len(required_old_files)


def create_directory_structure():
    """Create new directory structure"""
    print("\n" + "="*70)
    print("CREATING NEW DIRECTORY STRUCTURE")
    print("="*70)
    
    directories = [
        'utils',
        'pages',
        'backup_original'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created: {directory}/")
            
            # Create __init__.py files
            if directory in ['utils', 'pages']:
                init_file = os.path.join(directory, '__init__.py')
                if not os.path.exists(init_file):
                    with open(init_file, 'w') as f:
                        if directory == 'utils':
                            f.write("from .waiters import *\nfrom .selectors import *\n")
                        else:
                            f.write("from .test_page import TestPage\n")
                    print(f"   Created: {init_file}")
        except Exception as e:
            print(f"❌ Error creating {directory}: {e}")
            return False
    
    return True


def backup_original_files():
    """Backup original files before migration"""
    print("\n" + "="*70)
    print("BACKING UP ORIGINAL FILES")
    print("="*70)
    
    files_to_backup = [
        'OO_Automator_Plugin.py',
        'parameter_plugin_system.py',
        'trade_analysis_plugin.py'
    ]
    
    backup_dir = 'backup_original'
    
    for filename in files_to_backup:
        if os.path.exists(filename):
            try:
                backup_path = os.path.join(backup_dir, filename)
                shutil.copy2(filename, backup_path)
                print(f"✅ Backed up: {filename} → {backup_path}")
            except Exception as e:
                print(f"❌ Error backing up {filename}: {e}")
                return False
        else:
            print(f"⚠️  Skipped (not found): {filename}")
    
    return True


def create_new_files_guide():
    """Print guide for creating new files"""
    print("\n" + "="*70)
    print("NEW FILES TO CREATE")
    print("="*70)
    
    new_files = {
        'utils/waiters.py': 'Copy from artifact: waiters.py',
        'utils/selectors.py': 'Copy from artifact: selectors.py',
        'pages/test_page.py': 'Copy from artifact: test_page.py',
        'OO_Automator_Plugin.py': 'Replace with refactored version (Parts 1-4)',
        'parameter_plugin_system.py': 'Replace with complete version with verification',
    }
    
    print("\nYou need to create these files:")
    for filepath, instruction in new_files.items():
        print(f"\n📄 {filepath}")
        print(f"   → {instruction}")
    
    print("\n" + "="*70)
    print("STEP-BY-STEP GUIDE")
    print("="*70)
    print("""
1. Copy utils/waiters.py from the artifact provided
2. Copy utils/selectors.py from the artifact provided
3. Copy pages/test_page.py from the artifact provided
4. Replace OO_Automator_Plugin.py with Parts 1-4 (concatenated)
5. Replace parameter_plugin_system.py with complete version
6. Keep trade_analysis_plugin.py as-is (no changes needed)

After creating files, run:
    python migrate_to_refactored.py --verify
""")


def verify_installation():
    """Verify the new installation is complete"""
    print("\n" + "="*70)
    print("VERIFYING INSTALLATION")
    print("="*70)
    
    required_files = {
        'utils/waiters.py': ['wait_clickable', 'wait_visible', 'find_any'],
        'utils/selectors.py': ['NEW_BACKTEST_BTN', 'LOGIN_EMAIL', 'PROGRESS_ANY'],
        'pages/test_page.py': ['class TestPage', 'def click_new_backtest'],
        'utils/__init__.py': ['from .waiters', 'from .selectors'],
        'pages/__init__.py': ['from .test_page'],
        'OO_Automator_Plugin.py': ['class OptionOmegaWorker', 'def verify_value', 'from utils.waiters'],
        'parameter_plugin_system.py': ['def verify_value', 'from utils.waiters', 'from utils.selectors'],
        'trade_analysis_plugin.py': ['def enhance_results_with_trade_metrics'],
    }
    
    all_good = True
    
    for filepath, required_content in required_files.items():
        if not os.path.exists(filepath):
            print(f"❌ Missing: {filepath}")
            all_good = False
            continue
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            missing_content = []
            for req in required_content:
                if req not in content:
                    missing_content.append(req)
            
            if missing_content:
                print(f"⚠️  {filepath} - missing content:")
                for item in missing_content:
                    print(f"      - {item}")
                all_good = False
            else:
                print(f"✅ {filepath} - looks good")
        
        except Exception as e:
            print(f"❌ Error checking {filepath}: {e}")
            all_good = False
    
    print("\n" + "="*70)
    if all_good:
        print("✅ INSTALLATION VERIFIED - Ready to run!")
        print("\nTest with:")
        print("    python OO_Automator_Plugin.py --parameter entry_time --max-workers 1")
    else:
        print("❌ INSTALLATION INCOMPLETE - Fix issues above")
    print("="*70)
    
    return all_good


def create_test_config():
    """Create a test configuration file"""
    print("\n" + "="*70)
    print("CREATING TEST CONFIGURATION")
    print("="*70)
    
    test_config = {
        "parameter_type": "entry_time",
        "start_time": "10:00",
        "end_time": "10:05",
        "interval_minutes": 1,
        "delay_seconds": 1,
        "backtest_timeout": 300,
        "max_workers": 1,
        "debug": True
    }
    
    config_file = 'test_config.json'
    
    try:
        import json
        with open(config_file, 'w') as f:
            json.dump(test_config, f, indent=2)
        print(f"✅ Created: {config_file}")
        print("\nThis config will test 6 entry times with 1 worker")
        print("Use it for initial testing:")
        print(f"    python OO_Automator_Plugin.py --config {config_file}")
        return True
    except Exception as e:
        print(f"❌ Error creating config: {e}")
        return False


def run_quick_test():
    """Try to import the new modules to check for syntax errors"""
    print("\n" + "="*70)
    print("RUNNING QUICK IMPORT TEST")
    print("="*70)
    
    modules_to_test = [
        ('utils.waiters', ['wait_clickable', 'find_any']),
        ('utils.selectors', ['NEW_BACKTEST_BTN', 'LOGIN_EMAIL']),
        ('pages.test_page', ['TestPage']),
    ]
    
    all_good = True
    
    for module_name, expected_items in modules_to_test:
        try:
            print(f"Testing {module_name}...", end=' ')
            module = __import__(module_name, fromlist=expected_items)
            
            missing = []
            for item in expected_items:
                if not hasattr(module, item):
                    missing.append(item)
            
            if missing:
                print(f"❌ Missing: {', '.join(missing)}")
                all_good = False
            else:
                print("✅")
        
        except Exception as e:
            print(f"❌ Import error: {e}")
            all_good = False
    
    if all_good:
        print("\n✅ All modules imported successfully!")
    else:
        print("\n❌ Some modules have issues - check errors above")
    
    return all_good


def show_comparison():
    """Show before/after comparison"""
    print("\n" + "="*70)
    print("BEFORE vs AFTER COMPARISON")
    print("="*70)
    
    comparison = """
BEFORE (Old Code):
├── OO_Automator_Plugin.py (5000+ lines, many time.sleep)
├── parameter_plugin_system.py (no verification)
└── trade_analysis_plugin.py

Issues:
  • Workers degrade over time (no driver recycling)
  • Parameters get lost (no verification)
  • Random timeouts (arbitrary sleeps)
  • Trade logs fail (no atomic download)
  • Hard to debug (print statements only)

AFTER (Refactored):
├── utils/
│   ├── waiters.py (robust WebDriverWait utilities)
│   └── selectors.py (centralized with fallbacks)
├── pages/
│   └── test_page.py (Page Object pattern)
├── OO_Automator_Plugin.py (cleaner, with logging & recycling)
├── parameter_plugin_system.py (with verify_value())
└── trade_analysis_plugin.py (unchanged)

Improvements:
  ✅ Driver recycles every 50 tests (prevents degradation)
  ✅ Parameter verification (3 retry attempts)
  ✅ Robust waits (no race conditions)
  ✅ Atomic download detection (stable file checks)
  ✅ Structured logging (worker IDs, milestones)
  ✅ Retry decorators (automatic error recovery)
  ✅ Page objects (maintainable, testable)
  
Expected Results:
  • 10-20% faster execution
  • Consistent performance (no degradation)
  • Higher success rate (fewer lost parameters)
  • Better debugging (structured logs)
"""
    print(comparison)


def main():
    parser = argparse.ArgumentParser(description='Migration helper for refactored automation')
    parser.add_argument('--check', action='store_true', help='Check current setup')
    parser.add_argument('--setup', action='store_true', help='Create new directory structure')
    parser.add_argument('--verify', action='store_true', help='Verify installation')
    parser.add_argument('--test', action='store_true', help='Run quick import test')
    parser.add_argument('--compare', action='store_true', help='Show before/after comparison')
    parser.add_argument('--all', action='store_true', help='Run full migration workflow')
    
    args = parser.parse_args()
    
    if args.all:
        print("FULL MIGRATION WORKFLOW")
        print("="*70)
        
        # Step 1: Check
        if not check_current_setup():
            print("\n❌ Missing required files. Cannot proceed.")
            return
        
        # Step 2: Setup
        if not create_directory_structure():
            print("\n❌ Failed to create directory structure")
            return
        
        # Step 3: Backup
        if not backup_original_files():
            print("\n❌ Failed to backup files")
            return
        
        # Step 4: Guide
        create_new_files_guide()
        
        # Step 5: Test config
        create_test_config()
        
        # Step 6: Comparison
        show_comparison()
        
        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print("1. Create the new files as shown above")
        print("2. Run: python migrate_to_refactored.py --verify")
        print("3. Run: python migrate_to_refactored.py --test")
        print("4. Test: python OO_Automator_Plugin.py --config test_config.json")
        print("="*70)
    
    elif args.check:
        check_current_setup()
    
    elif args.setup:
        create_directory_structure()
        backup_original_files()
        create_new_files_guide()
    
    elif args.verify:
        verify_installation()
    
    elif args.test:
        run_quick_test()
    
    elif args.compare:
        show_comparison()
    
    else:
        parser.print_help()
        print("\n" + "="*70)
        print("QUICK START:")
        print("="*70)
        print("Run full migration workflow:")
        print("    python migrate_to_refactored.py --all")
        print("\nOr run steps individually:")
        print("    python migrate_to_refactored.py --check")
        print("    python migrate_to_refactored.py --setup")
        print("    python migrate_to_refactored.py --verify")
        print("="*70)


if __name__ == "__main__":
    main()
