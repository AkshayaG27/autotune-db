"""Upper Confidence Bound for Trees (UCT) Selection Policy.

Implements the multi-armed bandit selection policy for MCTS balancing
exploitation (mean reward Q) and exploration (uncertainty bonus from Hoeffding's Inequality).
"""

import math
from typing import Tuple, Optional
from src.engine.hypo_cost_engine import HypoIndex
from src.mcts.node import MCTSNode


class UCTPolicy:
    """Implements Upper Confidence Bound for Trees (UCT) selection policy."""

    @staticmethod
    def compute_uct(
        parent_visits: int,
        child_visits: int,
        child_q_value: float,
        c_param: float = 1.414
    ) -> float:
        """Computes UCT value: Q(s, a) + c * sqrt(ln(N(s)) / N(s, a)).
        
        Args:
            parent_visits: Total visits N of the parent node.
            child_visits: Total visits n of the candidate child action.
            child_q_value: Mean empirical reward Q of the child.
            c_param: Exploration constant (default sqrt(2) ~= 1.414).
            
        Returns:
            UCT scalar. Returns float('inf') if child_visits == 0 to guarantee
            that unvisited actions are explored first.
        """
        if child_visits == 0:
            return float('inf')
        if parent_visits <= 0:
            return child_q_value

        exploitation = child_q_value
        exploration = c_param * math.sqrt(math.log(parent_visits) / child_visits)
        return exploitation + exploration

    @classmethod
    def select_best_child(
        cls,
        node: MCTSNode,
        c_param: float = 1.414
    ) -> Tuple[HypoIndex, MCTSNode]:
        """Selects the child node maximizing the UCT score.
        
        Args:
            node: Parent MCTSNode with expanded children.
            c_param: Exploration constant.
            
        Returns:
            Tuple of (action, best_child_node).
            
        Raises:
            ValueError: If the node has no children.
        """
        if not node.children:
            raise ValueError("Cannot select child from a node with no children.")

        best_action: Optional[HypoIndex] = None
        best_child: Optional[MCTSNode] = None
        best_score = float('-inf')

        for action, child in node.children.items():
            score = cls.compute_uct(
                parent_visits=node.visits,
                child_visits=child.visits,
                child_q_value=child.q_value,
                c_param=c_param
            )
            if score > best_score:
                best_score = score
                best_action = action
                best_child = child

        if best_action is None or best_child is None:
            raise RuntimeError("Failed to select child node.")

        return best_action, best_child
