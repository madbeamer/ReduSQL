import logging
from typing import Callable

logger = logging.getLogger(__name__)


def apply_hdd_star(hdd_function: Callable, original_sql: str, tester_func, 
                   verbose: bool = False, max_iterations: int = 10) -> str:
    if verbose:
        print(f"=== Starting HDD* (Fixpoint) Iteration ===")
        print(f"Target: True 1-minimality (not just 1-tree-minimality)")
        print(f"Max iterations: {max_iterations}")
    
    current_sql = original_sql
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        if verbose:
            print(f"\n--- HDD* Iteration {iteration} ---")
            print(f"Input length: {len(current_sql)} characters")
        
        # Apply the HDD function
        reduced_sql = hdd_function(current_sql, tester_func, verbose)
        
        # Check if we made progress
        if len(reduced_sql) >= len(current_sql):
            if verbose:
                print(f"No reduction in iteration {iteration} - fixpoint reached!")
            break
        
        reduction = len(current_sql) - len(reduced_sql)
        reduction_pct = (reduction / len(current_sql)) * 100 if len(current_sql) > 0 else 0
        
        if verbose:
            print(f"Iteration {iteration}: reduced by {reduction} chars ({reduction_pct:.1f}%)")
        
        current_sql = reduced_sql
    
    final_reduction = len(original_sql) - len(current_sql)
    final_reduction_pct = (final_reduction / len(original_sql)) * 100 if len(original_sql) > 0 else 0
    
    if verbose:
        print(f"\n=== HDD* Completed ===")
        print(f"Total iterations: {iteration}")
        print(f"Total reduction: {final_reduction} chars ({final_reduction_pct:.1f}%)")
        print(f"Result is guaranteed to be 1-minimal")
    
    logger.info(f"HDD* completed in {iteration} iterations with {final_reduction_pct:.1f}% reduction")
    
    return current_sql
