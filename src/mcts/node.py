"""MCTS Tree Node Representation.

Defines the MCTSNode dataclass representing a discrete candidate index configuration state
within the Monte Carlo Tree Search space.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, FrozenSet
from src.engine.hypo_cost_engine import HypoIndex


@dataclass
class MCTSNode:
    """Represents a state node in the MCTS index selection tree."""
    state_indexes: FrozenSet[HypoIndex]
    cumulative_size_bytes: int
    parent: Optional['MCTSNode'] = None
    action_from_parent: Optional[HypoIndex] = None
    children: Dict[HypoIndex, 'MCTSNode'] = field(default_factory=dict)
    untried_actions: List[HypoIndex] = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    best_reward: float = 0.0

    @property
    def q_value(self) -> float:
        """Returns empirical mean reward Q(s) = W / N."""
        return self.total_reward / self.visits if self.visits > 0 else 0.0

    @property
    def is_fully_expanded(self) -> bool:
        """Returns True if all valid candidate index actions from this state have been tried."""
        return len(self.untried_actions) == 0

    @property
    def is_leaf(self) -> bool:
        """Returns True if node has no expanded children."""
        return len(self.children) == 0

    def add_child(self, action: HypoIndex, child_node: 'MCTSNode') -> None:
        """Attaches a child node for the given action and removes action from untried."""
        self.children[action] = child_node
        if action in self.untried_actions:
            self.untried_actions.remove(action)

    def update(self, reward: float) -> None:
        """Backpropagates visit count and accumulated reward to this node."""
        self.visits += 1
        self.total_reward += reward
        if reward > self.best_reward:
            self.best_reward = reward
