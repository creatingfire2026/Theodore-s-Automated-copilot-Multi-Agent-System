"""WorkflowSpec: structured definition of an agent's complete workflow."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InputField:
    """Describes a single input parameter for an agent task."""

    name: str
    type: str
    required: bool
    description: str
    example: Any = None


@dataclass
class OutputField:
    """Describes a single field in an agent's result dictionary."""

    name: str
    type: str
    description: str
    example: Any = None


@dataclass
class ErrorCase:
    """Documents a known error condition and how the agent handles it."""

    condition: str
    response: str
    example_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowSpec:
    """Structured specification of an agent workflow.

    Attributes:
        name:           Human-readable workflow name.
        objective:      One-sentence statement of what the workflow achieves.
        inputs:         List of InputField objects describing accepted parameters.
        outputs:        List of OutputField objects describing returned data.
        dependencies:   External services, libraries, or agents this workflow relies on.
        error_handling: List of ErrorCase objects documenting failure modes.
        use_cases:      Concrete examples of when and how to invoke this workflow.
    """

    name: str
    objective: str
    inputs: List[InputField] = field(default_factory=list)
    outputs: List[OutputField] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    error_handling: List[ErrorCase] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the spec to a plain dictionary for logging or display."""
        return {
            "name": self.name,
            "objective": self.objective,
            "inputs": [
                {
                    "name": f.name,
                    "type": f.type,
                    "required": f.required,
                    "description": f.description,
                    "example": f.example,
                }
                for f in self.inputs
            ],
            "outputs": [
                {
                    "name": f.name,
                    "type": f.type,
                    "description": f.description,
                    "example": f.example,
                }
                for f in self.outputs
            ],
            "dependencies": self.dependencies,
            "error_handling": [
                {
                    "condition": e.condition,
                    "response": e.response,
                    "example_payload": e.example_payload,
                }
                for e in self.error_handling
            ],
            "use_cases": self.use_cases,
        }
