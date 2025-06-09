import logging
import re
import hashlib
from typing import List, Dict, Optional, Set
from antlr4 import InputStream, CommonTokenStream
from antlr4.tree.Tree import ParseTree
from antlr4 import ParserRuleContext, TerminalNode

from src.redusql.antlr4.SQLiteLexer import SQLiteLexer
from src.redusql.antlr4.SQLiteParser import SQLiteParser
from src.redusql.antlr4.SQLiteParserVisitor import SQLiteParserVisitor
from src.redusql.dd import DD
from src.redusql.outcome import Outcome

logger = logging.getLogger(__name__)


class SQLContentCache:
    """Cache for SQL content and test results to avoid redundant tests."""
    
    def __init__(self):
        self.content_cache: Dict[str, str] = {}  # Hash -> SQL content
        self.test_cache: Dict[str, bool] = {}    # Hash -> test result
        self.hit_count = 0
        self.miss_count = 0
    
    def get_sql_hash(self, sql_content: str) -> str:
        return hashlib.sha256(sql_content.encode('utf-8')).hexdigest()[:16]
    
    def get_cached_result(self, sql_content: str) -> Optional[bool]:
        sql_hash = self.get_sql_hash(sql_content)
        if sql_hash in self.test_cache:
            self.hit_count += 1
            return self.test_cache[sql_hash]
        self.miss_count += 1
        return None
    
    def cache_result(self, sql_content: str, result: bool):
        sql_hash = self.get_sql_hash(sql_content)
        self.test_cache[sql_hash] = result
        self.content_cache[sql_hash] = sql_content
    
    def get_stats(self) -> Dict[str, int]:
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        return {
            'hits': self.hit_count,
            'misses': self.miss_count,
            'hit_rate': hit_rate,
            'total_entries': len(self.test_cache)
        }


class HoistableNode:    
    def __init__(self, source_node: 'OptimizedSQLTreeNode', target_node: 'OptimizedSQLTreeNode', distance: int):
        self.source_node = source_node  # Node to be replaced
        self.target_node = target_node  # Replacement node (descendant)
        self.distance = distance        # Distance from source to target
        self.size_reduction = self._calculate_size_reduction()
    
    def _calculate_size_reduction(self) -> int:
        source_size = len(self.source_node.get_text())
        target_size = len(self.target_node.get_text())
        return max(0, source_size - target_size)
    
    def __lt__(self, other):
        if self.size_reduction != other.size_reduction:
            return self.size_reduction > other.size_reduction  # Larger reduction first
        return self.distance > other.distance  # Further distance first


class OptimizedSQLTreeNode:
    def __init__(self, parse_tree_node: ParseTree, level: int = 0, node_id: int = 0):
        self.parse_tree_node = parse_tree_node
        self.level = level
        self.node_id = node_id
        self.children: List['OptimizedSQLTreeNode'] = []
        self.parent: Optional['OptimizedSQLTreeNode'] = None
        self.is_pruned = False
        self.hoisted_node: Optional['OptimizedSQLTreeNode'] = None  # If this node was hoisted
        
        # Optimization: Cache node properties
        self._text_cache = None
        self._is_reducible = None
        self._child_count = None
        self._rule_name = None
    
    def get_root(self) -> 'OptimizedSQLTreeNode':
        current = self
        while current.parent:
            current = current.parent
        return current
        
    def add_child(self, child: 'OptimizedSQLTreeNode'):
        child.parent = self
        self.children.append(child)
        self._child_count = None  # Invalidate cache
    
    def prune(self):
        self.is_pruned = True
        self._text_cache = None  # Invalidate cache
    
    def unprune(self):
        self.is_pruned = False
        self._text_cache = None  # Invalidate cache
    
    def hoist(self, replacement_node: 'OptimizedSQLTreeNode'):
        self.hoisted_node = replacement_node
        self._text_cache = None  # Invalidate cache
    
    def unhoist(self):
        self.hoisted_node = None
        self._text_cache = None  # Invalidate cache
    
    def get_text(self) -> str:
        if self.is_pruned:
            return ""
        
        if self._text_cache is None:
            if self.hoisted_node:
                # Use hoisted node's text
                self._text_cache = self.hoisted_node.get_text()
            else:
                # Use original text
                self._text_cache = self.parse_tree_node.getText()
        
        return self._text_cache
    
    def get_rule_name(self) -> str:
        if self._rule_name is None:
            if isinstance(self.parse_tree_node, ParserRuleContext):
                # Try to get rule name from parser rule context
                if hasattr(self.parse_tree_node, 'getRuleIndex'):
                    rule_index = self.parse_tree_node.getRuleIndex()
                    try:
                        if rule_index < len(SQLiteParser.ruleNames):
                            self._rule_name = SQLiteParser.ruleNames[rule_index]
                    except:
                        pass
                
                # Fallback: get from class name
                if not self._rule_name:
                    class_name = self.parse_tree_node.__class__.__name__
                    if class_name.endswith('Context'):
                        self._rule_name = class_name[:-7]  # Remove 'Context' suffix
            elif isinstance(self.parse_tree_node, TerminalNode):
                self._rule_name = f"TOKEN_{self.parse_tree_node.getText()}"
            else:
                self._rule_name = "UNKNOWN"
        
        return self._rule_name
    
    def is_compatible_with(self, other: 'OptimizedSQLTreeNode') -> bool:
        # Nodes are compatible if they have the same grammar rule
        return self.get_rule_name() == other.get_rule_name()
    
    def get_subtree_size(self) -> int:
        if self.is_pruned:
            return 0
        
        if self.hoisted_node:
            return self.hoisted_node.get_subtree_size()
        
        size = 1  # Count this node
        for child in self.children:
            size += child.get_subtree_size()
        return size
    
    def find_hoistable_descendants(self, max_distance: int = 10) -> List['OptimizedSQLTreeNode']:
        hoistable = []
        
        def find_compatible_in_subtree(node: 'OptimizedSQLTreeNode', distance: int):
            if distance > max_distance or node.is_pruned:
                return
            
            # Check direct children first
            for child in node.children:
                if self.is_compatible_with(child) and not child.is_pruned:
                    # This child is compatible and could be hoisted
                    hoistable.append(child)
                else:
                    # Recursively search in this child's subtree
                    find_compatible_in_subtree(child, distance + 1)
        
        # Start search from direct children
        for child in self.children:
            find_compatible_in_subtree(child, 1)
        
        return hoistable
    
    def is_reducible(self) -> bool:
        if self._is_reducible is None:
            # Only consider nodes that:
            # 1. Have children (non-terminal)
            # 2. Are not just whitespace or single characters
            # 3. Are not at the deepest levels (likely terminals)
            
            if not self.children:
                self._is_reducible = False
            else:
                text = self.get_text().strip()
                # Skip nodes that are just punctuation or very short
                self._is_reducible = (
                    len(text) > 2 and 
                    not text in {';', ',', '(', ')', '.', ' '} and
                    len(self.children) > 1  # Must have multiple children to be worth reducing
                )
        
        return self._is_reducible
    
    def get_child_count(self) -> int:
        if self._child_count is None:
            self._child_count = len(self.children)
        return self._child_count


class HoistingTransformationManager:    
    def __init__(self, tester_func, verbose: bool = False):
        self.tester_func = tester_func
        self.verbose = verbose
        self.transformation_count = 0
    
    def find_best_hoisting_transformations(self, nodes: List[OptimizedSQLTreeNode], 
                                         tree_renderer) -> List[HoistableNode]:
        all_hoistable = []
        
        # Find all possible hoisting transformations
        for node in nodes:
            if node.is_pruned:
                continue
            
            hoistable_descendants = node.find_hoistable_descendants()
            for descendant in hoistable_descendants:
                if not descendant.is_pruned:
                    distance = self._calculate_distance(node, descendant)
                    hoistable = HoistableNode(node, descendant, distance)
                    all_hoistable.append(hoistable)
        
        if not all_hoistable:
            return []
        
        # Sort by priority (size reduction, then distance)
        all_hoistable.sort()
        
        if self.verbose:
            print(f"    Found {len(all_hoistable)} potential hoisting transformations")
        
        # Apply greedy selection of non-conflicting transformations
        selected_transformations = []
        used_sources = set()
        used_targets = set()
        
        for hoistable in all_hoistable:
            # Check if this transformation conflicts with already selected ones
            if (hoistable.source_node.node_id not in used_sources and 
                hoistable.target_node.node_id not in used_targets):
                
                # Test if this transformation maintains the bug
                if self._test_hoisting_transformation(hoistable, tree_renderer):
                    selected_transformations.append(hoistable)
                    used_sources.add(hoistable.source_node.node_id)
                    used_targets.add(hoistable.target_node.node_id)
                    
                    if self.verbose:
                        reduction = hoistable.size_reduction
                        print(f"    Selected hoisting: {hoistable.source_node.get_rule_name()} "
                              f"-> {hoistable.target_node.get_rule_name()} "
                              f"(distance: {hoistable.distance}, reduction: {reduction} chars)")
        
        return selected_transformations
    
    def _calculate_distance(self, ancestor: OptimizedSQLTreeNode, descendant: OptimizedSQLTreeNode) -> int:
        return descendant.level - ancestor.level
    
    def _test_hoisting_transformation(self, hoistable: HoistableNode, tree_renderer) -> bool:
        # Apply the hoisting transformation temporarily
        original_hoisted = hoistable.source_node.hoisted_node
        hoistable.source_node.hoist(hoistable.target_node)
        
        try:
            # Invalidate cache and render
            tree_renderer.invalidate_cache()
            test_sql = tree_renderer.render(hoistable.source_node.get_root())
            
            if not test_sql.strip():
                return False
            
            # Test if bug still occurs
            self.transformation_count += 1
            result = self.tester_func(test_sql, f"hoist_{self.transformation_count}")
            return result
            
        except Exception:
            return False
        finally:
            # Restore original state
            hoistable.source_node.hoisted_node = original_hoisted
            tree_renderer.invalidate_cache()
    
    def apply_transformations(self, transformations: List[HoistableNode], tree_renderer):
        for hoistable in transformations:
            hoistable.source_node.hoist(hoistable.target_node)
        
        if transformations:
            tree_renderer.invalidate_cache()



class OptimizedSQLTreeBuilder(SQLiteParserVisitor):
    def __init__(self):
        self.root_node: Optional[OptimizedSQLTreeNode] = None
        self.node_counter = 0
        self.levels_map: Dict[int, List[OptimizedSQLTreeNode]] = {}
        self.reducible_nodes: Set[int] = set()  # Track reducible node IDs
    
    def build_tree(self, parse_tree: ParseTree) -> OptimizedSQLTreeNode:
        """Build the hierarchical tree from ANTLR parse tree."""
        self.root_node = self._build_node(parse_tree, 0)
        self._identify_reducible_nodes()
        return self.root_node
    
    def _build_node(self, parse_tree_node: ParseTree, level: int) -> OptimizedSQLTreeNode:
        """Recursively build tree nodes."""
        node = OptimizedSQLTreeNode(parse_tree_node, level, self.node_counter)
        self.node_counter += 1
        
        # Add to levels map
        if level not in self.levels_map:
            self.levels_map[level] = []
        self.levels_map[level].append(node)
        
        # Process children
        child_count = parse_tree_node.getChildCount()
        if child_count > 0:
            for i in range(child_count):
                child_parse_node = parse_tree_node.getChild(i)
                child_node = self._build_node(child_parse_node, level + 1)
                node.add_child(child_node)
        
        return node
    
    def _identify_reducible_nodes(self):
        for level_nodes in self.levels_map.values():
            for node in level_nodes:
                if node.is_reducible():
                    self.reducible_nodes.add(node.node_id)
    
    def get_reducible_nodes_at_level(self, level: int) -> List[OptimizedSQLTreeNode]:
        all_nodes = self.levels_map.get(level, [])
        return [node for node in all_nodes if node.node_id in self.reducible_nodes]
    
    def get_nodes_at_level(self, level: int) -> List[OptimizedSQLTreeNode]:
        return self.levels_map.get(level, [])
    
    def get_max_level(self) -> int:
        return max(self.levels_map.keys()) if self.levels_map else 0


class OptimizedSQLTreeRenderer:
    def __init__(self):
        self._render_cache: Dict[int, str] = {}  # Node ID -> rendered text
        self._cache_valid = True
    
    def invalidate_cache(self):
        self._render_cache.clear()
        self._cache_valid = False
    
    def render(self, root_node: OptimizedSQLTreeNode) -> str:
        if not self._cache_valid:
            self._render_cache.clear()
            self._cache_valid = True
        
        result = self._render_node(root_node)
        return self._clean_and_format_sql(result)
    
    def _render_node(self, node: OptimizedSQLTreeNode) -> str:
        if node.is_pruned:
            return ""
        
        # Check cache first
        if node.node_id in self._render_cache:
            return self._render_cache[node.node_id]
        
        # Handle hoisted nodes
        if node.hoisted_node:
            result = self._render_node(node.hoisted_node)
        elif not node.children:
            # Terminal node (leaf), return its text with space
            token_text = node.parse_tree_node.getText()
            result = token_text + " " if token_text else ""
        else:
            # For non-terminal nodes, render all children
            result = ""
            for child in node.children:
                child_text = self._render_node(child)
                result += child_text
        
        # Cache the result
        self._render_cache[node.node_id] = result
        return result
    
    def _clean_and_format_sql(self, sql: str) -> str:
        if not sql:
            return sql
        
        # Replace multiple spaces with single space
        sql = re.sub(r'\s+', ' ', sql)
        
        # Clean up the result
        sql = sql.strip()
        
        # Add final semicolon if missing and this looks like a complete statement
        if sql and not sql.endswith(';'):
            sql += ';'
        
        return sql


class OptimizedHierarchicalDeltaDebuggerWithHoisting:
    """
    Optimized HDD implementation with hoisting for better reduction quality.
    Implements the HDDH algorithm (HDD + Hoisting) from https://arxiv.org/abs/2104.03637.
    """
    
    def __init__(self, original_sql: str, tester_func, verbose: bool = False):
        self.original_sql = original_sql
        self.tester_func = tester_func
        self.verbose = verbose
        
        self.content_cache = SQLContentCache()
        self.hoisting_manager = HoistingTransformationManager(tester_func, verbose)
        
        self.tree_builder = OptimizedSQLTreeBuilder()
        self.tree_renderer = OptimizedSQLTreeRenderer()
        self.root_node = self._parse_sql(original_sql)
        
        self.test_count = 0
        self.cache_hits = 0
        self.hoisting_count = 0
        
        if self.verbose:
            print(f"Parsed SQL into tree with {self.tree_builder.get_max_level() + 1} levels")
            print(f"Identified {len(self.tree_builder.reducible_nodes)} reducible nodes")
    
    def _parse_sql(self, sql: str) -> OptimizedSQLTreeNode:
        try:
            # Create ANTLR input stream
            input_stream = InputStream(sql)
            
            # Create lexer
            lexer = SQLiteLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            
            # Create parser
            parser = SQLiteParser(token_stream)
            
            # Parse the SQL (starting from the root rule)
            parse_tree = parser.parse()
            
            # Build our hierarchical tree
            root_node = self.tree_builder.build_tree(parse_tree)
            
            return root_node
            
        except Exception as e:
            logger.error(f"Failed to parse SQL: {e}")
            raise
    
    def reduce(self) -> str:
        logger.info("Starting Optimized Hierarchical Delta Debugging with Hoisting")
        
        # Get initial statistics
        max_level = self.tree_builder.get_max_level()
        total_nodes = sum(len(self.tree_builder.get_nodes_at_level(i)) for i in range(max_level + 1))
        reducible_nodes = len(self.tree_builder.reducible_nodes)
        
        if self.verbose:
            print(f"Tree structure: {max_level + 1} levels, {total_nodes} total nodes")
            print(f"Reducible nodes: {reducible_nodes}/{total_nodes}")
            print("Algorithm: HDDH (HDD + Hoisting)")
        
        # Apply HDDH level by level
        levels_processed = 0
        nodes_pruned = 0
        total_hoisted = 0
        
        for level in range(max_level + 1):
            logger.info(f"Processing level {level}")
            
            # Get reducible nodes at this level
            reducible_nodes_at_level = self.tree_builder.get_reducible_nodes_at_level(level)
            if not reducible_nodes_at_level:
                continue
            
            if self.verbose:
                total_at_level = len(self.tree_builder.get_nodes_at_level(level))
                print(f"\nLevel {level}/{max_level}: {len(reducible_nodes_at_level)}/{total_at_level} reducible nodes")
            
            # HDDH Step 1: Apply DDMIN (traditional HDD pruning)
            nodes_before = len([n for n in reducible_nodes_at_level if not n.is_pruned])
            if nodes_before > 1:
                self._reduce_level(level, reducible_nodes_at_level)
                nodes_after = len([n for n in reducible_nodes_at_level if not n.is_pruned])
                
                pruned_this_level = nodes_before - nodes_after
                nodes_pruned += pruned_this_level
                
                if self.verbose and pruned_this_level > 0:
                    print(f"  Pruning: removed {pruned_this_level} nodes")
            
            # HDDH Step 2: Apply TMIN_χ (hoisting transformations)
            remaining_nodes = [n for n in reducible_nodes_at_level if not n.is_pruned]
            if remaining_nodes:
                if self.verbose:
                    print(f"  Hoisting: analyzing {len(remaining_nodes)} remaining nodes...")
                
                hoisting_transformations = self.hoisting_manager.find_best_hoisting_transformations(
                    remaining_nodes, self.tree_renderer
                )
                
                if hoisting_transformations:
                    self.hoisting_manager.apply_transformations(hoisting_transformations, self.tree_renderer)
                    hoisted_this_level = len(hoisting_transformations)
                    total_hoisted += hoisted_this_level
                    
                    if self.verbose:
                        print(f"  Hoisting: applied {hoisted_this_level} transformations")
                elif self.verbose:
                    print(f"  Hoisting: no beneficial transformations found")
            
            levels_processed += 1
        
        # Render the final reduced tree
        reduced_sql = self.tree_renderer.render(self.root_node)
        
        # Get final statistics
        cache_stats = self.content_cache.get_stats()
        
        logger.info(f"HDDH completed: processed {levels_processed} levels, "
                   f"pruned {nodes_pruned} nodes, hoisted {total_hoisted} nodes")
        
        if self.verbose:
            print(f"\nHDDH Summary:")
            print(f"  Levels processed: {levels_processed}")
            print(f"  Nodes pruned: {nodes_pruned}/{reducible_nodes}")
            print(f"  Nodes hoisted: {total_hoisted}")
            print(f"  Total tests: {self.test_count + self.hoisting_manager.transformation_count}")
            print(f"  Cache hits: {cache_stats['hits']}")
            print(f"  Cache hit rate: {cache_stats['hit_rate']:.1f}%")
            if reducible_nodes > 0:
                print(f"  Reduction rate: {(nodes_pruned/reducible_nodes)*100:.1f}%")
                print(f"  Hoisting rate: {(total_hoisted/reducible_nodes)*100:.1f}%")
        
        return reduced_sql
    
    def _reduce_level(self, level: int, nodes: List[OptimizedSQLTreeNode]):
        if len(nodes) <= 1:
            return
        
        # Create a configuration (list of node indices that should be kept)
        initial_config = list(range(len(nodes)))
        
        # Create a tester function for this level
        def level_tester(config, config_id):
            return self._test_level_config(level, nodes, config, config_id)
        
        # Apply DD to this level
        dd = DD(level_tester)
        
        try:
            minimal_config = dd(initial_config)
            
            # Prune nodes that are not in the minimal configuration
            for i, node in enumerate(nodes):
                if i not in minimal_config:
                    node.prune()
                    # Invalidate renderer cache since tree structure changed
                    self.tree_renderer.invalidate_cache()
                    if self.verbose:
                        print(f"    Pruned node {node.node_id} at level {level}")
            
            logger.info(f"Level {level}: reduced from {len(nodes)} to {len(minimal_config)} nodes")
            
        except Exception as e:
            logger.warning(f"DD failed at level {level}: {e}")
    
    def _test_level_config(self, level: int, nodes: List[OptimizedSQLTreeNode], 
                          config: List[int], config_id) -> Outcome:
        # Save current pruning state for rollback
        original_states = [(node, node.is_pruned) for node in nodes]
        
        try:
            # Apply the configuration (prune nodes not in config)
            state_changed = False
            for i, node in enumerate(nodes):
                new_state = i not in config
                if node.is_pruned != new_state:
                    if new_state:
                        node.prune()
                    else:
                        node.unprune()
                    state_changed = True
            
            # Only invalidate cache if state actually changed
            if state_changed:
                self.tree_renderer.invalidate_cache()
            
            # Render the current tree state
            current_sql = self.tree_renderer.render(self.root_node)
            
            # Skip empty SQL (would cause parse errors)
            if not current_sql.strip():
                return Outcome.PASS
            
            # Check cache first
            cached_result = self.content_cache.get_cached_result(current_sql)
            if cached_result is not None:
                if self.verbose:
                    print(f"      Config {config_id}: CACHED - {'FAIL' if cached_result else 'PASS'}")
                return Outcome.FAIL if cached_result else Outcome.PASS
            
            # Test if this configuration still triggers the bug
            if self.verbose:
                print(f"      Testing config {config_id}: {len(config)}/{len(nodes)} nodes")
                print(f"      SQL length: {len(current_sql)} chars")
            
            # Call the external tester function
            self.test_count += 1
            result = self.tester_func(current_sql, config_id)
            
            # Cache the result
            self.content_cache.cache_result(current_sql, result)
            
            if self.verbose:
                outcome_str = "FAIL" if result else "PASS"
                print(f"      Config {config_id}: {outcome_str}")
            
            return Outcome.FAIL if result else Outcome.PASS
            
        except Exception as e:
            logger.debug(f"Test failed with exception: {e}")
            return Outcome.PASS
        
        finally:
            # Restore original pruning state
            for node, original_state in original_states:
                if node.is_pruned != original_state:
                    node.is_pruned = original_state
                    self.tree_renderer.invalidate_cache()


def apply_optimized_hdd(original_sql: str, tester_func, verbose: bool = False) -> str:
    hdd = OptimizedHierarchicalDeltaDebuggerWithHoisting(original_sql, tester_func, verbose)
    return hdd.reduce()


# # Convenience function for applying hoisting only
# def apply_hoisting_only(original_sql: str, tester_func, verbose: bool = False) -> str:
#     """
#     Apply only hoisting transformations without traditional HDD pruning.
#     Useful for comparison or as a preprocessing step.
    
#     :param original_sql: The original SQL query to reduce.
#     :param tester_func: Function that tests if a SQL query triggers the bug.
#     :param verbose: Enable verbose output.
#     :return: The reduced SQL query with hoisting applied.
#     """
#     if verbose:
#         print("Applying Hoisting-Only Algorithm...")
    
#     # Create the debugger instance
#     hdd = OptimizedHierarchicalDeltaDebuggerWithHoisting(original_sql, tester_func, verbose)
    
#     # Apply only hoisting (skip the pruning step)
#     max_level = hdd.tree_builder.get_max_level()
#     total_hoisted = 0
    
#     for level in range(max_level + 1):
#         nodes_at_level = hdd.tree_builder.get_nodes_at_level(level)
#         if not nodes_at_level:
#             continue
        
#         if verbose:
#             print(f"\nLevel {level}/{max_level}: {len(nodes_at_level)} nodes")
        
#         # Apply only hoisting transformations
#         hoisting_transformations = hdd.hoisting_manager.find_best_hoisting_transformations(
#             nodes_at_level, hdd.tree_renderer
#         )
        
#         if hoisting_transformations:
#             hdd.hoisting_manager.apply_transformations(hoisting_transformations, hdd.tree_renderer)
#             hoisted_this_level = len(hoisting_transformations)
#             total_hoisted += hoisted_this_level
            
#             if verbose:
#                 print(f"  Applied {hoisted_this_level} hoisting transformations")
    
#     # Render the final result
#     reduced_sql = hdd.tree_renderer.render(hdd.root_node)
    
#     if verbose:
#         print(f"\nHoisting Summary:")
#         print(f"  Total hoisted nodes: {total_hoisted}")
#         print(f"  Total tests: {hdd.hoisting_manager.transformation_count}")
    
#     return reduced_sql


# # Alternative HDDH implementation that applies hoisting first, then pruning
# def apply_hoist_then_prune(original_sql: str, tester_func, verbose: bool = False) -> str:
#     """
#     Apply hoisting first as preprocessing, then traditional HDD pruning.
#     This can sometimes achieve better results than interleaved HDDH.
    
#     :param original_sql: The original SQL query to reduce.
#     :param tester_func: Function that tests if a SQL query triggers the bug.
#     :param verbose: Enable verbose output.
#     :return: The reduced SQL query.
#     """
#     if verbose:
#         print("=== Two-Phase Algorithm: Hoisting + HDD ===")
#         print("Phase 1: Applying hoisting transformations...")
    
#     # Phase 1: Apply hoisting only
#     hoisted_sql = apply_hoisting_only(original_sql, tester_func, verbose)
    
#     if verbose:
#         original_len = len(original_sql)
#         hoisted_len = len(hoisted_sql)
#         if original_len > 0:
#             reduction = (1 - hoisted_len / original_len) * 100
#             print(f"Hoisting phase: {reduction:.1f}% reduction")
#         print("\nPhase 2: Applying traditional HDD pruning...")
    
#     # Phase 2: Apply traditional optimized HDD (without hoisting)
#     # We need to create a version that doesn't do hoisting
#     class OptimizedHDDWithoutHoisting(OptimizedHierarchicalDeltaDebuggerWithHoisting):
#         def reduce(self):
#             # Call the parent class but skip hoisting steps
#             max_level = self.tree_builder.get_max_level()
#             total_nodes = sum(len(self.tree_builder.get_nodes_at_level(i)) for i in range(max_level + 1))
#             reducible_nodes = len(self.tree_builder.reducible_nodes)
            
#             levels_processed = 0
#             nodes_pruned = 0
            
#             for level in range(max_level + 1):
#                 reducible_nodes_at_level = self.tree_builder.get_reducible_nodes_at_level(level)
#                 if not reducible_nodes_at_level:
#                     continue
                
#                 # Only apply pruning, no hoisting
#                 nodes_before = len([n for n in reducible_nodes_at_level if not n.is_pruned])
#                 if nodes_before > 1:
#                     self._reduce_level(level, reducible_nodes_at_level)
#                     nodes_after = len([n for n in reducible_nodes_at_level if not n.is_pruned])
                    
#                     pruned_this_level = nodes_before - nodes_after
#                     nodes_pruned += pruned_this_level
                
#                 levels_processed += 1
            
#             return self.tree_renderer.render(self.root_node)
    
#     # Apply pruning to the hoisted result
#     hdd_pruner = OptimizedHDDWithoutHoisting(hoisted_sql, tester_func, verbose)
#     final_sql = hdd_pruner.reduce()
    
#     if verbose:
#         final_len = len(final_sql)
#         if len(original_sql) > 0:
#             total_reduction = (1 - final_len / len(original_sql)) * 100
#             print(f"\nTwo-phase total reduction: {total_reduction:.1f}%")
    
#     return final_sql
