#!/usr/bin/python3

import argparse
import sys
import traceback

from delta_debugging import SQLReducer


def main():
    """Main entry point for the ReduSQL tool."""
    parser = argparse.ArgumentParser(
        description="ReduSQL - Automated Reduction of Bug-Triggering SQL Queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  main.py --query buggy_query.sql --test test_script.sh
  
The test script should:
  - Take the path to a SQL query file as its first argument
  - Return exit code 0 if the bug still occurs
  - Return exit code 1 if the bug no longer occurs
        """
    )
    
    parser.add_argument(
        "--query",
        required=True,
        help="Path to the SQL query file to reduce"
    )
    
    parser.add_argument(
        "--test",
        required=True,
        help="Path to the test script that checks if the bug still occurs"
    )
    
    parser.add_argument(
        "--output",
        help="Path to save the reduced query (default: auto-generated)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Create reducer instance
        reducer = SQLReducer(args.query, args.test, verbose=args.verbose)
        
        # Run reduction
        reduced_query = reducer.reduce()
        
        if reduced_query is not None:
            # Save the result
            reducer.save_reduced_query(args.output)
            print("\n" + "="*60)
            print("✓ Reduction completed successfully!")
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("✗ Reduction failed!")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nReduction interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
