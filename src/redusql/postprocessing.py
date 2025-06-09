import re

from src.redusql.tokenizer import SQLTokenizer


def remove_consecutive_semicolons(sql_text: str, verbose: bool = False) -> str:
    if not sql_text:
        return sql_text
    
    original_length = len(sql_text)
    
    # Replace multiple consecutive semicolons with single semicolon
    cleaned_sql = re.sub(r';+', ';', sql_text)
    
    # Also clean up semicolons with only whitespace between them
    cleaned_sql = re.sub(r';\s*;+', ';', cleaned_sql)
    
    removed_chars = original_length - len(cleaned_sql)
    
    if verbose and removed_chars > 0:
        print(f"Post-processing: Removed {removed_chars} characters of consecutive semicolons")
    
    return cleaned_sql


def remove_consecutive_semicolons_from_tokens(tokens: list, verbose: bool = False) -> list:
    if not tokens:
        return tokens
    
    cleaned_tokens = []
    prev_was_semicolon = False
    removed_count = 0
    
    for token in tokens:
        current_is_semicolon = (token.strip() == ';')
        
        if current_is_semicolon and prev_was_semicolon:
            # Skip this semicolon (consecutive)
            removed_count += 1
            if verbose:
                print(f"  Removed consecutive semicolon at position {len(cleaned_tokens)}")
        else:
            # Keep this token
            cleaned_tokens.append(token)
            prev_was_semicolon = current_is_semicolon
    
    if verbose and removed_count > 0:
        print(f"Post-processing: Removed {removed_count} consecutive semicolon tokens")
    
    return cleaned_tokens


def apply_semicolon_postprocessing(reduced_sql: str, verbose: bool = False) -> str:
    if verbose:
        print("\n=== Semicolon Post-Processing ===")
        original_char_count = len(reduced_sql)
    
    # Token-level cleanup
    try:
        tokens = SQLTokenizer.tokenize(reduced_sql)
        original_token_count = len(tokens)
        
        if verbose:
            semicolon_count = sum(1 for t in tokens if t.strip() == ';')
            print(f"Original: {original_token_count} tokens ({semicolon_count} semicolons)")
        
        cleaned_tokens = remove_consecutive_semicolons_from_tokens(tokens, verbose)
        
        # Reconstruct SQL
        cleaned_sql = SQLTokenizer.detokenize(cleaned_tokens)
        
        if verbose:
            final_token_count = len(cleaned_tokens)
            final_semicolon_count = sum(1 for t in cleaned_tokens if t.strip() == ';')
            print(f"After token cleanup: {final_token_count} tokens ({final_semicolon_count} semicolons)")
            print(f"Removed {original_token_count - final_token_count} tokens")
        
    except Exception as e:
        if verbose:
            print(f"Token-level cleanup failed: {e}, falling back to string-level cleanup")
        cleaned_sql = reduced_sql
    
    # String-level cleanup (fallback and additional cleaning)
    final_sql = remove_consecutive_semicolons(cleaned_sql, verbose)
    
    if verbose:
        final_char_count = len(final_sql)
        total_removed = original_char_count - final_char_count
        if total_removed > 0:
            print(f"Total characters removed: {total_removed}")
        print("=== Post-Processing Complete ===")
    
    return final_sql

def remove_eof_from_tokens(tokens: list, verbose: bool = False) -> list:
    """
    Remove "< EOF >" tokens from the token list.
    This handles the case where EOF appears as separate tokens: '<', 'EOF', '>'
    """
    if not tokens:
        return tokens
    
    cleaned_tokens = []
    removed_count = 0
    i = 0
    
    while i < len(tokens):
        # Check for EOF pattern: '<', 'EOF', '>'
        if (i + 2 < len(tokens) and 
            tokens[i].strip() == '<' and 
            tokens[i + 1].strip().upper() == 'EOF' and 
            tokens[i + 2].strip() == '>'):
            
            # Skip the EOF pattern
            removed_count += 3
            if verbose:
                print(f"  Removed EOF pattern at positions {i}-{i+2}: {tokens[i:i+3]}")
            i += 3
            continue
        
        # Also check for single 'EOF' token (in case it appears without brackets)
        elif tokens[i].strip().upper() == 'EOF':
            removed_count += 1
            if verbose:
                print(f"  Removed standalone EOF token at position {i}: '{tokens[i]}'")
            i += 1
            continue
        
        # Keep this token
        cleaned_tokens.append(tokens[i])
        i += 1
    
    if verbose and removed_count > 0:
        print(f"Post-processing: Removed {removed_count} EOF-related tokens")
    
    return cleaned_tokens


def apply_complete_postprocessing(reduced_sql: str, verbose: bool = False) -> str:
    """
    Apply complete post-processing to reduced SQL, including:
    1. EOF removal
    2. Consecutive semicolon removal
    """
    if verbose:
        print("\n=== Complete Post-Processing ===")
        original_char_count = len(reduced_sql)
    
    # Token-level cleanup
    try:
        # Tokenize
        tokens = SQLTokenizer.tokenize(reduced_sql)
        original_token_count = len(tokens)
        
        if verbose:
            semicolon_count = sum(1 for t in tokens if t.strip() == ';')
            eof_count = sum(1 for i, t in enumerate(tokens) 
                          if (t.strip().upper() == 'EOF' or 
                              (i + 2 < len(tokens) and 
                               t.strip() == '<' and 
                               tokens[i + 1].strip().upper() == 'EOF' and 
                               tokens[i + 2].strip() == '>')))
            print(f"Original: {original_token_count} tokens ({semicolon_count} semicolons, ~{eof_count} EOF-related)")
        
        # Remove EOF tokens first
        cleaned_tokens = remove_eof_from_tokens(tokens, verbose)
        
        # Then remove consecutive semicolons
        cleaned_tokens = remove_consecutive_semicolons_from_tokens(cleaned_tokens, verbose)
        
        # Reconstruct SQL
        cleaned_sql = SQLTokenizer.detokenize(cleaned_tokens)
        
        if verbose:
            final_token_count = len(cleaned_tokens)
            final_semicolon_count = sum(1 for t in cleaned_tokens if t.strip() == ';')
            print(f"After cleanup: {final_token_count} tokens ({final_semicolon_count} semicolons)")
            print(f"Removed {original_token_count - final_token_count} tokens total")
        
    except Exception as e:
        if verbose:
            print(f"Token-level cleanup failed: {e}, falling back to string-level cleanup")
        cleaned_sql = reduced_sql
    
    # String-level cleanup (fallback and additional cleaning)
    final_sql = remove_consecutive_semicolons(cleaned_sql, verbose)
    
    if verbose:
        final_char_count = len(final_sql)
        total_removed = original_char_count - final_char_count
        if total_removed > 0:
            print(f"Total characters removed: {total_removed}")
        print("=== Post-Processing Complete ===")
    
    return final_sql
