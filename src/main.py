#!/usr/bin/env python3

import argparse
import logging
import os
import sys
import traceback

from src.redusql.iterator import IteratorRegistry
from src.redusql.reducer import SQLReducer

logger = logging.getLogger('redusql')


def create_parser():
    """Create the command-line argument parser."""
    
    parser = argparse.ArgumentParser(
        description='ReduSQL - Bug-Triggering SQL Query Reducer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  redusql --query query_to_reduce.sql --test test_script.sh
  
The test script should:
  - Read the SQL query path from TEST_CASE_LOCATION environment variable
  - Return exit code 0 if the bug still occurs
  - Return exit code 1 if the bug no longer occurs
        """
    )
    
    parser.add_argument(
        '--query',
        metavar='FILE',
        required=True,
        help='SQL query file to reduce'
    )
    
    parser.add_argument(
        '--test',
        metavar='FILE',
        required=True,
        help='test script that checks if the bug still occurs'
    )
    
    # Output settings
    parser.add_argument(
        '--output',
        metavar='FILE',
        help='path to save the reduced query (default: auto-generated)'
    )
    
    # Parallel settings
    parser.add_argument(
        '--parallel',
        action='store_true',
        default=False,
        help='run DD in parallel'
    )
    
    # Iterator settings
    parser.add_argument(
        '--complement-first',
        dest='subset_first',
        action='store_false',
        default=True,
        help='check complements first'
    )
    
    parser.add_argument(
        '--subset-iterator',
        metavar='NAME',
        choices=sorted(IteratorRegistry.registry.keys()),
        default='forward',
        help='ordering strategy for looping through subsets (%(choices)s; default: %(default)s)'
    )
    
    parser.add_argument(
        '--complement-iterator',
        metavar='NAME',
        choices=sorted(IteratorRegistry.registry.keys()),
        default='forward',
        help='ordering strategy for looping through complements (%(choices)s; default: %(default)s)'
    )

    parser.add_argument(
        '--atom',
        metavar='NAME',
        choices=['token', 'line', 'both'],
        default='line',
        help='atom (i.e., granularity) of input (%(choices)s; default: %(default)s)'
    )
    
    # Logging settings
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='enable verbose output'
    )
    
    return parser


def configure_logging(args):
    """Configure logging based on command-line arguments."""
    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def set_test_case_location(args):
    """Set the TEST_CASE_LOCATION environment variable based on the --query argument."""
    if args.query:
        # Use the provided query path
        test_case_location = args.query
    else:
        # Use default path if --query is not provided
        test_case_location = '/app/query.sql'
    
    os.environ['TEST_CASE_LOCATION'] = test_case_location
    logger.debug(f'Set TEST_CASE_LOCATION to: {test_case_location}')


def validate_args(args):
    """Validate command-line arguments."""
    # Determine the query file path
    query_file = args.query if args.query else '/app/query.sql'
    
    # Check that input files exist
    if not os.path.exists(query_file):
        raise ValueError(f'Query file does not exist: {query_file}')
    
    if not os.path.exists(args.test):
        raise ValueError(f'Test script does not exist: {args.test}')
    
    if not os.access(args.test, os.X_OK):
        raise ValueError(f'Test script is not executable: {args.test}')


def main():
    """Main entry point for ReduSQL."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        configure_logging(args)
        
        set_test_case_location(args)
        
        validate_args(args)
        
        query_file = args.query if args.query else '/app/query.sql'
        
        # Create reducer instance
        reducer = SQLReducer(query_file, args.test, verbose=args.verbose)
        
        # Run reduction with specified parameters
        reduced_query = reducer.reduce(
            parallel=args.parallel,
            subset_first=args.subset_first,
            subset_iterator=args.subset_iterator,
            complement_iterator=args.complement_iterator,
            atom=args.atom
        )
        
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
            
    except ValueError as e:
        parser.error(str(e))
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
